from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from tax_agent.rules_loader import RuleRepository

REQUIRED_SNAPSHOT_FILES = ("rules.yaml", "fx_policy.yaml", "disclaimers.yaml")
OPTIONAL_SNAPSHOT_FILES = ("fx_rates.yaml", "snapshot_meta.yaml")
VALID_STATUSES = frozenset({"draft", "review", "stable", "deprecated"})


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SnapshotInfo:
    snapshot_folder: str
    snapshot_id: str
    status: str
    effective_from: str | None
    checksum: str
    path: Path


class RuleRegistry:
    def __init__(self, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or (_repo_root() / "rules")
        self.repo = RuleRepository(self.rules_dir)

    def pack_dir(self, rule_pack_id: str) -> Path:
        return self.rules_dir / rule_pack_id

    def snapshot_dir(self, rule_pack_id: str, snapshot_folder: str) -> Path:
        return self.pack_dir(rule_pack_id) / "snapshots" / snapshot_folder

    def load_manifest(self, rule_pack_id: str) -> dict[str, Any]:
        return self.repo._load_manifest(rule_pack_id)

    def save_manifest(self, rule_pack_id: str, manifest: dict[str, Any]) -> None:
        path = self.pack_dir(rule_pack_id) / "manifest.yaml"
        path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def read_meta(self, snap_dir: Path) -> dict[str, Any]:
        meta_path = snap_dir / "snapshot_meta.yaml"
        if meta_path.is_file():
            data = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        return {"status": "draft"}

    def write_meta(self, snap_dir: Path, meta: dict[str, Any]) -> None:
        (snap_dir / "snapshot_meta.yaml").write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def snapshot_checksum(self, snap_dir: Path) -> str:
        h = hashlib.sha256()
        for name in sorted(REQUIRED_SNAPSHOT_FILES):
            p = snap_dir / name
            if p.is_file():
                h.update(name.encode())
                h.update(p.read_bytes())
        return "sha256:" + h.hexdigest()[:16]

    def validate_snapshot_dir(self, snap_dir: Path) -> list[str]:
        errors: list[str] = []
        if not snap_dir.is_dir():
            return [f"missing directory: {snap_dir}"]
        for fname in REQUIRED_SNAPSHOT_FILES:
            if not (snap_dir / fname).is_file():
                errors.append(f"missing file: {fname}")
        rules_path = snap_dir / "rules.yaml"
        if rules_path.is_file():
            try:
                rules = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                errors.append(f"rules.yaml parse error: {exc}")
                rules = {}
            cats = rules.get("categories") or {}
            if not cats:
                errors.append("rules.yaml: categories required")
            for cat_id, cat in cats.items():
                if not isinstance(cat, dict):
                    errors.append(f"invalid category: {cat_id}")
                    continue
                try:
                    rate = float(cat.get("rate", -1))
                except (TypeError, ValueError):
                    errors.append(f"invalid rate in {cat_id}")
                    continue
                if not 0 <= rate <= 1:
                    errors.append(f"rate out of range in {cat_id}: {rate}")
                applies = cat.get("appliesTo") or []
                if not applies:
                    errors.append(f"appliesTo empty in {cat_id}")
            credit = rules.get("credit") or {}
            if not credit.get("method"):
                errors.append("rules.yaml: credit.method required")
            try:
                self.repo.load_snapshot(
                    f"cn_resident_us_equity@{snap_dir.name}"
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"load_snapshot failed: {exc}")
        return errors

    def list_snapshots(self, rule_pack_id: str) -> list[SnapshotInfo]:
        base = self.pack_dir(rule_pack_id) / "snapshots"
        if not base.is_dir():
            return []
        out: list[SnapshotInfo] = []
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            meta = self.read_meta(child)
            status = str(meta.get("status") or "draft")
            if status not in VALID_STATUSES:
                status = "draft"
            sid = f"{rule_pack_id}@{child.name}"
            out.append(
                SnapshotInfo(
                    snapshot_folder=child.name,
                    snapshot_id=sid,
                    status=status,
                    effective_from=meta.get("effectiveFrom"),
                    checksum=self.snapshot_checksum(child),
                    path=child,
                )
            )
        return out

    def publish_stable(
        self,
        rule_pack_id: str,
        snapshot_folder: str,
        *,
        reviewer_id: str = "auto",
        regression_report_id: str | None = None,
    ) -> dict[str, Any]:
        snap_dir = self.snapshot_dir(rule_pack_id, snapshot_folder)
        errors = self.validate_snapshot_dir(snap_dir)
        if errors:
            raise ValueError("; ".join(errors))

        manifest = self.load_manifest(rule_pack_id)
        previous = manifest.get("latestStable")
        snapshot_id = f"{rule_pack_id}@{snapshot_folder}"

        for info in self.list_snapshots(rule_pack_id):
            if info.status == "stable" and info.snapshot_folder != snapshot_folder:
                meta = self.read_meta(info.path)
                meta["status"] = "deprecated"
                meta["deprecatedAt"] = _utc_now()
                self.write_meta(info.path, meta)

        meta = self.read_meta(snap_dir)
        meta["status"] = "stable"
        meta["publishedAt"] = _utc_now()
        meta["reviewerId"] = reviewer_id
        if regression_report_id:
            meta["regressionReportId"] = regression_report_id
        self.write_meta(snap_dir, meta)

        manifest["latestStable"] = snapshot_id
        self.save_manifest(rule_pack_id, manifest)

        log_entry = {
            "published": True,
            "rulePackId": rule_pack_id,
            "snapshotId": snapshot_id,
            "previousStable": previous,
            "checksum": self.snapshot_checksum(snap_dir),
            "publishedAt": meta["publishedAt"],
        }
        self._append_publish_log(log_entry)
        try:
            from tax_agent.rule_publish_monitor import on_publish_stable

            on_publish_stable(log_entry)
        except Exception:
            pass
        return log_entry

    def rollback_stable(self, rule_pack_id: str) -> dict[str, Any]:
        """Point latestStable to newest deprecated snapshot (emergency rollback)."""
        manifest = self.load_manifest(rule_pack_id)
        current = manifest.get("latestStable")
        candidates = [
            s
            for s in self.list_snapshots(rule_pack_id)
            if s.status == "deprecated" and s.snapshot_id != current
        ]
        if not candidates:
            raise ValueError("no deprecated snapshot to rollback to")
        target = sorted(candidates, key=lambda x: x.snapshot_folder)[-1]
        return self.publish_stable(rule_pack_id, target.snapshot_folder, reviewer_id="rollback")

    def _append_publish_log(self, entry: dict[str, Any]) -> None:
        log_dir = _repo_root() / ".data"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "rule_publish_log.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def apply_snapshot_files(
        self,
        rule_pack_id: str,
        snapshot_folder: str,
        files: dict[str, str],
        *,
        status: str = "review",
        effective_from: str | None = None,
        source: str = "feed",
    ) -> SnapshotInfo:
        snap_dir = self.snapshot_dir(rule_pack_id, snapshot_folder)
        snap_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in files.items():
            if fname not in REQUIRED_SNAPSHOT_FILES and fname not in OPTIONAL_SNAPSHOT_FILES:
                continue
            (snap_dir / fname).write_text(content, encoding="utf-8")
        errors = self.validate_snapshot_dir(snap_dir)
        if errors:
            raise ValueError("; ".join(errors))
        meta = {
            "status": status if status in VALID_STATUSES else "review",
            "effectiveFrom": effective_from,
            "syncedAt": _utc_now(),
            "source": source,
        }
        self.write_meta(snap_dir, meta)
        return SnapshotInfo(
            snapshot_folder=snapshot_folder,
            snapshot_id=f"{rule_pack_id}@{snapshot_folder}",
            status=meta["status"],
            effective_from=effective_from,
            checksum=self.snapshot_checksum(snap_dir),
            path=snap_dir,
        )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass
class RuleSnapshot:
    rule_pack_id: str
    rule_snapshot_id: str
    version: str
    categories: dict[str, Any]
    credit: dict[str, Any]
    resident_gate: dict[str, Any]
    checksum_label: str
    disclaimers: list[dict[str, str]]
    status: str = "stable"

    def rate_for_event_type(self, event_type: str) -> tuple[str, Decimal] | None:
        for cat_id, cat in self.categories.items():
            applies = cat.get("appliesTo") or []
            if event_type in applies:
                return cat_id, Decimal(str(cat.get("rate", "0.20")))
        return None


class RuleRepository:
    def __init__(self, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or (_repo_root() / "rules")

    def resolve_snapshot_id(self, rule_pack_id: str, requested: str) -> str:
        manifest = self._load_manifest(rule_pack_id)
        if requested in ("latest_stable", "latest"):
            return manifest["latestStable"]
        return requested

    def load_snapshot(self, rule_snapshot_id: str) -> RuleSnapshot:
        # cn_resident_us_equity@2026.06.01 -> snapshots/2026.06.01
        parts = rule_snapshot_id.split("@", 1)
        pack_id = parts[0]
        snap_folder = parts[1] if len(parts) == 2 else ""
        base = self.rules_dir / pack_id / "snapshots" / snap_folder
        rules = yaml.safe_load((base / "rules.yaml").read_text(encoding="utf-8"))
        disclaimers_raw = yaml.safe_load((base / "disclaimers.yaml").read_text(encoding="utf-8"))
        blocks = disclaimers_raw.get("blocks") or []
        status = "stable"
        meta_path = base / "snapshot_meta.yaml"
        if meta_path.is_file():
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            status = str(meta.get("status") or "stable")
        return RuleSnapshot(
            rule_pack_id=pack_id,
            rule_snapshot_id=rule_snapshot_id,
            version=rules.get("version", snap_folder),
            categories=rules.get("categories") or {},
            credit=rules.get("credit") or {},
            resident_gate=rules.get("residentGate") or {},
            checksum_label=f"{rule_snapshot_id}:rules.yaml",
            disclaimers=blocks,
            status=status,
        )

    def _load_manifest(self, rule_pack_id: str) -> dict[str, Any]:
        path = self.rules_dir / rule_pack_id / "manifest.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

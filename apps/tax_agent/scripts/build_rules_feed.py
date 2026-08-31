#!/usr/bin/env python3
"""
Build Tax Agent remote rules feed JSON from a rules-feed Git repo layout.

Layout:
  manifest.yaml
  snapshots/YYYY.MM.DD/{rules,fx_policy,disclaimers}.yaml
  snapshots/YYYY.MM.DD/snapshot_meta.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("rules.yaml", "fx_policy.yaml", "disclaimers.yaml")
OPTIONAL = ("fx_rates.yaml",)
DEFAULT_REPO = ROOT / "examples" / "rules-feed-repo"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def build_feed(repo_root: Path, *, include_status: tuple[str, ...] = ("review", "stable")) -> dict[str, Any]:
    manifest_path = repo_root / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    manifest = _load_yaml(manifest_path)
    pack_id = str(manifest.get("rulePackId") or "cn_resident_us_equity")

    snapshots_dir = repo_root / "snapshots"
    if not snapshots_dir.is_dir():
        raise FileNotFoundError(f"missing snapshots dir: {snapshots_dir}")

    items: list[dict[str, Any]] = []
    for child in sorted(snapshots_dir.iterdir()):
        if not child.is_dir():
            continue
        missing = [f for f in REQUIRED if not (child / f).is_file()]
        if missing:
            raise ValueError(f"{child.name}: missing {missing}")
        meta = _load_yaml(child / "snapshot_meta.yaml")
        status = str(meta.get("status") or "review")
        if status not in include_status:
            continue
        files = {name: _read_text(child / name) for name in REQUIRED}
        for name in OPTIONAL:
            if (child / name).is_file():
                files[name] = _read_text(child / name)
        items.append(
            {
                "snapshotFolder": child.name,
                "status": status,
                "effectiveFrom": meta.get("effectiveFrom"),
                "source": meta.get("source") or manifest.get("source") or "rules-feed-git",
                "changelog_zh": meta.get("changelog_zh"),
                "files": files,
            }
        )

    return {
        "rulePackId": pack_id,
        "feedVersion": manifest.get("feedVersion") or "1",
        "generatedFrom": str(repo_root),
        "snapshots": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tax Agent rules feed JSON")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="rules-feed repo root")
    parser.add_argument("--output", type=Path, default=None, help="output feed.json path")
    parser.add_argument(
        "--include-status",
        default="review,stable",
        help="comma-separated snapshot statuses to include",
    )
    args = parser.parse_args()
    include = tuple(s.strip() for s in args.include_status.split(",") if s.strip())
    feed = build_feed(args.repo.resolve(), include_status=include)
    text = json.dumps(feed, ensure_ascii=False, indent=2)
    out = args.output or (args.repo / "dist" / "feed.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(feed['snapshots'])} snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

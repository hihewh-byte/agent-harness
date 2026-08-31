#!/usr/bin/env python3
"""Thin wrapper — same logic as tax_agent/scripts/build_rules_feed.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("rules.yaml", "fx_policy.yaml", "disclaimers.yaml")
OPTIONAL = ("fx_rates.yaml",)


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def build_feed(repo_root: Path) -> dict:
    manifest = _load_yaml(repo_root / "manifest.yaml")
    pack_id = str(manifest.get("rulePackId") or "cn_resident_us_equity")
    snapshots_dir = repo_root / "snapshots"
    items = []
    for child in sorted(snapshots_dir.iterdir()):
        if not child.is_dir():
            continue
        for fname in REQUIRED:
            if not (child / fname).is_file():
                raise FileNotFoundError(f"{child.name}: missing {fname}")
        meta = _load_yaml(child / "snapshot_meta.yaml")
        status = str(meta.get("status") or "review")
        if status not in ("review", "stable"):
            continue
        items.append(
            {
                "snapshotFolder": child.name,
                "status": status,
                "effectiveFrom": meta.get("effectiveFrom"),
                "source": meta.get("source") or "rules-feed-git",
                "changelog_zh": meta.get("changelog_zh"),
                "files": {
                    fname: (child / fname).read_text(encoding="utf-8")
                    for fname in REQUIRED + OPTIONAL
                    if (child / fname).is_file()
                },
            }
        )
    return {"rulePackId": pack_id, "feedVersion": "1", "snapshots": items}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "feed.json")
    args = p.parse_args()
    feed = build_feed(REPO_ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(feed['snapshots'])} snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

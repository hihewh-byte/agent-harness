#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REQUIRED_FILES = {"rules.yaml", "fx_policy.yaml", "disclaimers.yaml"}


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/feed.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("rulePackId"), "rulePackId required"
    snaps = data.get("snapshots") or []
    assert isinstance(snaps, list), "snapshots must be list"
    for item in snaps:
        assert item.get("snapshotFolder"), "snapshotFolder required"
        files = item.get("files") or {}
        missing = REQUIRED_FILES - set(files)
        assert not missing, f"{item['snapshotFolder']}: missing {missing}"
        assert "categories:" in files["rules.yaml"], "rules.yaml invalid"
    print(f"PASS validate_feed: {len(snaps)} snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

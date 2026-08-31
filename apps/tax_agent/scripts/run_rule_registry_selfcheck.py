#!/usr/bin/env python3
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.rule_auto_updater import run_auto_update_and_record
from tax_agent.rule_registry import RuleRegistry
from tax_agent.regulation_monitor import sync_from_feed

PACK = "cn_resident_us_equity"
SNAP = "2026.06.01"


def main() -> int:
    reg = RuleRegistry()
    snaps = reg.list_snapshots(PACK)
    assert any(s.snapshot_folder == SNAP and s.status == "stable" for s in snaps)
    assert not reg.validate_snapshot_dir(reg.snapshot_dir(PACK, SNAP))
    print("PASS list + validate stable snapshot")

    rules = (reg.snapshot_dir(PACK, SNAP) / "rules.yaml").read_text(encoding="utf-8")
    fx = (reg.snapshot_dir(PACK, SNAP) / "fx_policy.yaml").read_text(encoding="utf-8")
    disc = (reg.snapshot_dir(PACK, SNAP) / "disclaimers.yaml").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        rules_root = Path(tmp) / "rules"
        shutil.copytree(ROOT / "rules" / PACK, rules_root / PACK)
        treg = RuleRegistry(rules_root)
        feed = {
            "rulePackId": PACK,
            "snapshots": [
                {
                    "snapshotFolder": "2099.12.31",
                    "status": "review",
                    "effectiveFrom": "2099-01-01",
                    "files": {
                        "rules.yaml": rules,
                        "fx_policy.yaml": fx,
                        "disclaimers.yaml": disc,
                    },
                }
            ],
        }
        applied = sync_from_feed(treg, feed=feed)
        assert applied[0]["action"] == "imported"
        assert not treg.validate_snapshot_dir(treg.snapshot_dir(PACK, "2099.12.31"))
        print("PASS feed import to review")

    dry = run_auto_update_and_record(trigger="selfcheck")
    assert isinstance(dry.get("latestStable"), str)
    assert dry.get("syncState", {}).get("updatedAt")
    print("PASS auto_update dry run:", dry.get("latestStable"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

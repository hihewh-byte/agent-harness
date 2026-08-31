#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_rules_feed import build_feed
from tax_agent.regulation_monitor import sync_from_feed

TEMPLATE = ROOT / "examples" / "rules-feed-repo"


def main() -> int:
    assert TEMPLATE.is_dir(), f"missing {TEMPLATE}"
    import subprocess

    fx_script = TEMPLATE / "scripts" / "build_fx_rates.py"
    if fx_script.is_file():
        r = subprocess.run([sys.executable, str(fx_script)], cwd=str(TEMPLATE))
        if r.returncode != 0:
            return r.returncode
        print("PASS build_fx_rates in feed repo")
    feed = build_feed(TEMPLATE)
    assert feed["rulePackId"] == "cn_resident_us_equity"
    assert len(feed["snapshots"]) >= 1
    print("PASS build_feed:", len(feed["snapshots"]), "snapshots")

    with tempfile.TemporaryDirectory() as tmp:
        rules_root = Path(tmp) / "rules"
        shutil.copytree(ROOT / "rules" / "cn_resident_us_equity", rules_root / "cn_resident_us_equity")
        from tax_agent.rule_registry import RuleRegistry

        reg = RuleRegistry(Path(tmp) / "rules")
        applied = sync_from_feed(reg, feed=feed)
        assert applied and applied[0].get("action") in ("imported", "skip_stable")
        print("PASS sync_from_feed:", applied[0].get("action"))

    out = ROOT / "examples" / "rules-feed-repo" / "dist" / "feed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

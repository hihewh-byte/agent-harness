#!/usr/bin/env python3
"""Self-check for 72h publish monitor and auto-rollback."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent import rule_publish_monitor as mon
from tax_agent.rule_registry import RuleRegistry


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "monitor.json"
        os.environ["TAX_AGENT_RULES_MONITOR_STATE"] = str(state_path)
        os.environ["TAX_AGENT_RULES_MONITOR_HOURS"] = "72"
        os.environ["TAX_AGENT_RULES_ROLLBACK_ERROR_RATE"] = "0.01"
        os.environ["TAX_AGENT_RULES_ROLLBACK_MIN_SAMPLES"] = "3"
        os.environ["TAX_AGENT_RULES_AUTO_ROLLBACK"] = "0"

        watch = mon.on_publish_stable(
            {
                "snapshotId": "cn_resident_us_equity@2099.01.01",
                "previousStable": "cn_resident_us_equity@2026.06.01",
                "publishedAt": mon._iso(mon._utc_now()),
            }
        )
        if watch is None or watch.status != "watching":
            failures.append("watch not started")

        for _ in range(2):
            mon.record_compute_outcome("cn_resident_us_equity@2099.01.01", "success")
        mon.record_compute_outcome("cn_resident_us_equity@2099.01.01", "failed")
        mon.record_compute_outcome("cn_resident_us_equity@2099.01.01", "failed")

        st = mon.get_monitor_status()
        active = st.get("activeWatches") or []
        if not active or active[0].get("total_computes") != 4:
            failures.append(f"record_compute: {active}")

        # Force window end + threshold exceeded without auto rollback
        state = mon.load_monitor_state()
        watches = mon._watches_from_state(state)
        watches[0].published_at = mon._iso(mon._utc_now() - timedelta(hours=80))
        mon._persist_watches(state, watches)
        actions = mon.evaluate_watches(RuleRegistry())
        if not any(a.get("action") == "threshold_exceeded" for a in actions):
            failures.append(f"expected threshold_exceeded, got {actions}")

        # Auto rollback path (mock by republishing with high failure rate)
        os.environ["TAX_AGENT_RULES_AUTO_ROLLBACK"] = "1"
        mon.on_publish_stable(
            {
                "snapshotId": "cn_resident_us_equity@2099.02.01",
                "previousStable": "cn_resident_us_equity@2026.06.01",
                "publishedAt": mon._iso(mon._utc_now()),
            }
        )
        for _ in range(5):
            mon.record_compute_outcome("cn_resident_us_equity@2099.02.01", "failed")
        state2 = mon.load_monitor_state()
        w2 = [w for w in mon._watches_from_state(state2) if w.snapshot_id.endswith("2099.02.01")][0]
        w2.published_at = mon._iso(mon._utc_now() - timedelta(hours=1))
        mon._persist_watches(state2, [w for w in mon._watches_from_state(state2) if w.snapshot_id != w2.snapshot_id] + [w2])
        actions2 = mon.evaluate_watches(RuleRegistry())
        if not any(a.get("action") == "auto_rollback" for a in actions2):
            failures.append(f"expected auto_rollback, got {actions2}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: rule publish monitor selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

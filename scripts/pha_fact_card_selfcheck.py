#!/usr/bin/env python3
"""Offline: fact card binds calendar day, user-selected metrics, short notify + HTML."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_PREFS = Path(tempfile.mkdtemp()) / "fact_card_prefs.json"
os.environ["PHA_FACT_CARD_PREFS"] = str(_PREFS)

from pha.fact_card import (  # noqa: E402
    DISCLAIMER,
    compose_fact_card,
    fact_card_numeric_atoms,
)
from pha.fact_card_html import render_fact_card_html  # noqa: E402
from pha.fact_card_prefs import prefs_payload, save_enabled_metric_ids  # noqa: E402
from pha.models import WearableDailySummary  # noqa: E402

DEFAULT_FIVE = (
    "steps",
    "hrv_rmssd_ms",
    "sleep_time_asleep",
    "resting_heart_rate_bpm",
    "active_energy",
)


def _row(day: date, *, steps: int | None = None, hrv: float | None = None) -> WearableDailySummary:
    return WearableDailySummary(
        user_id="selfcheck",
        day=day,
        steps=steps,
        hrv_rmssd_ms=hrv,
    )


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def _compose(calendar: date, rows, *, enabled=DEFAULT_FIVE):
    return compose_fact_card(
        calendar_day=calendar,
        rows=rows,
        user_id="selfcheck",
        enabled_metric_ids=enabled,
    )


def main() -> int:
    calendar = date(2026, 9, 6)
    yesterday = date(2026, 9, 5)
    hist = [
        _row(yesterday - timedelta(days=i), steps=8000 + i * 10, hrv=40.0 + i)
        for i in range(1, 20)
    ]
    y_row = _row(yesterday, steps=14872, hrv=33.0)

    empty = _compose(calendar, [])
    if empty["facts"]["as_of"] is not None or empty["facts"]["today"]["steps"] is not None:
        return _fail("empty ledger must not invent as_of or today steps")
    if "14872" in empty["notification"]["body"]:
        return _fail("empty card leaked a number")
    if not empty["notification"].get("open_path", "").startswith("/proactive/fact-card/view"):
        return _fail("notification must point at the HTML view")

    stale = _compose(calendar, hist + [y_row])
    if stale["facts"]["stale"] is not True:
        return _fail("calendar after MAX(day) must be stale")
    if stale["facts"]["today"]["steps"] is not None or stale["facts"]["today"]["present"]:
        return _fail("today must stay empty when the point-day row is missing")
    if stale["facts"]["as_of"] != "2026-09-05":
        return _fail("as_of must be MAX(day), not calendar day")
    steps_m = next(m for m in stale["facts"]["metrics"] if m["metric"] == "steps")
    if steps_m["value"] != 14872 or steps_m["day"] != "2026-09-05":
        return _fail("as_of steps must come from MAX(day) row")
    if "今日" in stale["notification"]["body"] and "非今日" not in stale["notification"]["body"]:
        return _fail("stale notification must not claim 今日")
    if DISCLAIMER not in stale["notification"]["body"]:
        return _fail("notification missing disclaimer")
    labels = [m["label"] for m in stale["facts"]["metrics"]]
    for label in ("步数", "HRV", "睡眠", "静息心率", "活动消耗"):
        if not any(label in item for item in labels):
            return _fail(f"JSON metrics must include {label}")
    missing = [m for m in stale["facts"]["metrics"] if m["value"] is None]
    if len(missing) != 3:
        return _fail(f"expected 3 missing metrics, got {missing}")
    if "评估：" in stale["notification"]["body"] and "2/5有数" not in stale["notification"]["body"]:
        return _fail("teaser should stay short and show coverage")
    if "睡眠无" in stale["notification"]["body"]:
        return _fail("lock-screen body must not dump the five-metric list")
    if "2/5有数" not in stale["notification"]["body"]:
        return _fail("teaser must show coverage 2/5")
    summary = stale["assessment"].get("summary") or {}
    if summary.get("coverage_present") != 2 or summary.get("coverage_total") != 5:
        return _fail(f"coverage must be 2/5 on this fixture, got {summary}")

    fresh = _compose(yesterday, hist + [y_row])
    if fresh["facts"]["stale"] is not False:
        return _fail("as_of == calendar must not be stale")
    if fresh["facts"]["today"]["steps"] != 14872:
        return _fail("today.steps must bind the point-day row")

    body = stale["notification"]["body"]
    if "2026-09-05" not in body:
        return _fail("stale notification must cite as_of day")
    atoms = fact_card_numeric_atoms(stale)
    leaked = {
        n
        for n in re.findall(r"\d+(?:\.\d+)?", body)
        if float(n) >= 100 and n not in atoms and n not in {"2026"}
    }
    if leaked:
        return _fail(f"notification numbers not in card atoms: {leaked}")

    if any("诊断" in a["text"] or "处方" in a["text"] for a in stale["assessment"]["advice"]):
        return _fail("assessment used diagnostic/prescriptive copy")

    only_steps = _compose(calendar, hist + [y_row], enabled=["steps", "not_a_metric"])
    if [m["metric"] for m in only_steps["facts"]["metrics"]] != ["steps"]:
        return _fail("unknown metric ids must be dropped; only user-selected catalog ids remain")
    if only_steps["assessment"]["summary"]["coverage_total"] != 1:
        return _fail("coverage_total must follow the user selection, not a hardcoded five")

    html = render_fact_card_html(stale, prefs=prefs_payload("selfcheck"), token=None)
    for needle in ("步数", "14872", "睡眠", "评估", "我要看哪些指标"):
        if needle not in html:
            return _fail(f"HTML view missing {needle}")
    if "诊断" in html or "处方" in html:
        return _fail("HTML used diagnostic/prescriptive copy")

    saved = save_enabled_metric_ids("selfcheck", ["steps", "spo2_percent"])
    if saved != ["steps", "spo2_percent"]:
        return _fail(f"prefs save should keep catalog order of the request, got {saved}")
    from_prefs = compose_fact_card(
        calendar_day=calendar,
        rows=hist + [y_row],
        user_id="selfcheck",
    )
    if [m["metric"] for m in from_prefs["facts"]["metrics"]] != ["steps", "spo2_percent"]:
        return _fail("compose without explicit ids must read user prefs")
    spo2 = next(m for m in from_prefs["facts"]["metrics"] if m["metric"] == "spo2_percent")
    if spo2["value"] is not None:
        return _fail("uningested selected metric must stay 无, not invented")

    print("pha_fact_card_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

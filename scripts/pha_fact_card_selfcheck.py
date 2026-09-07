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
from pha.fact_card_prefs import (  # noqa: E402
    load_enabled_metric_ids,
    prefs_payload,
    save_enabled_metric_ids,
)
from pha.healthkit_sync_plan import shortcut_sleep_specs, shortcut_sync_specs  # noqa: E402
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
    for needle in ("步数", "14872", "睡眠", "评估", "我要看哪些指标", "健康 App"):
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

    save_enabled_metric_ids("selfcheck", ["steps", "active_energy", "hrv_rmssd_ms"])
    plan = shortcut_sync_specs("selfcheck")
    plan_ids = [s.metric_id for s in plan]
    if set(plan_ids) != {"steps", "active_energy", "hrv_sdnn_ms"}:
        return _fail(f"sync plan must be selected ∩ quantity types, got {plan_ids}")
    if plan_ids[0] != "active_energy":
        return _fail(f"Sum metrics must POST before Average, got {plan_ids}")
    energy = next(s for s in plan if s.metric_id == "active_energy")
    if energy.health_type != "Active Calories":
        return _fail(
            "active_energy Find label must be Active Calories, not Active Energy"
        )
    hrv_plan = [s for s in plan if s.health_type == "Heart Rate Variability"]
    if len(hrv_plan) != 1 or hrv_plan[0].ingest_key != "hrv_sdnn":
        return _fail("selected RMSSD must pull SDNN shortcut, not ingest_key=hrv")
    if any(s.ingest_key == "hrv" for s in plan):
        return _fail("HRV SDNN must not POST as warehouse RMSSD")

    save_enabled_metric_ids("selfcheck", ["hrv_rmssd_ms"])
    sdnn_row = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        hrv_sdnn_ms=41.2,
    )
    sdnn_card = compose_fact_card(
        calendar_day=yesterday,
        rows=[sdnn_row],
        user_id="selfcheck",
        enabled_metric_ids=["hrv_rmssd_ms"],
    )
    hrv_m = next(m for m in sdnn_card["facts"]["metrics"] if m["metric"] == "hrv_rmssd_ms")
    if hrv_m["value"] != 41.2 or hrv_m.get("value_field") != "hrv_sdnn_ms":
        return _fail(f"empty RMSSD must display SDNN fallback, got {hrv_m}")
    if hrv_m["label"] != "HRV (SDNN)":
        return _fail(f"fallback label must say SDNN, got {hrv_m['label']}")

    save_enabled_metric_ids("selfcheck", ["sleep_time_asleep", "steps"])
    qty = shortcut_sync_specs("selfcheck")
    if any(s.health_type == "Sleep" for s in qty):
        return _fail("quantity shortcut must not Find Sleep")
    sleep_plan = shortcut_sleep_specs("selfcheck")
    sleep_values = [s.unit_health for s in sleep_plan]
    if sleep_values != ["In Bed", "Asleep Core", "Asleep Deep", "Asleep REM", "Awake"]:
        return _fail(f"sleep stages must be ActionKit sleep values, got {sleep_values}")
    if any(s.ingest_key == "sleep_hours" for s in sleep_plan):
        return _fail("do not POST derived sleep_hours")

    awake_hist = [
        WearableDailySummary(
            user_id="selfcheck",
            day=yesterday - timedelta(days=i),
            awake_duration_hours=1.0,
        )
        for i in range(1, 21)
    ]
    high_awake = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        awake_duration_hours=3.58,
    )
    high_card = compose_fact_card(
        calendar_day=yesterday,
        rows=awake_hist + [high_awake],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_awake"],
    )
    advice = " ".join(a["text"] for a in high_card["assessment"]["advice"])
    if "请到健康 App 核对这一夜的数据" not in advice:
        return _fail(f"high awake must add verify copy, got {advice}")
    if "明显高于" not in advice or "3.6h" not in advice:
        return _fail(f"verify copy must keep the number and 高于, got {advice}")
    if "请到健康 App 核对" not in high_card["notification"]["body"]:
        return _fail("notification must include the verify sentence")
    for word in ("错误", "异常", "采集失误"):
        if word in advice or word in high_card["notification"]["body"]:
            return _fail(f"verify copy must not judge with {word}")

    typical_hist = [
        WearableDailySummary(
            user_id="selfcheck",
            day=yesterday - timedelta(days=i),
            awake_duration_hours=1.0 if i <= 10 else 4.0,
        )
        for i in range(1, 21)
    ]
    typical_row = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        awake_duration_hours=2.0,
    )
    typical_card = compose_fact_card(
        calendar_day=yesterday,
        rows=typical_hist + [typical_row],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_awake"],
    )
    typical_advice = " ".join(a["text"] for a in typical_card["assessment"]["advice"])
    if "请到健康 App 核对" in typical_advice:
        return _fail("in-band awake must not add verify copy")

    short_hist = [
        WearableDailySummary(
            user_id="selfcheck",
            day=yesterday - timedelta(days=i),
            awake_duration_hours=1.0,
        )
        for i in range(1, 5)
    ]
    short_card = compose_fact_card(
        calendar_day=yesterday,
        rows=short_hist + [high_awake],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_awake"],
    )
    short_m = next(m for m in short_card["facts"]["metrics"] if m["metric"] == "sleep_awake")
    if short_m["band"] != "unknown":
        return _fail(f"n<7 must not band, got {short_m}")
    short_advice = " ".join(a["text"] for a in short_card["assessment"]["advice"])
    if "请到健康 App 核对" in short_advice:
        return _fail("n<7 must not remind")

    leftover_bed = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        in_bed_hours=0.728,
    )
    leftover_card = compose_fact_card(
        calendar_day=yesterday,
        rows=[leftover_bed],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_in_bed"],
    )
    bed_m = next(m for m in leftover_card["facts"]["metrics"] if m["metric"] == "sleep_in_bed")
    if bed_m["value"] is not None:
        return _fail(f"in_bed<1h without stages must display 无, got {bed_m}")
    leftover_html = render_fact_card_html(
        leftover_card, prefs=prefs_payload("selfcheck"), token=None
    )
    if ">无<" not in leftover_html:
        return _fail("HTML must show 无 for leftover in_bed")

    # M1-P7: progressive baseline 90d empty → 365d hit
    as_of = yesterday
    far_hist = [
        WearableDailySummary(
            user_id="selfcheck",
            day=as_of - timedelta(days=120 + i),
            sleep_hours=7.0 + (i % 5) * 0.1,
        )
        for i in range(30)
    ]
    as_of_sleep = WearableDailySummary(
        user_id="selfcheck",
        day=as_of,
        sleep_hours=7.5,
    )
    prog = compose_fact_card(
        calendar_day=as_of,
        rows=far_hist + [as_of_sleep],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_time_asleep"],
    )
    sleep_m = next(m for m in prog["facts"]["metrics"] if m["metric"] == "sleep_time_asleep")
    if sleep_m.get("baseline_window") != "365d":
        return _fail(f"90d-empty sleep must use 365d window, got {sleep_m}")
    if sleep_m.get("band") == "unknown":
        return _fail("365d with 30 nights must band")
    blob = json_blob(prog)
    if "近90日" in blob or "近 90 日个人" in blob:
        return _fail("copy must not hardcode 近90日 as the only baseline")
    if sleep_m.get("reference") is None or sleep_m["reference"].get("status") not in {
        "within",
        "below",
        "above",
    }:
        return _fail(f"sleep must carry reference status, got {sleep_m.get('reference')}")
    ref_text = str(sleep_m["reference"].get("text") or "")
    if not ref_text.startswith("【参考标准】") or "请自行查证" not in ref_text:
        return _fail(f"reference must be T1 disclosure, got {ref_text}")
    atoms = fact_card_numeric_atoms(prog)
    for needle in ("7", "9"):
        if needle not in atoms:
            return _fail(f"reference {needle} must be in numeric atoms, got {atoms}")

    empty_hist = compose_fact_card(
        calendar_day=as_of,
        rows=[as_of_sleep],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_time_asleep"],
    )
    empty_m = next(m for m in empty_hist["facts"]["metrics"] if m["metric"] == "sleep_time_asleep")
    if empty_m.get("band") != "unknown" or empty_m.get("baseline_window") is not None:
        return _fail(f"no history must be unknown without window, got {empty_m}")
    empty_advice = " ".join(a["text"] for a in empty_hist["assessment"]["advice"])
    if "0/7" not in empty_advice and "无历史" not in empty_advice:
        return _fail(f"short history copy must show progress, got {empty_advice}")

    hrv_only = compose_fact_card(
        calendar_day=as_of,
        rows=[
            WearableDailySummary(user_id="selfcheck", day=as_of, hrv_sdnn_ms=40.0),
            *[
                WearableDailySummary(
                    user_id="selfcheck",
                    day=as_of - timedelta(days=i),
                    hrv_sdnn_ms=40.0 + i,
                )
                for i in range(1, 20)
            ],
        ],
        user_id="selfcheck",
        enabled_metric_ids=["hrv_sdnn_ms"],
    )
    hrv_m2 = next(m for m in hrv_only["facts"]["metrics"] if m["metric"] == "hrv_sdnn_ms")
    if hrv_m2.get("reference") is not None:
        return _fail("HRV must not get a population reference_range")

    # composite requires sleep + HRV + RHR all selected and banded
    composite_rows = [
        WearableDailySummary(
            user_id="selfcheck",
            day=as_of - timedelta(days=i),
            sleep_hours=7.2,
            hrv_sdnn_ms=42.0,
            resting_heart_rate_bpm=62.0,
        )
        for i in range(1, 20)
    ] + [
        WearableDailySummary(
            user_id="selfcheck",
            day=as_of,
            sleep_hours=7.2,
            hrv_sdnn_ms=42.0,
            resting_heart_rate_bpm=62.0,
        )
    ]
    full_comp = compose_fact_card(
        calendar_day=as_of,
        rows=composite_rows,
        user_id="selfcheck",
        enabled_metric_ids=[
            "sleep_time_asleep",
            "hrv_sdnn_ms",
            "resting_heart_rate_bpm",
        ],
    )
    if full_comp["assessment"]["summary"].get("composite") not in {"持平", "偏好", "偏轻松"}:
        return _fail(
            f"full composite must vote, got {full_comp['assessment']['summary']}"
        )
    missing_comp = compose_fact_card(
        calendar_day=as_of,
        rows=composite_rows,
        user_id="selfcheck",
        enabled_metric_ids=["sleep_time_asleep", "steps"],
    )
    if missing_comp["assessment"]["summary"].get("composite") != "不综合":
        return _fail("missing HRV/RHR selection must 不综合")

    print("pha_fact_card_selfcheck: PASS")
    return 0


def json_blob(card: dict) -> str:
    import json

    return json.dumps(card, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())

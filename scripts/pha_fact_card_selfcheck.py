#!/usr/bin/env python3
"""Offline: fact card binds calendar day, user-selected metrics, short notify + HTML."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_TMP = Path(tempfile.mkdtemp())
_PREFS = _TMP / "fact_card_prefs.json"
_INTERPRET = _TMP / "fact_card_interpret"
os.environ["PHA_FACT_CARD_PREFS"] = str(_PREFS)
os.environ["PHA_FACT_CARD_INTERPRET_DIR"] = str(_INTERPRET)
os.environ.setdefault("OLLAMA_MODEL", "selfcheck-model")

from pha.fact_card import (  # noqa: E402
    DISCLAIMER,
    compose_fact_card,
    fact_card_numeric_atoms,
)
from pha.fact_card_html import render_fact_card_html  # noqa: E402
from pha.fact_card_interpret import (  # noqa: E402
    current_interpret_key,
    load_interpretation_for_user,
    run_interpretation,
    start_interpretation,
)
from pha.fact_card_prefs import (  # noqa: E402
    load_assessment_prompt,
    load_enabled_metric_ids,
    prefs_payload,
    save_assessment_prompt,
    save_enabled_metric_ids,
    save_fact_card_locale,
)
from pha.healthkit_sync_plan import shortcut_sleep_specs, shortcut_sync_specs  # noqa: E402
from pha.models import WearableDailySummary  # noqa: E402

DEFAULT_FIVE = (
    "steps",
    "hrv_sdnn_ms",
    "sleep_time_asleep",
    "resting_heart_rate_bpm",
    "active_energy",
)


def _row(day: date, *, steps: int | None = None, hrv: float | None = None) -> WearableDailySummary:
    return WearableDailySummary(
        user_id="selfcheck",
        day=day,
        steps=steps,
        hrv_sdnn_ms=hrv,
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
    save_fact_card_locale("selfcheck", "zh-CN")
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
    if steps_m["value"] is not None:
        return _fail("accrual must not fill calendar_day from MAX(day)")
    hrv_stale = next(m for m in stale["facts"]["metrics"] if m["metric"] == "hrv_sdnn_ms")
    if hrv_stale["value"] != 33.0 or hrv_stale.get("freshness") != "prior_day":
        return _fail(f"overnight HRV should keep as_of row as prior_day, got {hrv_stale}")
    if "今日" in stale["notification"]["body"] and "非今日" not in stale["notification"]["body"]:
        return _fail("stale notification must not claim 今日")
    if DISCLAIMER not in stale["notification"]["body"]:
        return _fail("notification missing disclaimer")
    labels = [m["label"] for m in stale["facts"]["metrics"]]
    for label in ("步数", "HRV", "睡眠", "静息心率", "活动消耗"):
        if not any(label in item for item in labels):
            return _fail(f"JSON metrics must include {label}")
    missing = [m for m in stale["facts"]["metrics"] if m["value"] is None]
    if len(missing) != 4:
        return _fail(f"expected 4 missing metrics (accrual empty on calendar day), got {missing}")
    if "评估：" in stale["notification"]["body"] and "1/5有数" not in stale["notification"]["body"]:
        return _fail("teaser should stay short and show coverage")
    if "睡眠无" in stale["notification"]["body"]:
        return _fail("lock-screen body must not dump the five-metric list")
    if "1/5有数" not in stale["notification"]["body"]:
        return _fail("teaser must show coverage 1/5")
    if "前一日" not in stale["notification"]["body"]:
        return _fail("teaser must count prior_day rows")
    summary = stale["assessment"].get("summary") or {}
    if summary.get("coverage_present") != 1 or summary.get("coverage_total") != 5:
        return _fail(f"coverage must be 1/5 on this fixture, got {summary}")

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
    for needle in ("步数", "睡眠", "评估", "我要看哪些指标", "健康 App", "改勾选后刷新即可", "呼吸与血氧", "体能"):
        if needle not in html:
            return _fail(f"HTML view missing {needle}")
    if "改勾选后请在 Mac 重新生成捷径" in html:
        return _fail("HTML must not ask to regenerate shortcuts after a prefs change")
    if "诊断" in html or "处方" in html:
        return _fail("HTML used diagnostic/prescriptive copy")
    fresh_html = render_fact_card_html(
        _compose(yesterday, hist + [y_row], enabled=["steps"]),
        prefs=prefs_payload("selfcheck"),
        token=None,
    )
    if "14872" not in fresh_html:
        return _fail("HTML missing point-day steps")

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

    save_enabled_metric_ids("selfcheck", ["steps", "active_energy", "hrv_sdnn_ms"])
    plan = shortcut_sync_specs("selfcheck")
    plan_ids = [s.metric_id for s in plan]
    universe = {
        "steps",
        "active_energy",
        "hrv_sdnn_ms",
        "resting_heart_rate_bpm",
        "spo2_percent",
        "respiratory_rate",
        "vo2max",
    }
    if set(plan_ids) != universe:
        return _fail(f"sync plan must be registry quantity universe, got {plan_ids}")
    before_prefs = plan_ids[:]
    save_enabled_metric_ids("selfcheck", ["sleep_time_asleep"])
    after_prefs = [s.metric_id for s in shortcut_sync_specs("selfcheck")]
    if after_prefs != before_prefs:
        return _fail("sync plan must ignore prefs")
    if plan_ids[0] != "active_energy":
        return _fail(f"Sum metrics must POST before Average, got {plan_ids}")
    energy = next(s for s in plan if s.metric_id == "active_energy")
    if energy.health_type != "Active Calories":
        return _fail(
            "active_energy Find label must be Active Calories, not Active Energy"
        )
    hrv_plan = [s for s in plan if s.health_type == "Heart Rate Variability"]
    if len(hrv_plan) != 1 or hrv_plan[0].ingest_key != "hrv_sdnn":
        return _fail("HRV shortcut must POST ingest_key=hrv_sdnn")
    if any(s.ingest_key == "hrv" for s in plan):
        return _fail("HRV must not POST as warehouse legacy hrv/RMSSD key")
    if any(s.metric_id == "wrist_temp" for s in plan):
        return _fail("wrist_temp must stay skipped until Find catalog is device_verified")
    wrist_row = next(r for r in prefs_payload("selfcheck")["catalog"] if r["metric_id"] == "wrist_temp")
    if wrist_row.get("shortcut_sync"):
        return _fail("wrist_temp catalog must not claim quantity shortcut sync")
    if wrist_row.get("shortcut_skip_reason") != "shortcuts_find_unverified":
        return _fail(f"wrist_temp skip reason, got {wrist_row}")

    # Prefs migration: old RMSSD id remaps to SDNN
    save_enabled_metric_ids("selfcheck", ["hrv_rmssd_ms"])
    remapped, _src = load_enabled_metric_ids("selfcheck")
    if remapped != ["hrv_sdnn_ms"]:
        return _fail(f"hrv_rmssd prefs must remap to hrv_sdnn, got {remapped}")
    sdnn_row = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        hrv_sdnn_ms=41.2,
    )
    sdnn_card = compose_fact_card(
        calendar_day=yesterday,
        rows=[sdnn_row],
        user_id="selfcheck",
        enabled_metric_ids=["hrv_sdnn_ms"],
    )
    hrv_m = next(m for m in sdnn_card["facts"]["metrics"] if m["metric"] == "hrv_sdnn_ms")
    if hrv_m["value"] != 41.2 or hrv_m.get("value_field") != "hrv_sdnn_ms":
        return _fail(f"HRV must read SDNN column, got {hrv_m}")
    if hrv_m["label"] != "HRV":
        return _fail(f"primary HRV label must be HRV, got {hrv_m['label']}")

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

    catalog = prefs_payload("selfcheck")["catalog"]
    asleep_row = next(r for r in catalog if r["metric_id"] == "sleep_time_asleep")
    if asleep_row.get("shortcut_hint") != "由睡眠捷径同步":
        return _fail(f"sleep_time_asleep hint must be sleep-channel, got {asleep_row}")
    deep_only = compose_fact_card(
        calendar_day=yesterday,
        rows=hist + [y_row],
        user_id="selfcheck",
        enabled_metric_ids=["sleep_deep"],
    )
    deep_ids = [m["metric"] for m in deep_only["facts"]["metrics"]]
    if deep_ids != ["sleep_deep"]:
        return _fail(f"selecting deep must not reveal other stages, got {deep_ids}")
    five = [
        "sleep_time_asleep",
        "hrv_sdnn_ms",
        "resting_heart_rate_bpm",
        "sleep_deep",
        "active_energy",
    ]
    five_card = compose_fact_card(
        calendar_day=yesterday,
        rows=hist + [y_row],
        user_id="selfcheck",
        enabled_metric_ids=five,
    )
    if [m["metric"] for m in five_card["facts"]["metrics"]] != five:
        return _fail("card metrics must equal selection order")
    if five_card["assessment"]["summary"]["coverage_total"] != 5:
        return _fail("coverage_total must be the selection size")
    vo2_day = yesterday - timedelta(days=40)
    vo2_row = WearableDailySummary(
        user_id="selfcheck",
        day=vo2_day,
        vo2max_ml_kg_min=44.0,
    )
    vo2_card = compose_fact_card(
        calendar_day=calendar,
        rows=[vo2_row],
        user_id="selfcheck",
        enabled_metric_ids=["steps", "vo2max"],
    )
    vo2_m = next(m for m in vo2_card["facts"]["metrics"] if m["metric"] == "vo2max")
    if vo2_m["value"] != 44.0 or vo2_m.get("counts_for_coverage") is not False:
        return _fail(f"VO2max latest must show last reading and skip coverage, got {vo2_m}")
    if vo2_card["assessment"]["summary"]["coverage_total"] != 1:
        return _fail("VO2max must not inflate coverage_total")
    blob = json_blob(five_card)
    if "sleep_rem" in blob or "sleep_core" in blob or "sleep_in_bed" in blob:
        return _fail("unselected stages must not appear on the card")

    rhr_d1 = WearableDailySummary(
        user_id="selfcheck",
        day=yesterday,
        resting_heart_rate_bpm=60,
    )
    rhr_card = compose_fact_card(
        calendar_day=calendar,
        rows=[rhr_d1],
        user_id="selfcheck",
        enabled_metric_ids=["resting_heart_rate_bpm"],
    )
    rhr_m = rhr_card["facts"]["metrics"][0]
    if rhr_m["value"] != 60 or rhr_m.get("freshness") != "prior_day" or rhr_m["day"] != "2026-09-05":
        return _fail(f"RHR should take D-1 within freshness_days, got {rhr_m}")
    if rhr_m.get("band") not in {"below", "typical", "above", "unknown"}:
        return _fail(f"prior_day RHR must still band, got {rhr_m}")
    if "今日" in (rhr_card["assessment"]["advice"][0]["text"] or ""):
        return _fail("prior_day copy must not say 今日")
    rhr_old = WearableDailySummary(
        user_id="selfcheck",
        day=calendar - timedelta(days=3),
        resting_heart_rate_bpm=58,
    )
    rhr_stale = compose_fact_card(
        calendar_day=calendar,
        rows=[rhr_old],
        user_id="selfcheck",
        enabled_metric_ids=["resting_heart_rate_bpm"],
    )
    if rhr_stale["facts"]["metrics"][0]["value"] is not None:
        return _fail("RHR older than freshness_days must stay empty")

    energy_today = WearableDailySummary(
        user_id="selfcheck",
        day=calendar,
        active_energy_kcal=13.5,
        steps=400,
    )
    energy_hist = [
        WearableDailySummary(
            user_id="selfcheck",
            day=calendar - timedelta(days=i),
            active_energy_kcal=500 + i,
            steps=8000 + i,
        )
        for i in range(1, 20)
    ]
    clock = datetime(2026, 9, 6, 8, 0, 0)
    partial = compose_fact_card(
        calendar_day=calendar,
        rows=energy_hist + [energy_today],
        user_id="selfcheck",
        enabled_metric_ids=["active_energy", "steps"],
        now=clock,
    )
    energy_m = next(m for m in partial["facts"]["metrics"] if m["metric"] == "active_energy")
    if not energy_m.get("partial_day") or energy_m.get("band") != "pending":
        return _fail(f"same-day accrual must be pending, got {energy_m}")
    if energy_m.get("as_of_time") != "08:00":
        return _fail(f"partial as_of_time, got {energy_m}")
    if "截至" not in (partial["assessment"]["advice"][0]["text"] or ""):
        return _fail("partial advice must say 截至")
    if "进行中" not in partial["notification"]["body"]:
        return _fail("notification must count in-progress accrual")

    roll_rows = [
        WearableDailySummary(user_id="selfcheck", day=calendar - timedelta(days=i), steps=1000 * (i + 1))
        for i in range(0, 5)
    ]
    from pha.fact_card_prefs import catalog_by_id
    from pha.fact_card import _metric_row

    steps_spec = catalog_by_id()["steps"]
    # rolling_mean is not on steps; exercise the picker via a synthetic spec
    from dataclasses import replace

    rolling_spec = replace(steps_spec, temporal={"kind": "rolling_mean", "window_days": 7})
    rolled = _metric_row(
        rolling_spec,
        calendar,
        calendar,
        roll_rows[0],
        roll_rows,
        by_day={r.day: r for r in roll_rows},
        clock=clock,
    )
    if rolled.get("n_days") != 5 or rolled["value"] is None:
        return _fail(f"rolling_mean should average 5 days, got {rolled}")

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

    # --- M1-P9: assessment_prompt + button interpret (mocked chat stream) ---
    import json
    import time

    save_assessment_prompt("selfcheck", "重点看睡眠，语气平实")
    if load_assessment_prompt("selfcheck") != "重点看睡眠，语气平实":
        return _fail("assessment_prompt not persisted")
    prefs_p9 = prefs_payload("selfcheck")
    if prefs_p9.get("assessment_prompt") != "重点看睡眠，语气平实":
        return _fail("prefs_payload missing assessment_prompt")
    try:
        save_assessment_prompt("selfcheck", "x" * 2001)
        return _fail("assessment_prompt over 2000 must raise")
    except ValueError:
        pass

    p9_card = compose_fact_card(
        calendar_day=yesterday,
        rows=hist + [y_row],
        user_id="selfcheck",
        enabled_metric_ids=["steps"],
    )
    if load_interpretation_for_user("selfcheck", card=p9_card) is not None:
        return _fail("no button → interpretation must be None")
    if "interpretation" in (p9_card.get("assessment") or {}):
        return _fail("interpretation must not live under assessment")
    notify_blob = json.dumps(p9_card.get("notification") or {}, ensure_ascii=False)
    if "AI 解读" in notify_blob or "生成解读" in notify_blob:
        return _fail("notification must not mention LLM interpret")

    html_p9 = render_fact_card_html(
        {**p9_card, "interpretation": None},
        prefs=prefs_payload("selfcheck"),
        token="tok",
    )
    if "我的评估要求" not in html_p9 or "assessment_prompt" not in html_p9:
        return _fail("HTML missing assessment_prompt form")
    if "重点看睡眠，语气平实" not in html_p9:
        return _fail("HTML must echo assessment_prompt")
    if "AI 解读（实验）" not in html_p9 or "生成解读" not in html_p9:
        return _fail("HTML missing interpret block")
    if "解读只能引用卡上的数字" not in html_p9:
        return _fail("HTML missing T1-only assessment help")

    atoms = fact_card_numeric_atoms(p9_card)
    steps_m = next(m for m in p9_card["facts"]["metrics"] if m["metric"] == "steps")
    sample_atom = str(int(steps_m["value"]))
    if sample_atom not in atoms:
        return _fail(f"steps value {sample_atom} missing from atoms {sorted(atoms)[:20]}")
    ref = steps_m.get("reference") or {}
    low_s = str(int(ref["low"])) if ref.get("low") is not None else sample_atom
    high_s = str(int(ref["high"])) if ref.get("high") is not None else sample_atom

    def _stream_ok(**_kwargs):
        text = (
            f"今日步数约 {sample_atom}。"
            f"【参考标准】成人常见建议 {low_s}–{high_s} 步"
            "（来源：CDC，请自行查证，非医疗建议）"
        )
        yield json.dumps(
            {
                "event": "done",
                "model": "selfcheck-model",
                "answer": {"answer_text": text},
                "numerics_audit": {"passed": True, "violations": []},
            },
            ensure_ascii=False,
        )

    def _stream_foreign(**_kwargs):
        yield json.dumps(
            {
                "event": "done",
                "model": "selfcheck-model",
                "answer": {"answer_text": "你的风险指数是 99999。"},
                "numerics_audit": {"passed": True, "violations": []},
            },
            ensure_ascii=False,
        )

    def _stream_boom(**_kwargs):
        raise RuntimeError("ollama down")

    bad = run_interpretation(
        user_id="selfcheck",
        card=p9_card,
        assessment_prompt="重点看睡眠",
        model="selfcheck-model",
        stream_fn=_stream_foreign,
    )
    if bad.get("status") != "failed" or bad.get("error") != "audit_rejected":
        return _fail(f"foreign number must audit_rejected, got {bad}")

    ok = run_interpretation(
        user_id="selfcheck",
        card=p9_card,
        assessment_prompt="重点看睡眠",
        model="selfcheck-model",
        stream_fn=_stream_ok,
    )
    if ok.get("status") != "done" or not ok.get("text"):
        return _fail(f"T1 OK must done, got {ok}")

    boom = run_interpretation(
        user_id="selfcheck",
        card=p9_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_stream_boom,
    )
    if boom.get("status") != "failed" or boom.get("error") != "model_unavailable":
        return _fail(f"exception must model_unavailable, got {boom}")

    calls: list[int] = []

    def _stream_count(**_kwargs):
        calls.append(1)
        text = f"步数 {sample_atom}，非医疗建议。"
        yield json.dumps(
            {
                "event": "done",
                "model": "selfcheck-model",
                "answer": {"answer_text": text},
                "numerics_audit": {"passed": True, "violations": []},
            },
            ensure_ascii=False,
        )

    first = start_interpretation(
        "selfcheck", card=p9_card, stream_fn=_stream_count
    )
    if first.get("status") not in {"pending", "done"}:
        return _fail(f"first interpret start unexpected {first}")
    deadline = time.time() + 5
    got = first
    while time.time() < deadline:
        got = load_interpretation_for_user("selfcheck", card=p9_card) or got
        if got.get("status") in {"done", "failed"}:
            break
        time.sleep(0.05)
    if got.get("status") != "done":
        return _fail(f"async interpret did not finish: {got}")
    if len(calls) != 1:
        return _fail(f"expected one stream call, got {len(calls)}")
    second = start_interpretation(
        "selfcheck", card=p9_card, stream_fn=_stream_count
    )
    if second.get("started") is not False:
        return _fail("same-key POST must not start again")
    if len(calls) != 1:
        return _fail("cache hit must not call stream again")

    # --- M1-P9.1: date-normalized audit, T1-only extras, cache digest ---
    from pha.harness_plan import build_turn_evidence_plan, resolve_profile_override
    from pha.numerics_manifest import build_fact_card_numerics_manifest

    p91_card = {
        "user_id": "selfcheck",
        "facts": {
            "as_of": "2026-09-07",
            "calendar_day": "2026-09-07",
            "stale": False,
            "metrics": [
                {
                    "metric": "sleep_time_asleep",
                    "label": "睡眠总时长",
                    "value": 7.6,
                    "unit": "h",
                    "day": "2026-09-07",
                    "baseline_window": "365d",
                    "baseline_n": 267,
                    "baseline_mean": 7.2,
                    "baseline_min": 5.0,
                    "baseline_max": 9.1,
                    "percentile": 40.0,
                    "baseline_earliest": "2025-09-08",
                },
                {
                    "metric": "resting_heart_rate_bpm",
                    "label": "静息心率",
                    "value": 62,
                    "unit": "bpm",
                    "day": "2026-09-06",
                    "baseline_window": "365d",
                    "baseline_n": 200,
                    "baseline_mean": 61.0,
                    "reference": {
                        "low": 60,
                        "high": 100,
                        "unit": "bpm",
                        "source": "AHA",
                    },
                },
            ],
        },
        "assessment": {"summary": {"text": "已选2项"}, "advice": "持平"},
    }

    def _done(text, *, passed=True, violations=None):
        def _stream(**_kwargs):
            yield json.dumps(
                {
                    "event": "done",
                    "model": "selfcheck-model",
                    "answer": {"answer_text": text},
                    "numerics_audit": {
                        "passed": passed,
                        "violations": list(violations or []),
                    },
                },
                ensure_ascii=False,
            )

        return _stream

    near90 = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("近 90 天睡眠均值 7.6h，基线 267 夜。"),
    )
    near90_v = near90.get("violations") or []
    if near90.get("status") != "failed" or not (
        "unauthorized_window:90" in near90_v or "unauthorized_value:90" in near90_v
    ):
        return _fail(f"365d card must reject 90, got {near90}")

    foreign_date = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("2026-06-10 的睡眠 7.6h。"),
    )
    if foreign_date.get("status") != "failed" or "unauthorized_date:2026-06-10" not in (
        foreign_date.get("violations") or []
    ):
        return _fail(f"must reject off-card date, got {foreign_date}")

    cn_ok = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("2026年9月7日睡眠 7.6h，近 12 个月 267 夜。"),
    )
    if cn_ok.get("status") != "done":
        return _fail(f"CN as_of + card numbers must done, got {cn_ok}")

    t1_ref = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done(
            "静息心率 62。"
            "【参考标准】成人常见静息心率 60–100 bpm"
            "（来源：American Heart Association，请自行查证，非医疗建议）"
        ),
    )
    if t1_ref.get("status") != "done":
        return _fail(f"T1 reference range must done, got {t1_ref}")

    future = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("睡眠 7.6h，日期 2099-01-01。"),
    )
    if future.get("status") != "failed" or future.get("error") != "audit_rejected":
        return _fail(f"future_date in body must reject, got {future}")
    if not any("2099-01-01" in str(v) for v in (future.get("violations") or [])):
        return _fail(f"future_date violation missing, got {future}")

    hr_out = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="给运动强度建议",
        model="selfcheck-model",
        stream_fn=_done("你的训练心率今天是 120–140。"),
    )
    if hr_out.get("status") != "failed":
        return _fail(f"personal HR zone must reject, got {hr_out}")
    if "unauthorized_value:120" not in (hr_out.get("violations") or []) and (
        "unauthorized_value:140" not in (hr_out.get("violations") or [])
    ):
        return _fail(f"HR zone violations missing, got {hr_out}")

    edu_zone = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="给运动强度建议",
        model="selfcheck-model",
        stream_fn=_done("训练心率控制在最大心率的 70–80%。"),
    )
    if edu_zone.get("status") != "done":
        return _fail(f"educational HR zone integers must done, got {edu_zone}")

    t1_zone = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="给运动强度建议",
        model="selfcheck-model",
        stream_fn=_done(
            "今天偏中等。"
            "【参考标准】中等强度常见对应最大心率 64–76%"
            "（来源：ACSM，请自行查证，非医疗建议）"
        ),
    )
    if t1_zone.get("status") != "done":
        return _fail(f"T1 ACSM zone must done, got {t1_zone}")

    ref_on_card = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("参考范围 60–100。"),
    )
    if ref_on_card.get("status") != "done":
        return _fail(f"on-card reference range in body must done, got {ref_on_card}")

    extra80 = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("静息心率 80 bpm。"),
    )
    if extra80.get("status") != "failed" or "unauthorized_value:80" not in (
        extra80.get("violations") or []
    ):
        return _fail(f"off-card metric+unit claim must reject, got {extra80}")

    k1 = current_interpret_key("selfcheck", card=p91_card)
    slim_card = {
        **p91_card,
        "facts": {
            **p91_card["facts"],
            "metrics": p91_card["facts"]["metrics"][:1],
        },
    }
    k2 = current_interpret_key("selfcheck", card=slim_card)
    if k1 == k2:
        return _fail("card_digest must change cache key after selection change")

    plan = build_turn_evidence_plan(
        "请生成今日事实卡解读",
        authoritative_profile="fact_card_interpret",
    )
    if plan.profile != "fact_card_interpret":
        return _fail(f"override profile {plan.profile}")
    if "WEARABLE_90D_SUMMARY" not in plan.forbidden:
        return _fail("WEARABLE_90D_SUMMARY must be forbidden")
    if "SUPPLEMENT_BG" not in plan.forbidden:
        return _fail("SUPPLEMENT_BG must stay forbidden on fact_card_interpret")
    if plan.slots_tier1 != ["USER_BACKGROUND_BRIEF"]:
        return _fail(f"fact_card_interpret tier1 must be USER_BACKGROUND_BRIEF only, got {plan.slots_tier1}")
    if "NUMERICS_MANIFEST" not in plan.slots_tier0:
        return _fail("NUMERICS_MANIFEST missing from fact_card_interpret")
    if resolve_profile_override("not_a_real_profile") is not None:
        return _fail("unknown profile_override must be rejected")

    manifest = build_fact_card_numerics_manifest(p91_card, user_id="selfcheck")
    valued = 1  # sleep has value; RHR has value → 2
    valued = sum(1 for m in p91_card["facts"]["metrics"] if m.get("value") is not None)
    baseline = 0
    reference = 0
    for item in p91_card["facts"]["metrics"]:
        for key in ("baseline_mean", "baseline_min", "baseline_max", "percentile"):
            if item.get(key) is not None:
                baseline += 1
        if item.get("baseline_n") is not None:
            baseline += 1
        ref = item.get("reference") or {}
        if isinstance(ref, dict):
            if ref.get("low") is not None:
                reference += 1
            if ref.get("high") is not None:
                reference += 1
    want = valued + baseline + reference
    if len(manifest.entries) != want:
        return _fail(
            f"manifest entries {len(manifest.entries)} != {want} "
            f"(valued={valued} baseline={baseline} reference={reference})"
        )
    if "2026-09-07" not in manifest.allowed_dates:
        return _fail(f"allowed_dates missing as_of: {sorted(manifest.allowed_dates)}")
    if any(e.domain == "wearable" for e in manifest.entries):
        return _fail("fact_card manifest must not use wearable domain")

    md = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("**睡眠** 7.6h，近 12 个月 267 夜。"),
    )
    if md.get("status") != "done" or "**" in (md.get("text") or ""):
        return _fail(f"markdown markers must be stripped, got {md}")
    if md.get("generated_at") and "T" not in str(md.get("generated_at")):
        return _fail("interpretation.generated_at must stay ISO")

    from pha.fact_card_locale import html_has_slash_date
    from pha.fact_card_interpret import interpret_cache_key

    zh_html = render_fact_card_html(
        p91_card, prefs={**prefs_payload("selfcheck"), "locale": "zh-CN"}, token=None
    )
    en_html = render_fact_card_html(
        p91_card, prefs={**prefs_payload("selfcheck"), "locale": "en-US"}, token=None
    )
    if "9月7日" not in zh_html:
        return _fail("zh HTML must render 9月7日")
    if "Sep 7" not in en_html:
        return _fail("en HTML must render Sep 7")
    if "PHA fact card" not in en_html or "Generate interpretation" not in en_html:
        return _fail("en HTML chrome must be English")
    if "<h1>PHA 事实卡</h1>" in en_html:
        return _fail("en HTML must not keep Chinese h1")
    from pha.metric_catalog_ui import GOLDEN_WEARABLE, apply_catalog_ui_locale, build_metrics_catalog_payload
    if GOLDEN_WEARABLE[0].get("label") != "Daily steps":
        return _fail("golden wearable git default must be English")
    if GOLDEN_WEARABLE[0].get("label_zh") != "每日步数":
        return _fail("golden wearable must keep zh variant")
    zh_cat = apply_catalog_ui_locale(build_metrics_catalog_payload([]), "zh")
    if zh_cat["golden"][0]["label"] != "每日步数":
        return _fail("zh catalog locale must resolve Daily steps to 每日步数")
    en_cat = apply_catalog_ui_locale(build_metrics_catalog_payload([]), "en")
    if en_cat["golden"][0]["label"] != "Daily steps":
        return _fail("en catalog locale must keep Daily steps")
    if zh_cat["golden"][0].get("label_en") != "Daily steps":
        return _fail("zh catalog must keep English label_en for UI switch")
    if "T15:29" in zh_html or "T15:29" in en_html:
        return _fail("HTML must not dump ISO timestamps")
    if html_has_slash_date(zh_html) or html_has_slash_date(en_html):
        return _fail("HTML must not use slash dates")
    if p91_card["facts"]["as_of"] != "2026-09-07":
        return _fail("JSON facts.as_of must stay ISO")
    k_zh = interpret_cache_key("selfcheck", "2026-09-07", "", card_digest="x", locale="zh-CN")
    k_en = interpret_cache_key("selfcheck", "2026-09-07", "", card_digest="x", locale="en-US")
    if k_zh == k_en:
        return _fail("interpret cache key must include locale")
    rhr_html = render_fact_card_html(
        rhr_card, prefs={**prefs_payload("selfcheck"), "locale": "zh-CN"}, token=None
    )
    if "9月5日" not in rhr_html:
        return _fail("prior_day date must be locale-formatted on the HTML row")

    en_ok = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("Sleep 7.6h on Sep 7, 2026, near 12 months 267 nights."),
    )
    if en_ok.get("status") != "done":
        return _fail(f"en-US as_of month name must done, got {en_ok}")
    md_ok = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("9月7日睡眠 7.6h，近 12 个月 267 夜。"),
    )
    if md_ok.get("status") != "done":
        return _fail(f"yearless 9月7日 must done, got {md_ok}")
    en_bad = run_interpretation(
        user_id="selfcheck",
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("Jun 10, 2026 sleep 7.6h."),
    )
    if en_bad.get("status") != "failed" or "unauthorized_date:2026-06-10" not in (
        en_bad.get("violations") or []
    ):
        return _fail(f"en-US off-card date must reject, got {en_bad}")
    next_day = {
        **p91_card,
        "facts": {**p91_card["facts"], "calendar_day": "2026-09-08"},
    }
    if current_interpret_key("selfcheck", card=p91_card) == current_interpret_key(
        "selfcheck", card=next_day
    ):
        return _fail("calendar_day must change interpret cache key")

    from pha.fact_card_interpret import build_fact_card_context_block
    from pha.harness_plan import fact_card_interpret_task_text
    from pha.harness_tier0_assembly import _compress_fact_card_context
    from pha.numerics_manifest import build_fact_card_numerics_manifest, audit_response_numerics

    task = fact_card_interpret_task_text("en")
    if "{T1_TEMPLATE}" in task:
        return _fail("TASK must expand T1_TEMPLATE for locale")
    from pha import harness_plan as _hp

    if "【参考标准" in _hp._FACT_CARD_INTERPRET_TASK:
        return _fail("TASK source must not hardcode Chinese T1 template")
    if "resting_heart_rate" in task or "静息心率" in task:
        return _fail("TASK must not name specific metrics")
    if "did not name" not in task:
        return _fail("TASK must forbid paragraphs for unnamed rows")
    if "USER_BACKGROUND_BRIEF" not in task:
        return _fail("TASK must mention USER_BACKGROUND_BRIEF")

    from pha.goal_classifier import assessment_outline_enabled

    if assessment_outline_enabled():
        exclusive = fact_card_interpret_task_text("en", outline_mode="exclusive")
        emphasis = fact_card_interpret_task_text("en", outline_mode="emphasis")
        cover = fact_card_interpret_task_text("en", outline_mode="cover-card")
        for mode_task, mode_name in (
            (exclusive, "exclusive"),
            (emphasis, "emphasis"),
            (cover, "cover-card"),
        ):
            if "resting_heart_rate" in mode_task or "静息心率" in mode_task:
                return _fail(f"TASK {mode_name} must not name specific metrics")
            if "in-progress cumulative" not in mode_task:
                return _fail(f"TASK {mode_name} must state partial_day is in-progress")
            if "sync disclaimer" not in mode_task:
                return _fail(f"TASK {mode_name} must forbid restating sync disclaimer")
        if "did not name" not in exclusive:
            return _fail("exclusive TASK must keep unnamed-row ban")
        if "same paragraph" not in emphasis or "topical" not in emphasis:
            return _fail("emphasis TASK must allow same-paragraph mention only")
        if "Cover checked rows" not in cover:
            return _fail("cover-card TASK must cover checked valued rows")

    from pha.chat_turn_slots import select_soul_base
    from pha.harness_plan import PHA_FACT_CARD_SOUL_MINIMAL
    from pha.attachment_asset_qa import PHA_ATTACHMENT_SOUL_MINIMAL
    from pha.wearable_harness import PHA_WEARABLE_SOUL_MINIMAL
    from pha.intent_gates import QuestionType as _QT
    import re as _re

    if select_soul_base("fact_card_interpret", _QT.WEARABLE) is not PHA_FACT_CARD_SOUL_MINIMAL:
        return _fail("fact_card_interpret must use PHA_FACT_CARD_SOUL_MINIMAL")
    if select_soul_base("wearable_screenshot_review", _QT.WEARABLE) is not PHA_WEARABLE_SOUL_MINIMAL:
        return _fail("wearable_screenshot_review soul regression")
    if select_soul_base("attachment_asset_qa", _QT.WEARABLE) is not PHA_ATTACHMENT_SOUL_MINIMAL:
        return _fail("attachment_asset_qa soul regression")
    if select_soul_base("lab_cross_year", _QT.LAB) is not None:
        return _fail("other profiles must fall through to full medical soul")
    soul = PHA_FACT_CARD_SOUL_MINIMAL
    for banned in (
        "resting_heart_rate",
        "静息心率",
        "HRV",
        "SpO2",
        "VO2",
        "【参考标准",
        "[Reference Standard",
    ):
        if banned in soul:
            return _fail(f"FACT_CARD soul must not hardcode {banned!r}")
    if _re.search(r"[\u4e00-\u9fff]", soul):
        return _fail("FACT_CARD soul must not contain CJK")
    from pha.fact_card_interpret import _interpret_prompt_rev

    rev_a = _interpret_prompt_rev()
    _orig_soul = _hp.PHA_FACT_CARD_SOUL_MINIMAL
    try:
        _hp.PHA_FACT_CARD_SOUL_MINIMAL = _orig_soul + "\n# rev-bump"
        rev_b = _interpret_prompt_rev()
    finally:
        _hp.PHA_FACT_CARD_SOUL_MINIMAL = _orig_soul
    if rev_a == rev_b:
        return _fail("interpret cache rev must change when soul text changes")
    if _interpret_prompt_rev() != rev_a:
        return _fail("interpret cache rev must restore after soul monkeypatch")

    ctx = build_fact_card_context_block(p91_card)
    if "7.6" not in ctx:
        return _fail("interpret context must keep the full card, not a parsed subset")
    if "大纲是 USER_ASSESSMENT_PROMPT" not in ctx:
        return _fail("context header must defer to USER_ASSESSMENT_PROMPT")
    min_ctx = _compress_fact_card_context(ctx, "min")
    if "7.6" not in min_ctx or "metrics omitted" in min_ctx:
        return _fail("Tier0 min must keep metric values, got " + min_ctx[:200])
    manifest = build_fact_card_numerics_manifest(p91_card, user_id="selfcheck")
    # Behavioral: SpO2 identifier + .0 normalize must pass; educational 95 must pass;
    # personal off-card must fail; harness audit == card path status.
    for text, want_pass in (
        ("今天血氧 7.6%，SpO2 正常。", True),  # 7.6 is on card sleep value — ok
        ("一般成年人血氧高于 95% 视为正常。", True),
        ("你的 HRV 接近 35 ms。", False),
        ("建议睡 7.5 小时。", False),
        (
            "[Reference Standard] SpO2 above 95% is typical "
            "(source: WHO, verify by yourself, not medical advice)",
            True,
        ),
    ):
        audit = audit_response_numerics(text, manifest)
        if bool(audit.get("passed")) != want_pass:
            return _fail(f"fact_card audit want pass={want_pass} for {text!r}, got {audit}")
        streamed = run_interpretation(
            user_id="selfcheck",
            card=p91_card,
            assessment_prompt="",
            model="selfcheck-model",
            stream_fn=_done(text),
        )
        status_pass = streamed.get("status") == "done"
        if status_pass != want_pass:
            return _fail(
                f"run_interpretation status must match audit for {text!r}: {streamed}"
            )

    boom_html = render_fact_card_html(
        {
            **p91_card,
            "interpretation": {
                "status": "failed",
                "error": "model_unavailable",
            },
        },
        prefs=prefs_payload("selfcheck"),
        token=None,
    )
    if "本机模型未响应" not in boom_html or "重试" not in boom_html:
        return _fail("failed interpret HTML must say 本机模型未响应 and 重试")

    mem_err = _check_p13_memory(p91_card)
    if mem_err:
        return mem_err
    p14_err = _check_p14_background(p91_card)
    if p14_err:
        return p14_err

    print("pha_fact_card_selfcheck: PASS")
    return 0


def _restore_p13_db(old_db, old_slots, old_disc) -> None:
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st

    st.DEFAULT_DB_PATH = old_db
    if old_slots is None:
        os.environ.pop("PHA_USER_DYNAMIC_SLOTS_DIR", None)
    else:
        os.environ["PHA_USER_DYNAMIC_SLOTS_DIR"] = old_slots
    if old_disc is None:
        os.environ.pop("PHA_DYNAMIC_SLOT_DISCOVERY", None)
    else:
        os.environ["PHA_DYNAMIC_SLOT_DISCOVERY"] = old_disc
    sc.reset_schema_state_for_tests()


def _memory_table_counts() -> dict[str, int]:
    from pha.sqlite_storage import _connect

    names = (
        "chat_sessions",
        "chat_messages",
        "user_health_background_notes",
        "chat_session_turn_focus",
        "chat_session_active_recall",
    )
    conn = _connect()
    try:
        out: dict[str, int] = {}
        for name in names:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
            out[name] = (
                int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                if exists
                else 0
            )
        return out
    finally:
        conn.close()


def _check_p13_memory(p91_card: dict) -> int | None:
    """FR-6.11: interpret writes no chat memory; hygiene script classifies A/B/C."""
    import pha.chat_turn_orchestrator as orch
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from pha.chat_background import maybe_capture_chat_background
    from pha.chat_storage import append_message, create_session, init_chat_schema
    from pha.chat_background import init_background_schema
    from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE
    from pha.harness_profile_registry import (
        introspect_harness_profile_plans,
        memory_write_policy,
    )

    if memory_write_policy("fact_card_interpret") != "none":
        return _fail("fact_card_interpret memory_write_policy must be none")
    snap = introspect_harness_profile_plans().get("fact_card_interpret") or {}
    t1 = set(snap.get("slots_tier1") or [])
    if "USER_BACKGROUND_BRIEF" not in t1:
        return _fail("fact_card_interpret tier1 must include USER_BACKGROUND_BRIEF")
    if "RECALL" in t1 or "EPISODIC_BRIDGE" in t1:
        return _fail("fact_card_interpret tier1 must not include RECALL/EPISODIC_BRIDGE")

    tmp = Path(tempfile.mkdtemp(prefix="pha-p13-"))
    db = tmp / "pha_storage.db"
    slots_dir = tmp / "slots"
    slots_dir.mkdir()
    slots_path = slots_dir / "dynamic_slots.json"
    slots_path.write_text("{}", encoding="utf-8")
    mtime0 = slots_path.stat().st_mtime
    old_db = st.DEFAULT_DB_PATH
    old_slots = os.environ.get("PHA_USER_DYNAMIC_SLOTS_DIR")
    old_disc = os.environ.get("PHA_DYNAMIC_SLOT_DISCOVERY")
    os.environ["PHA_USER_DYNAMIC_SLOTS_DIR"] = str(slots_dir)
    os.environ["PHA_DYNAMIC_SLOT_DISCOVERY"] = "1"
    st.DEFAULT_DB_PATH = db
    old_tls = getattr(sc._thread_local, "conn", None)
    if old_tls is not None:
        try:
            old_tls.close()
        except Exception:
            pass
    sc.reset_schema_state_for_tests()
    st.init_schema()
    init_chat_schema()
    init_background_schema()

    stored, rej = maybe_capture_chat_background(
        "selfcheck",
        "[vision_parse_failed] Server error 500",
    )
    if stored or rej != "system_tag_message":
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail(f"system tag must reject capture, got stored={stored} rej={rej}")
    stored_ok, rej_ok = maybe_capture_chat_background("selfcheck", "每天补镁 400mg")
    if not stored_ok or rej_ok is not None:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("real supplement note must still capture")

    class _FakeProvider:
        def __init__(self, model: str = "selfcheck-model", **_kwargs):
            self.model = model

        def stream_chat_messages(self, *, messages):
            yield "今日指标处于你的常见范围，训练可按舒适强度进行。"

        def chat_with_tools(self, *, messages, tools):
            return {
                "message": {
                    "role": "assistant",
                    "content": "今日指标处于你的常见范围，训练可按舒适强度进行。",
                },
            }

    real_sess = create_session("selfcheck")
    append_message(real_sess.id, "user", "我最近睡眠还行")
    append_message(real_sess.id, "assistant", "好的")
    maybe_capture_chat_background("selfcheck", "每天补镁 400mg")
    maybe_capture_chat_background("selfcheck", "鱼油一直在吃")
    before = _memory_table_counts()

    prev_provider = orch.OllamaProvider
    orch.OllamaProvider = _FakeProvider  # type: ignore[misc, assignment]
    try:
        events = list(
            orch.orchestrate_chat_turn_events(
                user_id="selfcheck",
                user_message=FACT_CARD_INTERPRET_USER_MESSAGE,
                model="selfcheck-model",
                profile_override="fact_card_interpret",
                fact_card_payload=p91_card,
                fact_card_context="{}",
                user_assessment_prompt="",
                response_locale="zh-CN",
            ),
        )
    finally:
        orch.OllamaProvider = prev_provider  # type: ignore[misc]

    after_interp = _memory_table_counts()
    if after_interp != before:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail(f"interpret must not write chat memory: {before} -> {after_interp}")
    if slots_path.stat().st_mtime != mtime0:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("interpret must not rewrite dynamic_slots.json")
    done_ev = None
    for raw in events:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "done":
            done_ev = payload
    if not done_ev:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("interpret orchestrate must still emit done")
    if done_ev.get("session_id") is not None:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("interpret done.session_id must be null")

    orch.OllamaProvider = _FakeProvider  # type: ignore[misc, assignment]
    try:
        list(
            orch.orchestrate_chat_turn_events(
                user_id="selfcheck",
                user_message="最近饮食需要注意什么",
                model="selfcheck-model",
                profile_override="lifestyle",
                response_locale="zh-CN",
            ),
        )
    finally:
        orch.OllamaProvider = prev_provider  # type: ignore[misc]

    after_life = _memory_table_counts()
    if after_life["chat_sessions"] != before["chat_sessions"] + 1:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail(
            f"lifestyle must create a session: {before['chat_sessions']} -> {after_life['chat_sessions']}",
        )
    if after_life["chat_messages"] < before["chat_messages"] + 2:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail(
            f"lifestyle must append user+assistant: {before['chat_messages']} -> {after_life['chat_messages']}",
        )

    import importlib.util

    hy_path = Path(ROOT) / "scripts" / "pha_memory_hygiene.py"
    spec = importlib.util.spec_from_file_location("pha_memory_hygiene", hy_path)
    if spec is None or spec.loader is None:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("cannot load pha_memory_hygiene")
    hygiene_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hygiene_mod)
    classify = hygiene_mod.classify
    connect = hygiene_mod.connect
    hygiene_run = hygiene_mod.run
    _SYN = FACT_CARD_INTERPRET_USER_MESSAGE

    hy_db = tmp / "hygiene.db"
    hy_conn = connect(hy_db)
    try:
        hy_conn.executescript(
            """
            CREATE TABLE chat_sessions (
                id TEXT PRIMARY KEY, user_id TEXT, title TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT
            );
            CREATE TABLE chat_session_turn_focus (session_id TEXT PRIMARY KEY, focus_summary TEXT);
            CREATE TABLE chat_session_active_recall (session_id TEXT PRIMARY KEY, ledger_json TEXT);
            CREATE TABLE user_health_background_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, note_date TEXT,
                category TEXT, content TEXT, created_at TEXT
            );
            """,
        )
        keep_sid = "keep-real"
        hy_conn.execute(
            "INSERT INTO chat_sessions VALUES (?,?,?,?,?)",
            (keep_sid, "selfcheck", "真实", "2026-09-01", "2026-09-01"),
        )
        hy_conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (keep_sid, "user", "每天补镁 400mg", "2026-09-01"),
        )
        hy_conn.execute(
            "INSERT INTO user_health_background_notes "
            "(user_id, note_date, category, content, created_at) VALUES (?,?,?,?,?)",
            ("selfcheck", "2026-09-01", "supplement", "每天补镁 400mg", "2026-09-01"),
        )
        for i in range(2):
            sid = f"interp-{i}"
            hy_conn.execute(
                "INSERT INTO chat_sessions VALUES (?,?,?,?,?)",
                (sid, "selfcheck", "解读", "2026-09-08", "2026-09-08"),
            )
            hy_conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (sid, "user", _SYN, "2026-09-08"),
            )
            hy_conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (sid, "assistant", "解读正文", "2026-09-08"),
            )
            hy_conn.execute(
                "INSERT INTO chat_session_turn_focus VALUES (?,?)",
                (sid, "leak"),
            )
        hy_conn.execute(
            "INSERT INTO user_health_background_notes "
            "(user_id, note_date, category, content, created_at) VALUES (?,?,?,?,?)",
            (
                "selfcheck",
                "2026-09-08",
                "medication",
                "请根据系统提供的当日事实卡数字与基线摘要，写一段简短的健康教育解读。只能引用已给出的数字。",
                "2026-09-08",
            ),
        )
        hy_conn.execute(
            "INSERT INTO user_health_background_notes "
            "(user_id, note_date, category, content, created_at) VALUES (?,?,?,?,?)",
            (
                "selfcheck",
                "2026-09-08",
                "unstructured_vision",
                "[vision_parse_failed] Server error 500",
                "2026-09-08",
            ),
        )
        for i in range(2):
            hy_conn.execute(
                "INSERT INTO chat_sessions VALUES (?,?,?,?,?)",
                (f"empty-{i}", "selfcheck", "空", "2026-09-08", "2026-09-08"),
            )
        hy_conn.commit()
        dry = classify(hy_conn)
        if len(dry["A"]) != 2 or len(dry["B"]) != 2 or len(dry["C"]) != 2:
            _restore_p13_db(old_db, old_slots, old_disc)
            return _fail(f"hygiene dry-run counts want A2 B2 C2 got { {k: len(dry[k]) for k in 'ABC'} }")
    finally:
        hy_conn.close()

    applied = hygiene_run(db_path=hy_db, apply=True, include_empty=False)
    after_hy = applied.get("after") or {}
    if len(after_hy.get("A") or []) != 0 or len(after_hy.get("B") or []) != 0:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("hygiene apply must clear A and B")
    if len(after_hy.get("C") or []) != 2:
        _restore_p13_db(old_db, old_slots, old_disc)
        return _fail("hygiene apply must keep empty sessions by default")
    verify = connect(hy_db)
    try:
        real_sessions = verify.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE id=?",
            (keep_sid,),
        ).fetchone()[0]
        real_notes = verify.execute(
            "SELECT COUNT(*) FROM user_health_background_notes WHERE category='supplement'",
        ).fetchone()[0]
        if real_sessions != 1 or real_notes != 1:
            _restore_p13_db(old_db, old_slots, old_disc)
            return _fail("hygiene apply must keep the real session and supplement note")
    finally:
        verify.close()

    _restore_p13_db(old_db, old_slots, old_disc)
    return None


def _check_p14_background(p91_card: dict) -> int | None:
    """FR-6.12: USER_BACKGROUND_BRIEF is denumerized Tier1, never a numeric source."""
    import pha.chat_turn_orchestrator as orch
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from pha.chat_background import init_background_schema
    from pha.chat_storage import init_chat_schema
    from pha.fact_card_background_brief import (
        background_brief_enabled,
        build_fact_card_background_brief,
    )
    from pha.fact_card_copy import card_copy
    from pha.fact_card_interpret import build_fact_card_context_block, interpret_cache_key
    from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE
    from pha.numerics_manifest import leftover_s_level_numeric_tokens

    html = render_fact_card_html(
        {
            **p91_card,
            "interpretation": {
                "status": "done",
                "text": "ok",
                "model": "selfcheck-model",
                "generated_at": "2026-09-09T00:00:00+00:00",
                "background_used": True,
                "background_notes_used": 2,
            },
        },
        prefs={**prefs_payload("selfcheck"), "locale": "zh-CN"},
        token=None,
    )
    if "已参考你在对话中自述的 2 条背景" not in html:
        return _fail("interpret HTML must show referenced background count")
    en_html = render_fact_card_html(
        {
            **p91_card,
            "interpretation": {
                "status": "done",
                "text": "ok",
                "model": "selfcheck-model",
                "generated_at": "2026-09-09T00:00:00+00:00",
                "background_used": True,
                "background_notes_used": 2,
            },
        },
        prefs={**prefs_payload("selfcheck"), "locale": "en-US"},
        token=None,
    )
    if "Referenced 2 background note" not in en_html:
        return _fail("en interpret HTML must show referenced background count")

    tmp = Path(tempfile.mkdtemp(prefix="pha-p14-"))
    db = tmp / "pha_storage.db"
    slots_dir = tmp / "slots"
    slots_dir.mkdir()
    old_db = st.DEFAULT_DB_PATH
    old_slots = os.environ.get("PHA_USER_DYNAMIC_SLOTS_DIR")
    old_disc = os.environ.get("PHA_DYNAMIC_SLOT_DISCOVERY")
    old_flag = os.environ.get("PHA_FACT_CARD_BG_BRIEF")
    old_quota = os.environ.get("PHA_FACT_CARD_BG_BRIEF_QUOTA")
    os.environ["PHA_USER_DYNAMIC_SLOTS_DIR"] = str(slots_dir)
    os.environ["PHA_DYNAMIC_SLOT_DISCOVERY"] = "1"
    os.environ["PHA_FACT_CARD_BG_BRIEF"] = "1"
    st.DEFAULT_DB_PATH = db
    old_tls = getattr(sc._thread_local, "conn", None)
    if old_tls is not None:
        try:
            old_tls.close()
        except Exception:
            pass
    sc.reset_schema_state_for_tests()
    st.init_schema()
    init_chat_schema()
    init_background_schema()

    def _restore() -> None:
        if old_flag is None:
            os.environ.pop("PHA_FACT_CARD_BG_BRIEF", None)
        else:
            os.environ["PHA_FACT_CARD_BG_BRIEF"] = old_flag
        if old_quota is None:
            os.environ.pop("PHA_FACT_CARD_BG_BRIEF_QUOTA", None)
        else:
            os.environ["PHA_FACT_CARD_BG_BRIEF_QUOTA"] = old_quota
        _restore_p13_db(old_db, old_slots, old_disc)

    def _insert(uid: str, note_date: str, category: str, content: str) -> None:
        conn = st._connect()
        try:
            conn.execute(
                "INSERT INTO user_health_background_notes "
                "(user_id, note_date, category, content) VALUES (?, ?, ?, ?)",
                (uid, note_date, category, content),
            )
            conn.commit()
        finally:
            conn.close()

    uid = "selfcheck-p14"
    _insert(uid, "2026-09-05", "supplement", "每晚补镁 400mg")
    _insert(uid, "2026-09-05", "sleep_lifestyle", "最近两周都 1 点后睡")
    _insert(uid, "2026-09-05", "supplement", "在吃维生素D3 和 Omega-3")
    _insert(uid, "2026-09-01", "supplement", "2026-09-01 开始每天两次鱼油")
    _insert(
        uid,
        "2026-09-05",
        "unstructured_vision",
        "[vision_parse_failed] Server error 500",
    )

    brief, meta = build_fact_card_background_brief(
        uid, locale="zh-CN", as_of="2026-09-07"
    )
    if not brief:
        _restore()
        return _fail("P14 brief must be non-empty with fixture notes")
    for needle in ("镁", "维生素D3", "Omega-3", "鱼油"):
        if needle not in brief:
            _restore()
            return _fail(f"P14 brief missing {needle!r}: {brief}")
    for banned in ("400", "1 点", "2026", "两次"):
        if banned in brief:
            _restore()
            return _fail(f"P14 brief leaked {banned!r}: {brief}")
    if "2026-09-05" in brief or "2026-09-01" in brief:
        _restore()
        return _fail(f"P14 brief must not emit note_date: {brief}")
    rel_words = (
        card_copy("zh-CN", "bg_brief_rel_week"),
        card_copy("zh-CN", "bg_brief_rel_month"),
        card_copy("zh-CN", "bg_brief_rel_earlier"),
    )
    if not any(word in brief for word in rel_words):
        _restore()
        return _fail(f"P14 brief must include a relative time word: {brief}")
    if "[vision_parse_failed]" in brief or "Server error" in brief:
        _restore()
        return _fail("P14 brief must drop unstructured_vision / system-tag notes")
    leftover = leftover_s_level_numeric_tokens(brief)
    if leftover:
        _restore()
        return _fail(f"P14 brief leftover S-level tokens {leftover}: {brief}")
    if int(meta.get("notes_used") or 0) < 4:
        _restore()
        return _fail(f"P14 notes_used too low: {meta}")

    class _CaptureProvider:
        last_blob = ""

        def __init__(self, model: str = "selfcheck-model", **_kwargs):
            self.model = model

        def stream_chat_messages(self, *, messages):
            parts = []
            for item in messages or []:
                if isinstance(item, dict):
                    parts.append(str(item.get("content") or ""))
            _CaptureProvider.last_blob = "\n".join(parts)
            yield "今日指标处于你的常见范围，训练可按舒适强度进行。"

        def chat_with_tools(self, *, messages, tools):
            parts = []
            for item in messages or []:
                if isinstance(item, dict):
                    parts.append(str(item.get("content") or ""))
            _CaptureProvider.last_blob = "\n".join(parts)
            return {
                "message": {
                    "role": "assistant",
                    "content": "今日指标处于你的常见范围，训练可按舒适强度进行。",
                },
            }

    prev_provider = orch.OllamaProvider
    orch.OllamaProvider = _CaptureProvider  # type: ignore[misc, assignment]
    try:
        list(
            orch.orchestrate_chat_turn_events(
                user_id=uid,
                user_message=FACT_CARD_INTERPRET_USER_MESSAGE,
                model="selfcheck-model",
                profile_override="fact_card_interpret",
                fact_card_payload=p91_card,
                fact_card_context=build_fact_card_context_block(p91_card),
                user_assessment_prompt="重点看静息心率",
                response_locale="zh-CN",
            ),
        )
    finally:
        orch.OllamaProvider = prev_provider  # type: ignore[misc]
    sys_blob = _CaptureProvider.last_blob
    if "用户背景 · 自述 · 非数字源" not in sys_blob:
        _restore()
        return _fail("P14 system prompt must include USER_BACKGROUND_BRIEF title")
    for banned in (
        "聊天背景档案",
        "上轮对话摘要",
        "近90日穿戴",
        "SUPPLEMENT_BG",
        "EPISODIC_BRIDGE",
        "WEARABLE_90D_SUMMARY",
        "【RECALL】",
    ):
        if banned in sys_blob:
            _restore()
            return _fail(f"P14 system prompt leaked {banned!r}")
    for t0 in (
        "【TASK】",
        "用户评估要求",
        "唯一可引用数字与日期",
        "Numerics Manifest",
    ):
        if t0 not in sys_blob:
            _restore()
            return _fail(f"P14 Tier0 missing {t0!r}")

    budget_uid = "selfcheck-p14-budget"
    os.environ["PHA_FACT_CARD_BG_BRIEF_QUOTA"] = json.dumps(
        {"supplement": 40, "medication": 4, "sleep_lifestyle": 3, "symptom": 3, "general": 2},
    )
    for i in range(40):
        _insert(budget_uid, "2026-09-05", "supplement", f"钙片 {i + 10}mg 早晚各一次编号{i}")
    fat, fat_meta = build_fact_card_background_brief(
        budget_uid, locale="zh-CN", as_of="2026-09-07"
    )
    title = card_copy("zh-CN", "bg_brief_title")
    lead = card_copy("zh-CN", "bg_brief_lead")
    header = f"【{title}】\n{lead}\n"
    body = fat[len(header) :] if fat.startswith(header) else fat
    if len(body) > 600:
        _restore()
        return _fail(f"P14 brief body exceeds 600 chars: {len(body)}")
    last_line = body.strip().splitlines()[-1] if body.strip() else ""
    if last_line.endswith("〔") or last_line.endswith("["):
        _restore()
        return _fail(f"P14 brief last line looks truncated: {last_line!r}")
    if int(fat_meta.get("notes_used") or 0) < 1:
        _restore()
        return _fail("P14 budget brief must keep at least one note")

    k_on = current_interpret_key(uid, card=p91_card, locale="zh-CN")
    os.environ["PHA_FACT_CARD_BG_BRIEF"] = "0"
    if background_brief_enabled():
        _restore()
        return _fail("flag 0 must disable background brief")
    off_text, off_meta = build_fact_card_background_brief(
        uid, locale="zh-CN", as_of="2026-09-07"
    )
    if off_text or int(off_meta.get("notes_used") or 0) != 0:
        _restore()
        return _fail("flag 0 must yield empty brief")
    k_off = current_interpret_key(uid, card=p91_card, locale="zh-CN")
    if k_on == k_off:
        _restore()
        return _fail("flag 0 cache key must differ from flag 1")
    orch.OllamaProvider = _CaptureProvider  # type: ignore[misc, assignment]
    try:
        list(
            orch.orchestrate_chat_turn_events(
                user_id=uid,
                user_message=FACT_CARD_INTERPRET_USER_MESSAGE,
                model="selfcheck-model",
                profile_override="fact_card_interpret",
                fact_card_payload=p91_card,
                fact_card_context=build_fact_card_context_block(p91_card),
                user_assessment_prompt="重点看静息心率",
                response_locale="zh-CN",
            ),
        )
    finally:
        orch.OllamaProvider = prev_provider  # type: ignore[misc]
    if "用户背景 · 自述 · 非数字源" in _CaptureProvider.last_blob:
        _restore()
        return _fail("flag 0 system prompt must omit USER_BACKGROUND_BRIEF title")

    os.environ["PHA_FACT_CARD_BG_BRIEF"] = "1"
    k_same = current_interpret_key(uid, card=p91_card, locale="zh-CN")
    if k_same != k_on:
        _restore()
        return _fail("unchanged notes must keep interpret cache key")
    _insert(uid, "2026-09-06", "supplement", "辅酶Q10 一直在吃")
    k_new = current_interpret_key(uid, card=p91_card, locale="zh-CN")
    if k_new == k_on:
        _restore()
        return _fail("new background note must change interpret cache key")
    digest_a = interpret_cache_key(
        uid, "2026-09-07", "", card_digest="x", locale="zh-CN", bg_brief_digest="aaa"
    )
    digest_b = interpret_cache_key(
        uid, "2026-09-07", "", card_digest="x", locale="zh-CN", bg_brief_digest="bbb"
    )
    if digest_a == digest_b:
        _restore()
        return _fail("interpret_cache_key must include bg_brief_digest")

    def _done(text: str):
        def _stream(**_kwargs):
            yield json.dumps(
                {
                    "event": "done",
                    "model": "selfcheck-model",
                    "answer": {"answer_text": text},
                    "numerics_audit": {"passed": True, "violations": []},
                },
                ensure_ascii=False,
            )

        return _stream

    streamed = run_interpretation(
        user_id=uid,
        card=p91_card,
        assessment_prompt="",
        model="selfcheck-model",
        stream_fn=_done("你的静息心率 400 bpm。"),
        locale="zh-CN",
    )
    if streamed.get("status") != "failed":
        _restore()
        return _fail(f"brief numbers must still fail audit, got {streamed}")
    if "unauthorized_value:400" not in (streamed.get("violations") or []):
        _restore()
        return _fail(f"audit must reject 400 from brief, got {streamed}")

    _restore()
    return None


def json_blob(card: dict) -> str:
    import json

    return json.dumps(card, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())

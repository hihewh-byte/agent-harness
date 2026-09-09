#!/usr/bin/env python3
"""Offline: fact card binds calendar day, user-selected metrics, short notify + HTML."""

from __future__ import annotations

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

    print("pha_fact_card_selfcheck: PASS")
    return 0


def json_blob(card: dict) -> str:
    import json

    return json.dumps(card, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""H9–H13 / H9E–H13E: chat ↔ fact-card parity (offline, fixture ledger)."""

from __future__ import annotations

import os
import sys
from datetime import date
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("PHA_GOAL_CLASSIFIER", "1")
os.environ.setdefault("PHA_GOAL_SESSION_ANCHOR", "1")
os.environ.setdefault("PHA_DAILY_READINESS_PROFILE", "1")
os.environ.setdefault("PHA_WEARABLE_CLUSTER_EXPAND", "1")
os.environ.setdefault("PHA_EPISODIC_GRAIN_ANCHOR", "1")

from pha.goal_classifier import classify_goal  # noqa: E402
from pha.grounded_answer_composer import try_warehouse_metric_focus_skip  # noqa: E402
from pha.harness_arbiter import resolve_harness_arbiter  # noqa: E402
from pha.harness_plan import build_turn_evidence_plan  # noqa: E402
from pha.health_intent_catalog import load_health_intent_catalog  # noqa: E402
from pha.intent_gates import infer_wearable_metric_ids  # noqa: E402
from pha.models import WearableDailySummary  # noqa: E402
from pha.sqlite_storage import init_schema, upsert_wearable_daily_batch  # noqa: E402
from pha.wearable_time_grain import resolve_wearable_time_grain  # noqa: E402

UID = "parity_selfcheck"
DAY = date(2026, 9, 9)
PRIOR = date(2026, 9, 8)

H9_ZH = "请分析今天的HRV，静息心率和睡眠数据是否适合高强度的力量训练？"
H9_EN = "Based on today's HRV, resting heart rate and sleep, is high-intensity strength training appropriate?"
H10_ZH = "今天的睡眠数据没有吗？请核实"
H10_EN = "Is there really no sleep data for today? Please verify."
H11_ZH = "核心睡眠是多少？深睡是多少？睡眠清醒是多少？"
H11_EN = "How much core sleep, deep sleep and awake time?"
H12_ZH = "请列出今天的睡眠相关的数据"
H13_ZH = "今天静息心率多少？"
H13_EN = "What is today's resting heart rate?"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _seed() -> None:
    init_schema()
    upsert_wearable_daily_batch(
        [
            WearableDailySummary(
                user_id=UID,
                day=DAY,
                sleep_hours=8.2167,
                sleep_deep_hours=0.4667,
                sleep_rem_hours=2.45,
                sleep_core_hours=5.3,
                awake_duration_hours=0.7833,
                hrv_sdnn_ms=32.83,
                resting_heart_rate_bpm=None,
                steps=67,
            ),
            WearableDailySummary(
                user_id=UID,
                day=PRIOR,
                sleep_hours=6.2,
                sleep_deep_hours=0.9,
                sleep_rem_hours=1.8,
                sleep_core_hours=3.5,
                awake_duration_hours=0.5,
                hrv_sdnn_ms=30.0,
                resting_heart_rate_bpm=62.0,
            ),
        ]
    )


def _today_episodic() -> SimpleNamespace:
    return SimpleNamespace(
        focus_grain_start=DAY.isoformat(),
        focus_grain_end=DAY.isoformat(),
        focus_grain_aggregation="point",
    )


def test_h9_readiness_profile() -> None:
    load_health_intent_catalog.cache_clear()
    for msg in (H9_ZH, H9_EN):
        goal = classify_goal(msg)
        _assert(goal.goal_class == "daily_readiness", f"{msg!r} → {goal}")
        decision = resolve_harness_arbiter(
            msg,
            user_id=UID,
            router_profile="wearable_only",
            goal=goal,
            existence_override={"wearable": True, "lab": False},
        )
        _assert(decision is not None, msg)
        _assert(decision.authoritative_profile == "wearable_daily_review", decision)
        _assert(decision.reason == "goal_readiness_daily", decision)
        plan = build_turn_evidence_plan(
            msg,
            authoritative_profile=decision.authoritative_profile,
        )
        _assert(plan.profile == "wearable_daily_review", plan.profile)
        _assert("FACT_CARD_CONTEXT" in plan.slots_tier0, plan.slots_tier0)
        _assert("NUMERICS_MANIFEST" in plan.slots_tier0, plan.slots_tier0)
        _assert("USER_ASSESSMENT_PROMPT" in plan.slots_tier0, plan.slots_tier0)
    print("PASS H9/H9E daily_readiness → wearable_daily_review")


def test_h10_sleep_cluster_point() -> None:
    ids = infer_wearable_metric_ids(H10_ZH)
    _assert("sleep_time_asleep" in ids, ids)
    _assert("sleep_deep" in ids and "sleep_rem" in ids, ids)
    _assert("sleep_core" in ids and "sleep_awake" in ids, ids)
    _assert("sleep_in_bed" not in ids, ids)
    ids_en = infer_wearable_metric_ids(H10_EN)
    _assert(set(ids) == set(ids_en), (ids, ids_en))
    zh = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H10_ZH,
        manifest=None,
        response_locale="zh",
    )
    en = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H10_EN,
        manifest=None,
        response_locale="en",
    )
    _assert("8.22" in zh and "0.47" in zh and "2.45" in zh, zh)
    _assert("5.3" in zh and "0.78" in zh, zh)
    _assert("2026-09-09" in zh, zh)
    _assert("均值" not in zh, zh)
    _assert("8.22" in en and "0.47" in en and "2.45" in en, en)
    _assert("2026-09-09" in en, en)
    _assert("Mean" not in en, en)
    print("PASS H10/H10E sleep cluster point-day skip-LLM")


def test_h11_grain_anchor() -> None:
    grain = resolve_wearable_time_grain(H11_ZH, episodic=_today_episodic())
    _assert(grain.source == "episodic_anchor", grain)
    _assert(grain.start == DAY and grain.end == DAY, grain)
    on = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H11_ZH,
        manifest=None,
        response_locale="zh",
        episodic=_today_episodic(),
    )
    _assert("5.3" in on and "0.47" in on and "0.78" in on, on)
    _assert("2026-09-09" in on, on)
    _assert("均值" not in on, on)
    prev = os.environ.get("PHA_EPISODIC_GRAIN_ANCHOR")
    os.environ["PHA_EPISODIC_GRAIN_ANCHOR"] = "0"
    try:
        off_grain = resolve_wearable_time_grain(H11_ZH, episodic=_today_episodic())
        _assert(off_grain.source == "default", off_grain)
        off = try_warehouse_metric_focus_skip(
            user_id=UID,
            profile="wearable_only",
            user_message=H11_ZH,
            manifest=None,
            response_locale="zh",
            episodic=_today_episodic(),
        )
        _assert("均值" in off, off)
        _assert("- **睡眠均值**" not in off, off)
    finally:
        if prev is None:
            os.environ.pop("PHA_EPISODIC_GRAIN_ANCHOR", None)
        else:
            os.environ["PHA_EPISODIC_GRAIN_ANCHOR"] = prev
    en = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H11_EN,
        manifest=None,
        response_locale="en",
        episodic=_today_episodic(),
    )
    _assert("5.3" in en and "0.47" in en, en)
    print("PASS H11/H11E episodic grain anchor on/off")


def test_h12_h13_fail_closed() -> None:
    h12 = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H12_ZH,
        manifest=None,
        response_locale="zh",
    )
    _assert("8.22" in h12, h12)
    _assert("在床" not in h12 or "库内没有" not in h12, h12)
    explicit = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message="今天在床多久？",
        manifest=None,
        response_locale="zh",
    )
    _assert("库内没有 2026-09-09 的在床记录" in explicit, explicit)
    h13 = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H13_ZH,
        manifest=None,
        response_locale="zh",
    )
    _assert("库内没有 2026-09-09 的静息心率记录" in h13, h13)
    _assert("不会用其他日期或其他指标的数字代替" in h13, h13)
    _assert("62" not in h13, h13)
    h13e = try_warehouse_metric_focus_skip(
        user_id=UID,
        profile="wearable_only",
        user_message=H13_EN,
        manifest=None,
        response_locale="en",
    )
    _assert("No verified" in h13e and "2026-09-09" in h13e, h13e)
    _assert("62" not in h13e, h13e)
    print("PASS H12/H13/H13E fail-closed (no silent date/metric swap)")


def main() -> int:
    _seed()
    test_h9_readiness_profile()
    test_h10_sleep_cluster_point()
    test_h11_grain_anchor()
    test_h12_h13_fail_closed()
    print("ALL PASS pha_chat_fact_card_parity_selfcheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

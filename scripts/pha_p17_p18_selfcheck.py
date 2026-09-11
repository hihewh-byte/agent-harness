#!/usr/bin/env python3
"""M1-P17 / M1-P18: outline modes + context_lookup (O1–O3 / C1–C4)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_GOAL_CLASSIFIER", "1")
os.environ.setdefault("PHA_ASSESSMENT_OUTLINE", "1")
os.environ.setdefault("PHA_CONTEXT_LOOKUP", "1")
os.environ.setdefault("PHA_DAILY_READINESS_PROFILE", "1")

from pha.chat_background import (  # noqa: E402
    list_background_notes,
    maybe_capture_chat_background,
    should_capture_background_message,
)
from pha.fact_card import _advice  # noqa: E402
from pha.fact_card_copy import card_copy  # noqa: E402
from pha.goal_classifier import classify_goal  # noqa: E402
from pha.grounded_answer_composer import (  # noqa: E402
    _label_for_metric_id,
    build_fact_card_event,
    is_warehouse_metric_focus_turn,
)
from pha.harness_plan import fact_card_interpret_task_text  # noqa: E402
from pha.health_intent_catalog import (  # noqa: E402
    classify_outline_mode,
    infer_metrics_from_message,
    load_health_intent_catalog,
)
from pha.intent_gates import infer_wearable_metric_ids  # noqa: E402
from pha.numerics_manifest import ManifestEntry, NumericsManifest  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _banned_sync_needles() -> tuple[str, ...]:
    return (
        "未进 Mac",
        "还在手机",
        "健康 App 有数不等于已进",
        "not on this Mac",
        "still on the phone",
    )


def _core_manifest(hrv_label: str, energy_label: str) -> NumericsManifest:
    return NumericsManifest(
        profile="wearable_only",
        user_id="p17p18_selfcheck",
        entries=[
            ManifestEntry(
                domain="wearable",
                metric=hrv_label,
                value=33.1,
                unit="ms",
                anchor="90d",
                source="selfcheck",
            ),
            ManifestEntry(
                domain="wearable",
                metric=energy_label,
                value=412.0,
                unit="kcal",
                anchor="90d",
                source="selfcheck",
            ),
        ],
    )


def test_o1_exclusive() -> None:
    load_health_intent_catalog.cache_clear()
    prompt = "只看静息心率"
    _assert(classify_outline_mode(prompt) == "exclusive", classify_outline_mode(prompt))
    task = fact_card_interpret_task_text("en", outline_mode="exclusive")
    _assert("did not name" in task, task)
    _assert("same paragraph" not in task, task)
    _assert("resting_heart_rate" not in task and "静息心率" not in task, task)
    print("PASS O1 exclusive outline (P9.5b unnamed-row ban)")


def test_o2_emphasis_readiness() -> None:
    load_health_intent_catalog.cache_clear()
    prompt = "今天整体恢复如何，重点看HRV和睡眠，再给训练建议"
    goal = classify_goal(prompt)
    _assert(goal.goal_class == "daily_readiness", goal)
    _assert(classify_outline_mode(prompt) == "emphasis", classify_outline_mode(prompt))
    task = fact_card_interpret_task_text("en", outline_mode="emphasis")
    _assert("same paragraph" in task and "topical" in task, task)
    _assert("Sentence 1 = overall" in task, task)
    _assert("did not name" not in task, task)
    exclusive = fact_card_interpret_task_text("en", outline_mode="exclusive")
    _assert("Sentence 1 = overall" not in exclusive, exclusive)
    print("PASS O2 daily_readiness + emphasis")


def test_o3_accrual_copy_domains() -> None:
    zh_partial = _advice(
        "typical",
        "活动消耗",
        baseline_window="90d",
        baseline_n=30,
        baseline_earliest=None,
        night=False,
        partial_day=True,
        as_of_time="18:00",
        locale="zh-CN",
    )
    en_partial = card_copy(
        "en-US",
        "advice_partial",
        label="Active energy",
        until="as of 18:00 ",
    )
    zh_ok = card_copy("zh-CN", "hk_ok", metric="HRV", at="12:00")
    en_ok = card_copy("en-US", "hk_ok", metric="HRV", at="12:00")
    for blob in (zh_partial, en_partial, zh_ok, en_ok):
        for needle in _banned_sync_needles():
            _assert(needle not in blob, f"{needle!r} in {blob!r}")
    _assert("不是缺失" in zh_partial, zh_partial)
    _assert("not missing" in en_partial, en_partial)
    print("PASS O3 accrual copy vs hk/sync domains")


def test_c1_lookup_no_card() -> None:
    load_health_intent_catalog.cache_clear()
    msg = "有服用什么药物吗？"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "context_lookup", goal)
    _assert(not infer_metrics_from_message(msg), infer_metrics_from_message(msg))
    ids = infer_wearable_metric_ids("近90天HRV")
    energy_ids = infer_wearable_metric_ids("活动消耗")
    _assert(ids and energy_ids, (ids, energy_ids))
    hrv_label = _label_for_metric_id(
        ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    energy_label = _label_for_metric_id(
        energy_ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    fc = build_fact_card_event(_core_manifest(hrv_label, energy_label), user_message=msg)
    _assert(fc is None, fc)
    print("PASS C1 context_lookup emits no fact_card")


def test_c2_hrv_card_allowed() -> None:
    load_health_intent_catalog.cache_clear()
    msg = "近90天HRV趋势如何"
    goal = classify_goal(msg)
    _assert(goal.goal_class != "context_lookup", goal)
    ids = infer_wearable_metric_ids(msg)
    energy_ids = infer_wearable_metric_ids("活动消耗")
    _assert(ids and energy_ids, (ids, energy_ids))
    hrv_label = _label_for_metric_id(
        ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    energy_label = _label_for_metric_id(
        energy_ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    fc = build_fact_card_event(_core_manifest(hrv_label, energy_label), user_message=msg)
    _assert(fc is not None, "C2 should still emit an HRV card")
    metrics = {str(item.get("metric") or "") for item in fc.get("items") or []}
    _assert(hrv_label in metrics, metrics)
    _assert(energy_label not in metrics, metrics)
    print("PASS C2 HRV trend card ⊆ named metric")


def test_c3_skip_veto_and_scope() -> None:
    load_health_intent_catalog.cache_clear()
    msg = "药物对于HRV有没有影响"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "context_lookup", goal)
    _assert(infer_metrics_from_message(msg), infer_metrics_from_message(msg))
    _assert(not is_warehouse_metric_focus_turn(msg), "lookup must veto warehouse skip")
    ids = infer_wearable_metric_ids(msg)
    energy_ids = infer_wearable_metric_ids("活动消耗")
    _assert(ids and energy_ids, (ids, energy_ids))
    hrv_label = _label_for_metric_id(
        ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    energy_label = _label_for_metric_id(
        energy_ids[0], locale="zh", grain_point=False, same_day_today=False
    )
    fc = build_fact_card_event(_core_manifest(hrv_label, energy_label), user_message=msg)
    if fc is None:
        print("PASS C3 skip veto; empty scoped card (fail-closed, no energy dump)")
        return
    metrics = {str(item.get("metric") or "") for item in fc.get("items") or []}
    _assert(energy_label not in metrics, metrics)
    print("PASS C3 skip veto and card ⊆ named rows")


def test_c4_question_not_captured() -> None:
    question = "有服用什么药物吗？"
    statement = "我每天服用辅酶Q10一粒作为自述"
    _assert(not should_capture_background_message(question), question)
    _assert(should_capture_background_message(statement), statement)
    uid = "p18_c4_selfcheck"
    before = len(list_background_notes(uid, limit=50))
    stored, _reason = maybe_capture_chat_background(uid, question)
    _assert(stored is False, stored)
    after = len(list_background_notes(uid, limit=50))
    _assert(after == before, (before, after))
    print("PASS C4 question does not increment notes")


def test_flag_off_card_regression() -> None:
    """PHA_CONTEXT_LOOKUP=0 restores emit-if-entries (documented rollback risk)."""
    prev = os.environ.get("PHA_CONTEXT_LOOKUP")
    os.environ["PHA_CONTEXT_LOOKUP"] = "0"
    try:
        ids = infer_wearable_metric_ids("近90天HRV")
        energy_ids = infer_wearable_metric_ids("活动消耗")
        hrv_label = _label_for_metric_id(
            ids[0], locale="zh", grain_point=False, same_day_today=False
        )
        energy_label = _label_for_metric_id(
            energy_ids[0], locale="zh", grain_point=False, same_day_today=False
        )
        fc = build_fact_card_event(
            _core_manifest(hrv_label, energy_label),
            user_message="有服用什么药物吗？",
        )
        _assert(fc is not None and fc.get("items"), fc)
    finally:
        if prev is None:
            os.environ.pop("PHA_CONTEXT_LOOKUP", None)
        else:
            os.environ["PHA_CONTEXT_LOOKUP"] = prev
    print("PASS flag-off fact_card regression (entries still emit)")


def main() -> int:
    tests = [
        test_o1_exclusive,
        test_o2_emphasis_readiness,
        test_o3_accrual_copy_domains,
        test_c1_lookup_no_card,
        test_c2_hrv_card_allowed,
        test_c3_skip_veto_and_scope,
        test_c4_question_not_captured,
        test_flag_off_card_regression,
    ]
    for test in tests:
        test()
    print("ALL PASS pha_p17_p18_selfcheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

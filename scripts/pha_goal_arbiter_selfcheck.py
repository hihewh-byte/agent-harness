#!/usr/bin/env python3
"""Stage 3F-α: GoalClassifier + Harness Arbiter golden cases H5–H8."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.goal_classifier import classify_goal, goal_classifier_enabled
from pha.harness_arbiter import resolve_harness_arbiter
from pha.harness_plan import build_turn_evidence_plan
from pha.health_intent_catalog import load_health_intent_catalog


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _with_goal_classifier(fn) -> None:
    prev_gc = os.environ.get("PHA_GOAL_CLASSIFIER")
    prev_ga = os.environ.get("PHA_GOAL_SESSION_ANCHOR")
    prev_ci = os.environ.get("PHA_CLARIFY_INTENT_SCOPE")
    os.environ["PHA_GOAL_CLASSIFIER"] = "1"
    os.environ["PHA_GOAL_SESSION_ANCHOR"] = "1"
    os.environ["PHA_CLARIFY_INTENT_SCOPE"] = "1"
    load_health_intent_catalog.cache_clear()
    try:
        _assert(goal_classifier_enabled(), "PHA_GOAL_CLASSIFIER should be on")
        fn()
    finally:
        load_health_intent_catalog.cache_clear()
        if prev_gc is None:
            os.environ.pop("PHA_GOAL_CLASSIFIER", None)
        else:
            os.environ["PHA_GOAL_CLASSIFIER"] = prev_gc
        if prev_ga is None:
            os.environ.pop("PHA_GOAL_SESSION_ANCHOR", None)
        else:
            os.environ["PHA_GOAL_SESSION_ANCHOR"] = prev_ga
        if prev_ci is None:
            os.environ.pop("PHA_CLARIFY_INTENT_SCOPE", None)
        else:
            os.environ["PHA_CLARIFY_INTENT_SCOPE"] = prev_ci


def test_h5_holistic_dual_domain_upgrade() -> None:
    msg = "根据各项指标综合评估健康状态"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "holistic_assessment", goal)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="lifestyle",
        goal=goal,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "combined_review", decision)
    _assert(decision.reason == "goal_holistic_upgrade", decision)
    plan = build_turn_evidence_plan(msg, authoritative_profile=decision.authoritative_profile)
    _assert(plan.profile == "combined_review", plan.profile)
    _assert(plan.profile != "lifestyle", plan.profile)
    print("PASS H5 holistic + dual probe → combined_review")


def test_h6_metric_specific_no_upgrade() -> None:
    msg = "我最近的 HRV 怎么样"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "metric_specific", goal)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="wearable_only",
        goal=goal,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "wearable_only", decision)
    _assert(decision.reason == "schema_default", decision)
    print("PASS H6 explicit metric → schema_default (no holistic upgrade)")


def test_h7_explicit_ldl_override() -> None:
    msg = "只看 LDL"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "metric_specific", goal)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="lab_cross_year",
        goal=goal,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision.authoritative_profile == "lab_cross_year", decision)
    print("PASS H7 explicit LDL → lab_cross_year")


def test_h8_single_domain_intent_scope_clarify() -> None:
    msg = "根据各项指标综合评估健康状态"
    goal = classify_goal(msg)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="lifestyle",
        goal=goal,
        existence_override={"lab": False, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "clarify", decision)
    _assert(decision.reason == "goal_clarify_scope", decision)
    _assert(decision.turn_scope is not None, "clarify scope missing")
    _assert(decision.turn_scope.clarify_kind == "intent_scope", decision.turn_scope)
    plan = build_turn_evidence_plan(msg, turn_scope=decision.turn_scope)
    _assert(plan.profile == "clarify", plan.profile)
    print("PASS H8 holistic + wearable-only probe → intent_scope clarify")


def test_h6_episodic_goal_continue() -> None:
    from pha.health_episodic_focus import HealthSessionFocus

    episodic = HealthSessionFocus(
        session_id="h6",
        focus_profile="wearable_only",
        focus_goal="holistic_assessment",
        focus_domains=["lab", "wearable"],
        turns_remaining=6,
        last_user_message="根据各项指标综合评估健康状态",
    )
    decision = resolve_harness_arbiter(
        "那结论呢",
        user_id="default",
        router_profile="lifestyle",
        episodic=episodic,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.reason == "episodic_goal_continue", decision)
    _assert(decision.authoritative_profile == "combined_review", decision)
    plan = build_turn_evidence_plan("那结论呢", authoritative_profile=decision.authoritative_profile)
    _assert(plan.profile == "combined_review", plan.profile)
    print("PASS H6 holistic goal anchor → weak follow-up → combined_review")


def test_h6b_arbiter_beats_episodic_profile_hint() -> None:
    from pha.health_turn_resolver import HealthTurnScope

    scope = HealthTurnScope(profile_hint="wearable_only", focus_profile="wearable_only")
    plan = build_turn_evidence_plan(
        "身体年龄多少岁",
        turn_scope=scope,
        authoritative_profile="combined_review",
    )
    _assert(plan.profile == "combined_review", plan.profile)
    print("PASS H6b arbiter combined beats turn_scope wearable_only")


def test_h7_explicit_metric_clears_goal_continue() -> None:
    from pha.health_episodic_focus import HealthSessionFocus

    episodic = HealthSessionFocus(
        session_id="h7",
        focus_profile="combined_review",
        focus_goal="holistic_assessment",
        focus_domains=["lab", "wearable"],
        turns_remaining=6,
    )
    decision = resolve_harness_arbiter(
        "只看 LDL",
        user_id="default",
        router_profile="lab_cross_year",
        episodic=episodic,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.reason == "schema_default", decision)
    _assert(decision.authoritative_profile == "lab_cross_year", decision)
    print("PASS H7 explicit LDL overrides holistic goal continue")


def test_h9_arbiter_beats_attachment_qa_flag() -> None:
    plan = build_turn_evidence_plan(
        "用已有数据分析身体年龄",
        attachment_asset_qa=True,
        attachment_qa_mode="episodic_bridge",
        authoritative_profile="combined_review",
    )
    _assert(plan.profile == "combined_review", plan.profile)
    _assert("fetch_evidence_by_id" in (plan.tools_allowed or []), plan.tools_allowed)
    print("PASS H9 arbiter combined_review beats attachment_asset_qa routing flag")


def test_h9b_attachment_qa_without_arbiter() -> None:
    plan = build_turn_evidence_plan(
        "这个补剂标签成分是什么",
        attachment_asset_qa=True,
        attachment_qa_mode="initial",
    )
    _assert(plan.profile == "attachment_asset_qa", plan.profile)
    print("PASS H9b attachment_asset_qa when no authoritative_profile")


def test_h9c_lab_marker_blocks_holistic_continue() -> None:
    from pha.health_episodic_focus import HealthSessionFocus

    episodic = HealthSessionFocus(
        session_id="h9c",
        focus_profile="combined_review",
        focus_goal="holistic_assessment",
        focus_domains=["lab", "wearable"],
        turns_remaining=6,
    )
    decision = resolve_harness_arbiter(
        "血脂怎么样",
        user_id="default",
        router_profile="lab_cross_year",
        episodic=episodic,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "lab_cross_year", decision)
    _assert(decision.reason == "schema_default", decision)
    plan = build_turn_evidence_plan(
        "血脂怎么样",
        authoritative_profile=decision.authoritative_profile,
        attachment_asset_qa=True,
    )
    _assert(plan.profile == "lab_cross_year", plan.profile)
    print("PASS H9c lab marker → lab_cross_year (not holistic continue)")


def test_h9d_orchestrator_auth_profile_on_schema_default() -> None:
    from pha.health_episodic_focus import HealthSessionFocus

    episodic = HealthSessionFocus(
        session_id="h9d",
        focus_profile="combined_review",
        focus_goal="holistic_assessment",
        focus_domains=["lab", "wearable"],
        turns_remaining=6,
    )
    decision = resolve_harness_arbiter(
        "血脂怎么样",
        user_id="default",
        router_profile="lab_cross_year",
        episodic=episodic,
        existence_override={"lab": True, "wearable": True},
    )
    _assert(decision is not None and decision.reason == "schema_default", decision)
    auth = decision.authoritative_profile
    plan = build_turn_evidence_plan(
        "血脂怎么样",
        attachment_asset_qa=True,
        authoritative_profile=auth,
    )
    _assert(plan.profile == "lab_cross_year", plan.profile)
    print("PASS H9d schema_default authoritative_profile wired to plan")


def test_p18_context_lookup_no_metric_lifestyle() -> None:
    msg = "有服用什么药物吗？"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "context_lookup", goal)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="wearable_only",
        goal=goal,
        existence_override={"wearable": True, "lab": False},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "lifestyle", decision)
    _assert(decision.reason == "goal_context_lookup", decision)
    plan = build_turn_evidence_plan(
        msg,
        authoritative_profile=decision.authoritative_profile,
    )
    _assert(plan.profile == "lifestyle", plan.profile)
    _assert("NUMERICS_MANIFEST" not in plan.slots_tier0, plan.slots_tier0)
    print("PASS P18 context_lookup no metric → lifestyle")


def test_p18_context_lookup_keeps_router_when_metrics() -> None:
    msg = "药物对于HRV有没有影响"
    goal = classify_goal(msg)
    _assert(goal.goal_class == "context_lookup", goal)
    decision = resolve_harness_arbiter(
        msg,
        user_id="default",
        router_profile="wearable_only",
        goal=goal,
        existence_override={"wearable": True, "lab": False},
    )
    _assert(decision is not None, "arbiter missing")
    _assert(decision.authoritative_profile == "wearable_only", decision)
    _assert(decision.reason == "explicit_metric_with_context_lookup", decision)
    print("PASS P18 context_lookup + metric keeps Data profile")


def test_p18_lookup_without_goal_classifier() -> None:
    prev = os.environ.get("PHA_GOAL_CLASSIFIER")
    os.environ["PHA_GOAL_CLASSIFIER"] = "0"
    load_health_intent_catalog.cache_clear()
    try:
        msg = "有服用什么药物吗？"
        decision = resolve_harness_arbiter(
            msg,
            user_id="default",
            router_profile="wearable_only",
            existence_override={"wearable": True, "lab": False},
        )
        _assert(decision is not None, "lookup should run with classifier off")
        _assert(decision.authoritative_profile == "lifestyle", decision)
        _assert(decision.reason == "goal_context_lookup", decision)
    finally:
        load_health_intent_catalog.cache_clear()
        if prev is None:
            os.environ.pop("PHA_GOAL_CLASSIFIER", None)
        else:
            os.environ["PHA_GOAL_CLASSIFIER"] = prev
    print("PASS P18 context_lookup with PHA_GOAL_CLASSIFIER=0")


def main() -> int:
    tests = [
        test_h5_holistic_dual_domain_upgrade,
        test_h6_episodic_goal_continue,
        test_h6b_arbiter_beats_episodic_profile_hint,
        test_h7_explicit_metric_clears_goal_continue,
        test_h6_metric_specific_no_upgrade,
        test_h7_explicit_ldl_override,
        test_h8_single_domain_intent_scope_clarify,
        test_h9_arbiter_beats_attachment_qa_flag,
        test_h9b_attachment_qa_without_arbiter,
        test_h9c_lab_marker_blocks_holistic_continue,
        test_h9d_orchestrator_auth_profile_on_schema_default,
        test_p18_context_lookup_no_metric_lifestyle,
        test_p18_context_lookup_keeps_router_when_metrics,
    ]
    for test in tests:
        _with_goal_classifier(test)
    test_p18_lookup_without_goal_classifier()
    print(f"\nAll {len(tests) + 1} goal/arbiter checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

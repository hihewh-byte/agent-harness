#!/usr/bin/env python3
"""M1-P19: emphasis lead, Tier0 no tail-cut, workout hints, card-scoped SSE."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_GOAL_CLASSIFIER", "1")
os.environ.setdefault("PHA_ASSESSMENT_OUTLINE", "1")
os.environ.setdefault("PHA_CONTEXT_LOOKUP", "1")
os.environ.setdefault("PHA_WEARABLE_CLUSTER_EXPAND", "1")

from pha.chat_message_stack import SYSTEM_CONTENT_MAX_CHARS, _cap_system_tiered  # noqa: E402
from pha.goal_classifier import classify_goal  # noqa: E402
from pha.grounded_answer_composer import (  # noqa: E402
    _scope_from_fact_card_payload,
    build_fact_card_event,
)
from pha.harness_plan import (  # noqa: E402
    QuestionType,
    TurnEvidencePlan,
    fact_card_interpret_task_text,
)
from pha.harness_tier0_assembly import assemble_tiered_supplemental_v2  # noqa: E402
from pha.health_intent_catalog import classify_outline_mode  # noqa: E402
from pha.intent_gates import infer_wearable_metric_ids  # noqa: E402
from pha.numerics_manifest import ManifestEntry, NumericsManifest  # noqa: E402
from pha.wearable_metric_registry import clear_registry_cache  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _interpret_plan() -> TurnEvidencePlan:
    return TurnEvidencePlan(
        profile="fact_card_interpret",
        slots_tier0=[
            "TASK",
            "USER_ASSESSMENT_PROMPT",
            "FACT_CARD_CONTEXT",
            "NUMERICS_MANIFEST",
        ],
        slots_tier1=["USER_BACKGROUND_BRIEF"],
        forbidden=[],
        tools_allowed=[],
        task_text=fact_card_interpret_task_text("en", outline_mode="emphasis"),
        legacy_question_type=QuestionType.WEARABLE,
    )


def test_p19_t_emphasis_lead() -> None:
    prompt = "今天整体恢复如何，重点看HRV和睡眠，再给训练建议"
    _assert(classify_goal(prompt).goal_class == "daily_readiness", classify_goal(prompt))
    _assert(classify_outline_mode(prompt) == "emphasis", classify_outline_mode(prompt))
    emphasis = fact_card_interpret_task_text("en", outline_mode="emphasis")
    exclusive = fact_card_interpret_task_text("en", outline_mode="exclusive")
    _assert("Sentence 1 = overall" in emphasis, emphasis)
    _assert("no metric labels" in emphasis, emphasis)
    _assert("Sentence 1 = overall" not in exclusive, exclusive)
    _assert("resting_heart_rate" not in emphasis and "静息心率" not in emphasis, emphasis)
    print("PASS P19-T emphasis Sentence 1 overall; exclusive does not")


def test_p19_k_training_words_not_workout() -> None:
    clear_registry_cache()
    family = [
        "今天整体恢复如何，重点看HRV和睡眠，再给训练建议",
        "是否可以进行力量训练？",
        "这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度",
    ]
    for msg in family:
        ids = infer_wearable_metric_ids(msg)
        _assert(
            "workout_heart_rate_range_bpm" not in ids,
            f"workout HR leaked from {msg!r}: {ids}",
        )
        _assert(
            "workout_count_recent" not in ids,
            f"workout count leaked from {msg!r}: {ids}",
        )
    named = infer_wearable_metric_ids("请报告锻炼心率范围")
    _assert("workout_heart_rate_range_bpm" in named, named)
    print("PASS P19-K readiness training words do not infer workout_*")


def test_p19_s_sleep_cluster() -> None:
    clear_registry_cache()
    ids = infer_wearable_metric_ids("睡眠的各项指标")
    for mid in ("sleep_deep", "sleep_rem", "sleep_core", "sleep_awake"):
        _assert(mid in ids, f"{mid} missing from {ids}")
    print("PASS P19-S sleep cluster still expands")


def test_p19_c_sse_from_card() -> None:
    msg = "评估今天整体身体状况，重点看静息心率与HRV，睡眠的各项指标，运动训练与力量训练"
    card_ids = [
        "hrv_sdnn_ms",
        "resting_heart_rate",
        "sleep_time_asleep",
        "sleep_deep",
        "active_energy",
        "blood_oxygen",
    ]
    scope = _scope_from_fact_card_payload({"enabled_metric_ids": card_ids}, msg)
    _assert(scope == card_ids, scope)
    _assert("workout_heart_rate_range_bpm" not in scope, scope)
    manifest = NumericsManifest(
        profile="wearable_daily_review",
        user_id="p19",
        entries=[
            ManifestEntry(
                domain="fact_card",
                metric="HRV",
                value=33.1,
                unit="ms",
                anchor="today",
                source="fact_card",
            )
        ],
    )
    fc = build_fact_card_event(
        manifest,
        user_message=msg,
        fact_card_payload={"enabled_metric_ids": card_ids},
    )
    _assert(fc is not None, fc)
    _assert("workout_heart_rate_range_bpm" not in (fc.get("metrics_in_scope") or []), fc)
    _assert(set(fc.get("metrics_in_scope") or []) <= set(card_ids), fc)
    print("PASS P19-C SSE scope ⊆ fact-card ids when payload present")


def test_p19_b_tier0_no_tail_cut() -> None:
    metrics = [
        {
            "metric": f"metric_{i}",
            "label": f"Label{i}",
            "value": 10 + i,
            "unit": "u",
            "day": "2026-09-09",
        }
        for i in range(12)
    ]
    payload = {
        "metrics": metrics,
        "summary": "S" * 1800,
        "advice": "A" * 1800,
    }
    context = "以下为唯一可引用数字与日期。大纲是 USER_ASSESSMENT_PROMPT，不是 summary/advice。\n" + json.dumps(
        payload, ensure_ascii=False
    )
    manifest_lines = ["【Numerics Manifest】"]
    for i in range(12):
        manifest_lines.append(f"Label{i} {10 + i}u 2026-09-09")
    manifest = "\n".join(manifest_lines)
    t0, _t1, _missing, integrity = assemble_tiered_supplemental_v2(
        plan=_interpret_plan(),
        slot_contents={
            "TASK": fact_card_interpret_task_text("en", outline_mode="emphasis"),
            "USER_ASSESSMENT_PROMPT": "emphasis outline",
            "FACT_CARD_CONTEXT": context,
            "NUMERICS_MANIFEST": manifest,
        },
    )
    for i in range(12):
        token = f"{10 + i}u"
        _assert(token in t0, f"missing {token} in assembled T0 (integrity={integrity})")
    _assert("系统提示已熔断截断" not in t0, t0[-200:])
    _assert("Tier0 证据已按上限截断" not in t0, t0[-200:])
    marker = "p19_manifest_kv_33.17"
    huge = f"NUMERICS_MANIFEST\n{marker}\n" + ("x" * (SYSTEM_CONTENT_MAX_CHARS + 800))
    protected = _cap_system_tiered(
        soul_with_anchor="soul",
        tier0_supplemental=huge,
        tier1_supplemental="brief should drop",
        protect_tier0=True,
    )
    _assert(marker in protected, protected[:200])
    _assert("系统提示已熔断截断" not in protected, protected[-80:])

    from pha.numerics_manifest import format_manifest_tier0_block

    many = NumericsManifest(
        profile="fact_card_interpret",
        user_id="p19",
        entries=[
            ManifestEntry(
                domain="fact_card",
                metric=f"Label{i}",
                value=float(10 + i),
                unit="u",
                anchor="2026-09-09",
                source="fact_card",
            )
            for i in range(12)
        ],
    )
    block = format_manifest_tier0_block(many, profile="fact_card_interpret")
    for i in range(12):
        _assert(f"Label{i}" in block, f"truncated fact-card manifest missing Label{i}")
    _assert("已按 Tier0 上限截断" not in block, block[-120:])
    print("PASS P19-B Tier0 metric KV not tail-truncated")


def main() -> int:
    tests = [
        test_p19_t_emphasis_lead,
        test_p19_k_training_words_not_workout,
        test_p19_s_sleep_cluster,
        test_p19_c_sse_from_card,
        test_p19_b_tier0_no_tail_cut,
    ]
    for test in tests:
        test()
    print("ALL PASS pha_p19_selfcheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

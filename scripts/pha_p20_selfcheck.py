#!/usr/bin/env python3
"""M1-P20: exclusive LLM inject ⊆ catalog named metric ids."""

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
os.environ.setdefault("PHA_EXCLUSIVE_INJECT_NAMED", "1")
os.environ.setdefault("PHA_WEARABLE_CLUSTER_EXPAND", "1")

from pha.fact_card_interpret import (  # noqa: E402
    build_fact_card_context_block,
    exclusive_inject_is_empty,
    run_interpretation,
    slice_fact_card_for_outline_inject,
)
from pha.health_intent_catalog import classify_outline_mode  # noqa: E402
from pha.intent_gates import infer_wearable_metric_ids  # noqa: E402
from pha.numerics_manifest import build_fact_card_numerics_manifest  # noqa: E402


GOLDEN_EMPHASIS = (
    "评估今天整体身体状况，重点看今天的静息心率与HRV，睡眠的各项指标，"
    "用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，"
    "比如运动类型运动强度的建议，是否可以进行力量训练？"
)
EXCLUSIVE_DEEP = "只看今天的深睡"
EXCLUSIVE_VO2 = "只看今天的VO2Max"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _card() -> dict:
    return {
        "user_id": "selfcheck-p20",
        "facts": {
            "as_of": "2026-09-10",
            "calendar_day": "2026-09-10",
            "stale": False,
            "metrics": [
                {
                    "metric": "sleep_deep",
                    "label": "深睡",
                    "value": 0.5,
                    "unit": "h",
                    "day": "2026-09-10",
                    "baseline_window": "90d",
                    "baseline_n": 40,
                },
                {
                    "metric": "resting_heart_rate_bpm",
                    "label": "静息心率",
                    "value": 62,
                    "unit": "bpm",
                    "day": "2026-09-10",
                    "baseline_window": "90d",
                    "baseline_n": 40,
                },
                {
                    "metric": "hrv_sdnn_ms",
                    "label": "HRV SDNN",
                    "value": 35,
                    "unit": "ms",
                    "day": "2026-09-10",
                    "baseline_window": "90d",
                    "baseline_n": 40,
                },
                {
                    "metric": "active_energy",
                    "label": "活动消耗",
                    "value": 400,
                    "unit": "kcal",
                    "day": "2026-09-10",
                    "baseline_window": "90d",
                    "baseline_n": 40,
                },
            ],
        },
        "assessment": {
            "summary": {"text": "已选4项"},
            "advice": [
                {"metric": "sleep_deep", "text": "深睡偏低"},
                {"metric": "active_energy", "text": "消耗进行中"},
            ],
        },
    }


def _metric_ids(card: dict) -> list[str]:
    return [
        str(row.get("metric"))
        for row in ((card.get("facts") or {}).get("metrics") or [])
        if isinstance(row, dict)
    ]


def test_exclusive_inject_named_only() -> None:
    _assert(classify_outline_mode(EXCLUSIVE_DEEP) == "exclusive", classify_outline_mode(EXCLUSIVE_DEEP))
    named = infer_wearable_metric_ids(EXCLUSIVE_DEEP)
    _assert("sleep_deep" in named, named)
    sliced = slice_fact_card_for_outline_inject(
        _card(),
        outline_mode="exclusive",
        assessment_prompt=EXCLUSIVE_DEEP,
    )
    ids = _metric_ids(sliced)
    _assert(ids == ["sleep_deep"], ids)
    _assert("resting_heart_rate_bpm" not in ids, ids)
    ctx = build_fact_card_context_block(sliced)
    _assert("sleep_deep" in ctx, ctx)
    _assert("resting_heart_rate_bpm" not in ctx, ctx)
    _assert("active_energy" not in ctx, ctx)
    manifest = build_fact_card_numerics_manifest(sliced, user_id="selfcheck-p20")
    mids = [str(getattr(e, "metric", "") or "") for e in (manifest.entries or [])]
    _assert(any("深睡" in m for m in mids), mids)
    _assert(not any("活动消耗" in m or "active_energy" in m for m in mids), mids)
    _assert("400" not in ctx, ctx)


def test_emphasis_keeps_full_card() -> None:
    _assert(classify_outline_mode(GOLDEN_EMPHASIS) == "emphasis", classify_outline_mode(GOLDEN_EMPHASIS))
    sliced = slice_fact_card_for_outline_inject(
        _card(),
        outline_mode="emphasis",
        assessment_prompt=GOLDEN_EMPHASIS,
    )
    ids = set(_metric_ids(sliced))
    _assert(
        {"sleep_deep", "resting_heart_rate_bpm", "hrv_sdnn_ms", "active_energy"} <= ids,
        ids,
    )
    ctx = build_fact_card_context_block(sliced)
    _assert("active_energy" in ctx, ctx)


def test_exclusive_empty_fail_closed() -> None:
    _assert(classify_outline_mode(EXCLUSIVE_VO2) == "exclusive", classify_outline_mode(EXCLUSIVE_VO2))
    _assert(
        exclusive_inject_is_empty(
            _card(),
            outline_mode="exclusive",
            assessment_prompt=EXCLUSIVE_VO2,
        ),
        infer_wearable_metric_ids(EXCLUSIVE_VO2),
    )

    def _boom(**_kwargs):
        raise AssertionError("exclusive empty must not call LLM")
        yield ""  # pragma: no cover

    result = run_interpretation(
        user_id="selfcheck-p20",
        card=_card(),
        assessment_prompt=EXCLUSIVE_VO2,
        model="selfcheck-model",
        stream_fn=_boom,
        locale="zh-CN",
    )
    _assert(result.get("status") == "failed", result)
    _assert(result.get("error") == "exclusive_scope_empty", result)


def test_flag_off_restores_full_card() -> None:
    prev = os.environ.get("PHA_EXCLUSIVE_INJECT_NAMED")
    os.environ["PHA_EXCLUSIVE_INJECT_NAMED"] = "0"
    try:
        sliced = slice_fact_card_for_outline_inject(
            _card(),
            outline_mode="exclusive",
            assessment_prompt=EXCLUSIVE_DEEP,
        )
        ids = set(_metric_ids(sliced))
        _assert("resting_heart_rate_bpm" in ids, ids)
        _assert("sleep_deep" in ids, ids)
    finally:
        if prev is None:
            os.environ.pop("PHA_EXCLUSIVE_INJECT_NAMED", None)
        else:
            os.environ["PHA_EXCLUSIVE_INJECT_NAMED"] = prev


def main() -> int:
    test_exclusive_inject_named_only()
    print("PASS P20 exclusive inject ⊆ named ids")
    test_emphasis_keeps_full_card()
    print("PASS P20 emphasis still full-card inject")
    test_exclusive_empty_fail_closed()
    print("PASS P20 exclusive empty fail-closed")
    test_flag_off_restores_full_card()
    print("PASS P20 flag off restores full card")
    print("OK pha_p20_selfcheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

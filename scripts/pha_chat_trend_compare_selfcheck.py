#!/usr/bin/env python3
"""M1-P23: chat trend_compare intent + Manifest compare atoms (T1/T2/T4/T5)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_t1_trend_hits_and_manifest_has_compare() -> None:
    from pha.chat_trend_compare import is_trend_compare_turn
    from pha.numerics_manifest import build_numerics_manifest, format_manifest_tier0_block

    msg = "最近一周我的HRV和深睡的数据有什么变化？"
    _assert(is_trend_compare_turn(msg, user_id="default"), "T1 must hit trend_compare")
    m = build_numerics_manifest(
        "default",
        profile="wearable_only",
        user_message=msg,
        include_lipid=False,
        include_wearable=True,
    )
    compare = [e for e in m.entries if (e.source or "").startswith("wearable.trend_compare")]
    _assert(
        len(compare) >= 2,
        f"T1 expected compare atoms (mean+n), got {compare!r} entries={m.entries!r}",
    )
    _assert("7" in m.window_day_tokens or "90" in m.window_day_tokens, m.window_day_tokens)

    block = format_manifest_tier0_block(m, profile="wearable_only")
    for e in compare[:4]:
        _assert(e.kv_line() in block or e.metric.split("·")[0] in block, f"truncated dropped {e}")


def test_t2_rhr_14d_task_and_compare() -> None:
    from pha.chat_trend_compare import is_trend_compare_turn, trend_compare_task_text
    from pha.harness_plan import build_turn_evidence_plan
    from pha.numerics_manifest import build_numerics_manifest

    msg = "近14天静息心率趋势如何？"
    _assert(is_trend_compare_turn(msg, user_id="default"), "T2 must hit trend_compare")
    plan = build_turn_evidence_plan(msg)
    _assert(plan.profile == "wearable_only", plan.profile)
    _assert("趋势/对比" in (plan.task_text or ""), plan.task_text)
    _assert("对照" in (plan.task_text or ""), plan.task_text)
    _assert(trend_compare_task_text(locale="zh") in (plan.task_text or ""), "TASK must be trend_compare copy")

    m = build_numerics_manifest(
        "default",
        profile="wearable_only",
        user_message=msg,
        include_lipid=False,
        include_wearable=True,
    )
    compare = [e for e in m.entries if (e.source or "").startswith("wearable.trend_compare")]
    _assert(len(compare) >= 2, f"T2 expected compare atoms, got {compare!r}")
    _assert("14" in m.window_day_tokens or any("14" in (e.anchor or "") for e in m.entries), m.window_day_tokens)


def test_t4_compare_insufficient_skip() -> None:
    from pha.chat_skip_llm import evaluate_skip_llm_path
    from pha.chat_trend_compare import (
        build_compare_insufficient_answer,
        try_trend_compare_deterministic_reply,
    )
    from pha.harness_plan import build_turn_evidence_plan
    from pha.numerics_manifest import ManifestEntry, NumericsManifest

    msg = "最近一周我的HRV有什么变化？"
    plan = build_turn_evidence_plan(msg)
    focal_only = NumericsManifest(
        profile="wearable_only",
        user_id="default",
        entries=[
            ManifestEntry(
                domain="wearable",
                metric="HRV均值",
                value=42.0,
                unit="ms",
                anchor="2026-09-11~2026-09-17",
                source="wearable.summary",
            )
        ],
        window_day_tokens={"7"},
    )
    with patch(
        "pha.chat_trend_compare.compile_trend_compare_stats",
        return_value=[],
    ), patch(
        "pha.numerics_manifest.build_numerics_manifest",
        return_value=focal_only,
    ):
        det = try_trend_compare_deterministic_reply(
            user_id="default",
            user_message=msg,
            manifest=focal_only,
            response_locale="zh",
        )
        _assert(det, "T4 expected deterministic insufficient reply")
        _assert("对照历史不足" in det or "暂不作" in det, det)
        _assert("上升" in det and "下降" in det, det)
        for ban in ("上升了", "下降了", "趋于稳定"):
            _assert(ban not in det, f"T4 must not claim direction: {ban}")

        skip = evaluate_skip_llm_path(
            plan=plan,
            user_id="default",
            msg=msg,
            raw_user_msg=msg,
            prior_user_msg="",
            numerics_manifest=focal_only,
            response_locale="zh",
            wearable_screenshot_review=False,
            attachment_asset_qa=False,
            parsed_payload=None,
            qa_mode="",
            paths_in=[],
            wearable_compare_table_obj=None,
            episodic=None,
        )
        _assert(skip.skip_llm, "T4 skip_llm must be True")
        _assert("对照" in (skip.answer_text or ""), skip.answer_text)

    tpl = build_compare_insufficient_answer(focal_only, locale="zh")
    _assert("HRV" in tpl or "42" in tpl, tpl)


def test_t5_point_lookup_no_forced_compare() -> None:
    from pha.chat_trend_compare import is_trend_compare_turn
    from pha.numerics_manifest import build_numerics_manifest

    msg = "昨天深睡多少"
    _assert(not is_trend_compare_turn(msg, user_id="default"), "T5 must not hit trend_compare")
    m = build_numerics_manifest(
        "default",
        profile="wearable_only",
        user_message=msg,
        include_lipid=False,
        include_wearable=True,
    )
    compare = [e for e in m.entries if (e.source or "").startswith("wearable.trend_compare")]
    _assert(not compare, f"T5 must not force compare atoms: {compare}")


def test_broad_compare_anti_does_not_hijack() -> None:
    from pha.chat_trend_compare import is_trend_compare_turn

    msg = "各项指标是否正常"
    _assert(not is_trend_compare_turn(msg, user_id="default"), msg)


def test_flag_off() -> None:
    from pha import chat_trend_compare as mod
    from pha.numerics_manifest import build_numerics_manifest

    prev = os.environ.get("PHA_CHAT_TREND_COMPARE")
    os.environ["PHA_CHAT_TREND_COMPARE"] = "0"
    try:
        msg = "最近一周我的HRV有什么变化？"
        _assert(not mod.is_trend_compare_turn(msg), "flag off")
        m = build_numerics_manifest(
            "default",
            profile="wearable_only",
            user_message=msg,
            include_lipid=False,
            include_wearable=True,
        )
        compare = [e for e in m.entries if (e.source or "").startswith("wearable.trend_compare")]
        _assert(not compare, compare)
    finally:
        if prev is None:
            os.environ.pop("PHA_CHAT_TREND_COMPARE", None)
        else:
            os.environ["PHA_CHAT_TREND_COMPARE"] = prev


def main() -> None:
    test_t1_trend_hits_and_manifest_has_compare()
    test_t2_rhr_14d_task_and_compare()
    test_t4_compare_insufficient_skip()
    test_t5_point_lookup_no_forced_compare()
    test_broad_compare_anti_does_not_hijack()
    test_flag_off()
    print("pha_chat_trend_compare_selfcheck: PASS")


if __name__ == "__main__":
    main()

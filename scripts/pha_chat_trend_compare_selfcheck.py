#!/usr/bin/env python3
"""M1-P23: chat trend_compare intent + Manifest compare atoms (T1 / T5)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_HEALTH_INTENT_CATALOG", "1")
os.environ.setdefault("PHA_CHAT_TREND_COMPARE", "1")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_t1_trend_hits_and_manifest_has_compare() -> None:
    from pha.chat_trend_compare import is_trend_compare_turn
    from pha.grounded_answer_composer import is_warehouse_metric_focus_turn
    from pha.health_intent_catalog import load_health_intent_catalog
    from pha.numerics_manifest import build_numerics_manifest, format_manifest_tier0_block

    load_health_intent_catalog.cache_clear()  # type: ignore[attr-defined]

    msg = "最近一周我的HRV和深睡的数据有什么变化？"
    _assert(is_trend_compare_turn(msg, user_id="default"), "T1 must hit trend_compare")
    _assert(
        not is_warehouse_metric_focus_turn(msg, user_id="default"),
        "T1 must not warehouse-skip",
    )

    m = build_numerics_manifest(
        "default",
        profile="wearable_only",
        user_message=msg,
        include_lipid=False,
        include_wearable=True,
    )
    compare = [e for e in m.entries if (e.source or "").startswith("wearable.trend_compare")]
    focal = [e for e in m.entries if e.source in ("wearable.summary", "wearable.daily")]
    _assert(len(focal) >= 1, f"T1 focal entries missing: {m.entries!r}")
    # With real default ledger history, compare atoms should exist for HRV/deep.
    _assert(
        len(compare) >= 2,
        f"T1 expected compare atoms (mean+n), got {compare!r} entries={m.entries!r}",
    )
    _assert("7" in m.window_day_tokens or "90" in m.window_day_tokens, m.window_day_tokens)

    block = format_manifest_tier0_block(m, profile="wearable_only")
    for e in compare[:4]:
        _assert(e.kv_line() in block or e.metric.split("·")[0] in block, f"truncated dropped {e}")


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
    test_t5_point_lookup_no_forced_compare()
    test_broad_compare_anti_does_not_hijack()
    test_flag_off()
    print("pha_chat_trend_compare_selfcheck: PASS")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""M1-P21b: registry-driven daily rollup for zip passthrough samples; named recovery exclusive."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASK = "查询可穿戴库里的 Cardio recovery"
HK = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_registry_not_importer_hardcode() -> None:
    from pha.data_importer import _SUPPORTED_RECORD_TYPES
    from pha.wearable_metric_registry import (
        l1_field_for,
        metric_entry,
        zip_passthrough_rollups,
    )

    _assert(HK not in _SUPPORTED_RECORD_TYPES, _SUPPORTED_RECORD_TYPES)
    spec = zip_passthrough_rollups().get(HK)
    _assert(spec == ("cardio_recovery_1min_bpm", "max"), spec)
    entry = metric_entry("cardio_recovery_1min_bpm") or {}
    fc = entry.get("fact_card") or {}
    _assert(fc.get("eligible") is True, fc)
    _assert(fc.get("enabled_default") is False, fc)
    _assert(not fc.get("reference_range"), fc)
    _assert(str(fc.get("shortcut_skip_reason") or ""), fc)
    _assert(not str(fc.get("shortcut_health_type") or ""), fc)
    _assert(l1_field_for("cardio_recovery_1min_bpm") == "cardio_recovery_1min_bpm", "l1 field")
    cat = entry.get("catalog") or {}
    _assert(cat.get("key") == "cardio_recovery", cat)
    _assert(cat.get("cluster") != "hrv" and cat.get("cluster") != "vo2max", cat)
    print("OK registry promotion; importer allow-set unchanged")


def test_named_exclusive() -> None:
    from pha.goal_classifier import classify_goal
    from pha.health_intent_catalog import classify_outline_mode, infer_metrics_from_message
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.numerics_manifest import build_numerics_manifest

    ids = infer_wearable_metric_ids(ASK)
    _assert(ids == ["cardio_recovery_1min_bpm"], ids)
    _assert("hrv_sdnn_ms" not in ids and "vo2max" not in ids, ids)
    _assert(infer_metrics_from_message(ASK) == ["cardio_recovery"], infer_metrics_from_message(ASK))
    _assert(
        infer_metrics_from_message("有氧恢复怎么样") == ["cardio_recovery"],
        infer_metrics_from_message("有氧恢复怎么样"),
    )
    _assert(
        infer_wearable_metric_ids("一分钟心率恢复") == ["cardio_recovery_1min_bpm"],
        infer_wearable_metric_ids("一分钟心率恢复"),
    )
    _assert(classify_goal(ASK).goal_class != "daily_readiness", classify_goal(ASK))
    _assert(classify_outline_mode(ASK) == "exclusive", classify_outline_mode(ASK))
    man = build_numerics_manifest(
        "p21b-selfcheck",
        profile="wearable_only",
        user_message=ASK,
        include_lipid=False,
        include_wearable=True,
    )
    blob = " ".join(f"{e.metric} {e.value}" for e in (man.entries or [])).lower()
    _assert("hrv" not in blob, blob)
    _assert("vo2" not in blob, blob)
    print("OK named Cardio recovery exclusive; no HRV/VO2max")


def test_fact_card_checkbox_prefs() -> None:
    from pha.fact_card_prefs import load_enabled_metric_ids
    from pha.wearable_metric_registry import metric_entry

    ids, src = load_enabled_metric_ids("default")
    _assert("cardio_recovery_1min_bpm" in ids, (ids, src))
    fc = (metric_entry("cardio_recovery_1min_bpm") or {}).get("fact_card") or {}
    _assert(fc.get("eligible") is True, fc)
    _assert(fc.get("enabled_default") is False, fc)
    print("OK default prefs include cardio recovery checkbox")


def main() -> int:
    test_registry_not_importer_hardcode()
    test_named_exclusive()
    test_fact_card_checkbox_prefs()
    print("pha_p21b_cardio_recovery_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

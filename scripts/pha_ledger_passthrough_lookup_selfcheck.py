#!/usr/bin/env python3
"""Runtime catalog → L0 ledger → Manifest (or fail-closed). No per-ask promotion PR."""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HK_STEADINESS = "HKQuantityTypeIdentifierAppleWalkingSteadiness"
HK_STAIR = "HKQuantityTypeIdentifierStairAscentSpeed"
ASK_STEADINESS = "查询可穿戴库里的 walking steadiness"
ASK_STEADINESS_ZH = "查询可穿戴库里的 步行稳定性"
ASK_L0 = "查询可穿戴库里的 Stair Ascent Speed"
ASK_MISS = "查询可穿戴库里的 台阶上升速度"
ASK_CARDIO = "查询可穿戴库里的 Cardio recovery"
UID = "p21-ledger-selfcheck"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _zip_from_xml(xml: bytes) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.xml", xml)
    buf.seek(0)
    return buf


def test_needles_are_derived_not_a_name_table() -> None:
    from pha.data_importer import _SUPPORTED_RECORD_TYPES
    from pha.ledger_passthrough_lookup import hk_quantity_display_label, hk_quantity_needles

    lookup_src = (ROOT / "pha" / "ledger_passthrough_lookup.py").read_text(encoding="utf-8")
    _assert("WalkingSteadiness" not in lookup_src, "no type name table in lookup module")
    _assert("cardio_recovery" not in lookup_src, lookup_src)
    _assert(HK_STEADINESS not in _SUPPORTED_RECORD_TYPES, _SUPPORTED_RECORD_TYPES)
    needles = hk_quantity_needles(HK_STEADINESS)
    _assert("Walking Steadiness" in needles, needles)
    _assert("Steadiness" not in needles, needles)
    _assert(
        hk_quantity_display_label(HK_STEADINESS) == "Apple Walking Steadiness",
        hk_quantity_display_label(HK_STEADINESS),
    )
    print("OK derived needles; importer allow-set unchanged")


def test_import_and_named_lookup(tmp_db: Path) -> None:
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from pha.data_importer import AppleHealthParser
    from pha.goal_classifier import classify_goal
    from pha.grounded_answer_composer import is_warehouse_metric_focus_turn
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.ledger_passthrough_lookup import match_ledger_passthrough_types, resolve_turn_wearable_scope
    from pha.numerics_manifest import build_numerics_manifest

    old_db = st.DEFAULT_DB_PATH
    st.DEFAULT_DB_PATH = tmp_db
    tls = getattr(sc._thread_local, "conn", None)
    if tls is not None:
        try:
            tls.close()
        except Exception:
            pass
    sc.reset_schema_state_for_tests()
    st.init_schema()

    try:
        xml = (ROOT / "tests/fixtures/wearable/p21a_passthrough_export.xml").read_bytes()
        parser = AppleHealthParser(UID)
        parser.parse_export_zip(_zip_from_xml(xml), filename="p21-ledger.zip", clear_before_import=True)

        hit = match_ledger_passthrough_types(UID, ASK_L0)
        _assert(hit == (HK_STAIR,), hit)
        _assert(match_ledger_passthrough_types(UID, ASK_MISS) == (), ASK_MISS)
        _assert(match_ledger_passthrough_types(UID, ASK_STEADINESS) == (), "promoted steadiness stays on catalog")
        hit_scope = resolve_turn_wearable_scope(UID, ASK_L0)
        _assert(hit_scope.ledger_types == (HK_STAIR,), hit_scope)
        _assert(not hit_scope.registry_ids, hit_scope)
        hrv_scope = resolve_turn_wearable_scope(UID, "我最近的 HRV 怎么样？")
        _assert(hrv_scope.registry_ids and not hrv_scope.fail_closed_named, hrv_scope)
        _assert(any("hrv" in mid for mid in hrv_scope.registry_ids), hrv_scope)
        compare = resolve_turn_wearable_scope(UID, "今天的HRV跟昨天的相比，有什么变化")
        _assert(compare.registry_ids and not compare.fail_closed_named, compare)
        _assert(any("hrv" in mid for mid in compare.registry_ids), compare)
        _assert(bool(compare.unresolved_residue), compare)
        _assert(
            infer_wearable_metric_ids(ASK_CARDIO) == ["cardio_recovery_1min_bpm"],
            infer_wearable_metric_ids(ASK_CARDIO),
        )
        _assert(
            infer_wearable_metric_ids(ASK_STEADINESS) == ["walking_steadiness"],
            infer_wearable_metric_ids(ASK_STEADINESS),
        )
        _assert(
            infer_wearable_metric_ids(ASK_STEADINESS_ZH) == ["walking_steadiness"],
            infer_wearable_metric_ids(ASK_STEADINESS_ZH),
        )
        _assert(match_ledger_passthrough_types(UID, ASK_CARDIO) == (), "promoted types stay on catalog")

        man = build_numerics_manifest(
            UID,
            profile="wearable_only",
            user_message=ASK_L0,
            include_lipid=False,
            include_wearable=True,
        )
        blob = " ".join(f"{e.metric} {e.value}" for e in (man.entries or [])).lower()
        _assert("0.41" in blob, blob)
        _assert("stair ascent" in blob, blob)
        _assert("hrv" not in blob, blob)
        _assert("vo2" not in blob, blob)
        _assert("51.5" not in blob, blob)
        _assert(classify_goal(ASK_L0, user_id=UID).goal_class == "metric_specific", classify_goal(ASK_L0, user_id=UID))
        _assert(is_warehouse_metric_focus_turn(ASK_L0, user_id=UID), "warehouse focus")

        miss = build_numerics_manifest(
            UID,
            profile="wearable_only",
            user_message=ASK_MISS,
            include_lipid=False,
            include_wearable=True,
        )
        miss_blob = " ".join(
            f"{e.metric} {e.value}" for e in (miss.entries or []) if e.value is not None
        ).lower()
        _assert(miss.entries == [] or all(e.value is None for e in miss.entries), miss_blob)
        _assert("hrv" not in miss_blob and "0.41" not in miss_blob, miss_blob)
        _assert("51.5" not in miss_blob, miss_blob)
        print("OK ledger hit cites sample; promoted steadiness on catalog; Chinese miss fail-closed; no HRV pad")
    finally:
        tls = getattr(sc._thread_local, "conn", None)
        if tls is not None:
            try:
                tls.close()
            except Exception:
                pass
        st.DEFAULT_DB_PATH = old_db
        sc.reset_schema_state_for_tests()


def main() -> int:
    test_needles_are_derived_not_a_name_table()
    with tempfile.TemporaryDirectory() as raw:
        test_import_and_named_lookup(Path(raw) / "pha_storage.db")
    print("pha_ledger_passthrough_lookup_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

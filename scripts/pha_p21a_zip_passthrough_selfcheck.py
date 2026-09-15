#!/usr/bin/env python3
"""M1-P21a: unknown zip quantity Records land as-is; named Cardio Recovery fail-closed."""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HK_RECOVERY = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"
ASK = "查询可穿戴库里的 Cardio recovery"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _zip_from_xml(xml: bytes) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.xml", xml)
    buf.seek(0)
    return buf


def test_import_passthrough(tmp_db: Path) -> None:
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from pha.data_importer import AppleHealthParser
    from pha.sqlite_storage import METRIC_VO2MAX, query_wearable_daily_range, query_wearable_data_range

    uid = "p21a-selfcheck"
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
        parser = AppleHealthParser(uid)
        parser.parse_export_zip(_zip_from_xml(xml), filename="p21a.zip", clear_before_import=True)

        rec = query_wearable_data_range(uid, HK_RECOVERY, date(2026, 3, 1), date(2026, 3, 3))
        _assert(len(rec) == 1, rec)
        _assert(abs(rec[0][1] - 32.0) < 1e-6, rec)

        vo2 = query_wearable_data_range(uid, METRIC_VO2MAX, date(2026, 3, 1), date(2026, 3, 3))
        _assert(len(vo2) == 1, vo2)
        leaked = query_wearable_data_range(
            uid,
            "HKQuantityTypeIdentifierVO2Max",
            date(2026, 3, 1),
            date(2026, 3, 3),
        )
        _assert(leaked == [], leaked)

        daily = query_wearable_daily_range(uid, date(2026, 3, 1), date(2026, 3, 3))
        vo2_on_daily = False
        rec_daily = None
        for row in daily:
            vo2v = getattr(row, "vo2max_ml_kg_min", None)
            if vo2v not in (None, 0, 0.0):
                vo2_on_daily = True
            cr = getattr(row, "cardio_recovery_1min_bpm", None)
            if cr is not None:
                rec_daily = cr
        _assert(vo2_on_daily, daily)
        _assert(rec_daily is not None and abs(float(rec_daily) - 32.0) < 1e-6, rec_daily)

        parser.parse_export_zip(_zip_from_xml(xml), filename="p21a.zip", clear_before_import=False)
        rec2 = query_wearable_data_range(uid, HK_RECOVERY, date(2026, 3, 1), date(2026, 3, 3))
        _assert(len(rec2) == 1, rec2)
        print("OK zip passthrough + no double-write + idempotent")
    finally:
        tls = getattr(sc._thread_local, "conn", None)
        if tls is not None:
            try:
                tls.close()
            except Exception:
                pass
        st.DEFAULT_DB_PATH = old_db
        sc.reset_schema_state_for_tests()


def test_fail_closed_named() -> None:
    from pha.goal_classifier import classify_goal
    from pha.health_intent_catalog import classify_outline_mode, infer_metrics_from_message
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.numerics_manifest import build_numerics_manifest

    ids = infer_wearable_metric_ids(ASK)
    _assert(ids == ["cardio_recovery_1min_bpm"], ids)
    _assert(infer_metrics_from_message(ASK) == ["cardio_recovery"], infer_metrics_from_message(ASK))
    goal = classify_goal(ASK)
    _assert(goal.goal_class != "daily_readiness", goal)
    _assert(classify_outline_mode(ASK) == "exclusive", classify_outline_mode(ASK))
    man = build_numerics_manifest(
        "p21a-selfcheck",
        profile="wearable_only",
        user_message=ASK,
        include_lipid=False,
        include_wearable=True,
    )
    blob = " ".join(
        f"{e.metric} {e.value}" for e in (man.entries or []) if e.value is not None
    ).lower()
    _assert("hrv" not in blob, blob)
    _assert("vo2" not in blob, blob)
    _assert("51.5" not in blob and "37.6" not in blob, blob)
    print("OK named Cardio recovery exclusive (no HRV/VO2max padding)")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        test_import_passthrough(Path(raw) / "pha_storage.db")
    test_fail_closed_named()
    print("pha_p21a_zip_passthrough_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

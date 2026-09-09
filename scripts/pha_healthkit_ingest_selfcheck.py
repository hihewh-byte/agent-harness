#!/usr/bin/env python3
"""M0-P0 selfcheck: POST /ingest/healthkit writes fake samples into a temp SQLite DB."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOKEN = "selfcheck-ingest-token-m0"
TZ = "Asia/Shanghai"
DAY = date(2026, 8, 30)


def _bind_temp_db() -> Path:
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st

    tmp = Path(tempfile.mkdtemp(prefix="pha-hk-ingest-"))
    db = tmp / "pha_storage.db"
    st.DEFAULT_DB_PATH = db
    old = getattr(sc._thread_local, "conn", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    sc.reset_schema_state_for_tests()
    st.init_schema()
    return db


def _load_fixture() -> dict:
    path = ROOT / "scripts" / "fixtures" / "healthkit_ingest_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from pha.healthkit_ingest import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_token_gates(client) -> bool:
    os.environ.pop("PHA_INGEST_TOKEN", None)
    r = client.post("/ingest/healthkit", json={"user_id": "selfcheck", "samples": []})
    if r.status_code != 503:
        print("FAIL expected 503 when token unset, got", r.status_code, r.text)
        return False

    os.environ["PHA_INGEST_TOKEN"] = TOKEN
    r = client.post(
        "/ingest/healthkit",
        json={"user_id": "selfcheck", "token": "wrong", "samples": []},
    )
    if r.status_code != 401:
        print("FAIL expected 401 on bad token, got", r.status_code, r.text)
        return False
    print("OK token fail-closed (503 unset / 401 wrong)")
    return True


def test_malformed_drops_batch(client, db: Path) -> bool:
    from pha.sqlite_storage import count_wearable_samples

    before = count_wearable_samples("selfcheck")
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "hrv",
                    "timestamp": "not-a-timestamp",
                    "value": 40,
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 400:
        print("FAIL expected 400 malformed, got", r.status_code, r.text)
        return False
    after = count_wearable_samples("selfcheck")
    if after != before:
        print("FAIL malformed batch wrote rows", before, after)
        return False
    if db.resolve() == (ROOT / "data" / "pha_storage.db").resolve():
        print("FAIL selfcheck bound production DB", db)
        return False
    print("OK malformed timestamp fail-closed, temp DB isolated")
    return True


def test_happy_path_and_idempotent(client) -> bool:
    from pha.sqlite_storage import (
        count_wearable_samples,
        query_wearable_daily_range,
    )

    fixture = _load_fixture()
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json=fixture,
    )
    if r.status_code != 200:
        print("FAIL ingest 200 expected, got", r.status_code, r.text)
        return False
    body = r.json()
    if body.get("inserted") != 5 or body.get("source") != "healthkit":
        print("FAIL first ingest body", body)
        return False

    n = count_wearable_samples("selfcheck")
    if n < 5:
        print("FAIL wearable_data sample count", n)
        return False

    rows = query_wearable_daily_range("selfcheck", DAY, DAY)
    if len(rows) != 1:
        print("FAIL daily rows", rows)
        return False
    row = rows[0]
    if row.hrv_sdnn_ms != 42.0:
        print("FAIL daily hrv_sdnn", row.hrv_sdnn_ms)
        return False
    if row.hrv_rmssd_ms is not None:
        print("FAIL legacy hrv key must write SDNN column only", row.hrv_rmssd_ms)
        return False
    if row.resting_heart_rate_bpm != 54.0:
        print("FAIL daily rhr", row.resting_heart_rate_bpm)
        return False
    if row.steps != 8123:
        print("FAIL daily steps", row.steps)
        return False
    if row.sleep_hours != 7.25:
        print("FAIL daily sleep_hours", row.sleep_hours)
        return False
    if row.active_energy_kcal != 410.0:
        print("FAIL daily active_energy", row.active_energy_kcal)
        return False

    from pha.health_data import get_health_data

    hd = get_health_data(
        "selfcheck",
        DAY,
        DAY,
        ["hrv", "steps", "sleep", "rhr", "activity_kcal"],
    )
    if hd.row_count != 1 or not hd.metrics_supported:
        print("FAIL get_health_data row_count", hd)
        return False
    hrv_avg = None
    if "hrv_sdnn_ms" in hd.summaries:
        hrv_avg = hd.summaries["hrv_sdnn_ms"].average
    else:
        for mid, ckey in (hd.catalog_key_of or {}).items():
            if ckey == "hrv" and mid in hd.summaries:
                hrv_avg = hd.summaries[mid].average
                break
    if hrv_avg != 42.0:
        print("FAIL get_health_data hrv", hd.summaries)
        return False

    again = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json=fixture,
    )
    if again.status_code != 200:
        print("FAIL idempotent ingest", again.status_code, again.text)
        return False
    again_body = again.json()
    if again_body.get("inserted") != 0 or again_body.get("ignored") != 5:
        print("FAIL idempotent counts", again_body)
        return False
    rows2 = query_wearable_daily_range("selfcheck", DAY, DAY)
    if rows2[0].active_energy_kcal != 410.0:
        print("FAIL energy doubled after rebuild", rows2[0].active_energy_kcal)
        return False
    print("OK ingest → wearable_data + wearable_daily; idempotent; no energy double-count")
    return True


def test_energy_daily_key_replaces(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "energy_replace"
    first = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "active_energy",
                    "timestamp": "2026-08-30T10:00:00+08:00",
                    "value": 410.0,
                    "unit": "kcal",
                    "source": "healthkit",
                }
            ],
        },
    )
    second = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "active_energy",
                    "timestamp": "2026-08-30T21:00:00+08:00",
                    "value": 200.0,
                    "unit": "kcal",
                    "source": "healthkit",
                }
            ],
        },
    )
    if first.status_code != 200 or second.status_code != 200:
        print("FAIL energy daily replace status", first.status_code, second.status_code)
        return False
    rows = query_wearable_daily_range(uid, DAY, DAY)
    if not rows or rows[0].active_energy_kcal != 200.0:
        print("FAIL energy must replace same-day total, got", rows)
        return False
    print("OK active_energy daily key replaces (no sum of two POSTs)")
    return True


def test_hrv_sdnn_does_not_write_rmssd(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "hrv_sdnn_only"
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "hrv_sdnn",
                    "timestamp": "2026-08-30T07:00:00+08:00",
                    "value": 38.4,
                    "unit": "ms",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL hrv_sdnn status", r.status_code, r.text)
        return False
    alias = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "heartRateVariabilitySDNN",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 40.0,
                    "unit": "ms",
                    "source": "healthkit",
                }
            ],
        },
    )
    if alias.status_code != 200:
        print("FAIL sdnn alias status", alias.status_code, alias.text)
        return False
    rows = query_wearable_daily_range(uid, DAY, DAY)
    if not rows:
        print("FAIL hrv_sdnn missing daily row")
        return False
    if rows[0].hrv_rmssd_ms is not None:
        print("FAIL SDNN leaked into RMSSD", rows[0].hrv_rmssd_ms)
        return False
    if rows[0].hrv_sdnn_ms != 40.0:
        print("FAIL daily key should replace SDNN mean, got", rows[0].hrv_sdnn_ms)
        return False
    print("OK hrv_sdnn writes hrv_sdnn_ms only")
    return True


def test_sleep_stages_sum_to_asleep(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_stages"
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "sleep_core",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 4.0,
                    "unit": "h",
                    "source": "healthkit",
                },
                {
                    "metric_type": "sleep_deep",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 1.5,
                    "unit": "h",
                    "source": "healthkit",
                },
                {
                    "metric_type": "sleep_rem",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 1.2,
                    "unit": "h",
                    "source": "healthkit",
                },
                {
                    "metric_type": "sleep_in_bed",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 8.0,
                    "unit": "h",
                    "source": "healthkit",
                },
                {
                    "metric_type": "sleep_awake",
                    "timestamp": "2026-08-30T08:00:00+08:00",
                    "value": 0.3,
                    "unit": "h",
                    "source": "healthkit",
                },
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL sleep stages status", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range(uid, DAY, DAY)
    if not rows:
        print("FAIL sleep stages missing daily")
        return False
    row = rows[0]
    if row.sleep_hours != 6.7:
        print("FAIL sleep_hours must be core+deep+rem, got", row.sleep_hours)
        return False
    if row.in_bed_hours != 8.0 or row.sleep_deep_hours != 1.5:
        print("FAIL stage columns", row.in_bed_hours, row.sleep_deep_hours)
        return False
    if row.awake_duration_hours != 0.3:
        print("FAIL awake", row.awake_duration_hours)
        return False
    bad = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "sleep_deep",
                    "timestamp": "2026-08-30T09:00:00+08:00",
                    "value": 20,
                    "unit": "h",
                    "source": "healthkit",
                }
            ],
        },
    )
    if bad.status_code != 400:
        print("FAIL hours>16 must 400, got", bad.status_code)
        return False
    secs = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "sleep_in_bed",
                    "timestamp": "2026-08-30T09:00:00+08:00",
                    "value": 30960,
                    "unit": "s",
                    "source": "healthkit",
                }
            ],
        },
    )
    if secs.status_code != 200:
        print("FAIL sleep seconds coerce status", secs.status_code, secs.text)
        return False
    rows = query_wearable_daily_range(uid, DAY, DAY)
    if not rows or abs(float(rows[0].in_bed_hours) - 8.6) > 0.01:
        print("FAIL Duration seconds should become hours, got", rows[0].in_bed_hours if rows else None)
        return False
    print("OK sleep stages sum to asleep hours; seconds coerced; implausible rejected")
    return True


def test_unknown_metric_dropped(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "not_a_real_metric",
                    "timestamp": "2026-08-30T12:00:00+08:00",
                    "value": 40,
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL unknown metric should drop not 400, got", r.status_code, r.text)
        return False
    if r.json().get("dropped") != 1 or r.json().get("inserted") != 0:
        print("FAIL unknown metric body", r.json())
        return False
    print("OK unknown metric dropped (not invented)")
    return True


def test_shortcuts_quantity_string(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-09-04T00:02:00+08:00",
                    "value": "16 count",
                    "unit": "count",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL shortcuts quantity string", r.status_code, r.text)
        return False
    if r.json().get("inserted") != 1:
        print("FAIL shortcuts quantity inserted", r.json())
        return False
    print("OK coerce Shortcuts value '16 count'")
    return True


def test_steps_sums_multiple_numbers(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-08-29T12:00:00+08:00",
                    "value": "10 count\n20 count\n5",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL steps sum string", r.status_code, r.text)
        return False
    from pha.sqlite_storage import query_wearable_daily_range
    from datetime import date as date_cls

    day = date_cls(2026, 8, 29)
    rows = query_wearable_daily_range("selfcheck", day, day)
    if not rows or rows[0].steps != 35:
        print("FAIL steps sum daily", rows)
        return False
    print("OK steps value string sums to daily total")
    return True


def test_newline_json_uses_leading_total(client) -> bool:
    raw = (
        b'{"user_id":"selfcheck","samples":[{"metric_type":"steps","timestamp":'
        b'"2026-08-28T12:00:00+08:00","value":"11259 16\n2\n6","source":"healthkit"}]}'
    )
    r = client.post(
        "/ingest/healthkit",
        headers={
            "X-PHA-Ingest-Token": TOKEN,
            "Content-Type": "application/json",
        },
        content=raw,
    )
    if r.status_code != 200:
        print("FAIL newline json", r.status_code, r.text)
        return False
    from datetime import date as date_cls

    from pha.sqlite_storage import query_wearable_daily_range

    day = date_cls(2026, 8, 28)
    rows = query_wearable_daily_range("selfcheck", day, day)
    if not rows or rows[0].steps != 11259:
        print("FAIL newline json daily", rows)
        return False
    print("OK newline JSON salvaged; leading total kept")
    return True


def test_quantity_dict_magnitude(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-09-04T11:00:00+08:00",
                    "value": {"Magnitude": "42", "Unit": "count"},
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200 or r.json().get("inserted") != 1:
        print("FAIL quantity dict", r.status_code, r.text)
        return False
    print("OK coerce value Magnitude dict")
    return True


def test_object_replacement_char_fail_closed(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-09-04T11:00:00+08:00",
                    "value": "\ufffc",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 400:
        print("FAIL object replacement should 400", r.status_code, r.text)
        return False
    body = r.json()
    detail = body.get("detail") if isinstance(body, dict) else None
    err = detail.get("error") if isinstance(detail, dict) else None
    if err != "unreadable_value":
        print("FAIL object replacement detail", body)
        return False
    print("OK U+FFFC value fail-closed")
    return True


def test_empty_sample_receipt(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "rhr",
                    "timestamp": "",
                    "value": "",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 400:
        print("FAIL empty sample should 400", r.status_code, r.text)
        return False
    body = r.json()
    detail = body.get("detail") if isinstance(body, dict) else None
    err = detail.get("error") if isinstance(detail, dict) else None
    if err != "empty_sample":
        print("FAIL empty sample detail", body)
        return False
    print("OK empty sample is empty_sample not unreadable_value")
    return True


def test_quantity_shortcut_p10_p11() -> bool:
    sys.path.insert(0, str(ROOT / "scripts" / "macos"))
    from build_pha_ingest_shortcuts import build_health
    from pha.healthkit_sync_plan import shortcut_sync_specs

    specs = shortcut_sync_specs("anyone")
    ids = {s.metric_id for s in specs}
    expected = {
        "steps",
        "active_energy",
        "hrv_sdnn_ms",
        "resting_heart_rate_bpm",
        "spo2_percent",
        "respiratory_rate",
        "vo2max",
    }
    if ids != expected:
        print("FAIL quantity universe size", [s.metric_id for s in specs])
        return False
    from pha.wearable_metric_registry import shortcut_pack_version

    pack = shortcut_pack_version()
    wf = build_health("http://example.local:8788/ingest/healthkit", "t", specs, pack_version=pack)
    finds = [
        a
        for a in wf["WFWorkflowActions"]
        if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.filter.health.quantity"
    ]
    if len(finds) != 7:
        print("FAIL expected 7 quantity Finds", len(finds))
        return False
    blob = str(wf)
    if pack not in blob or "Oxygen Saturation" not in blob or "VO2 Max" not in blob:
        print("FAIL pack_version or new Find labels missing")
        return False
    forbidden = (
        "Blood Oxygen",
        "Apple Sleeping Wrist Temperature",
        "Active Energy",
        "Wrist Temperature",
        "Cardio Fitness",
    )
    for label in forbidden:
        if label in blob:
            print(f"FAIL forbidden Find label in shortcut: {label}")
            return False
    conds = [
        a
        for a in wf["WFWorkflowActions"]
        if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.conditional"
    ]
    if len(conds) < 14:
        print("FAIL each quantity Find should have If/EndIf", len(conds))
        return False
    opens = [
        a
        for a in conds
        if a["WFWorkflowActionParameters"].get("WFControlFlowMode") == 0
    ]
    if len(opens) != 7:
        print("FAIL expected 7 If starts", len(opens))
        return False
    for op in opens:
        params = op["WFWorkflowActionParameters"]
        wf_in = params.get("WFInput") or {}
        if params.get("WFCondition") != 100:
            print("FAIL If must be has-any-value (100)", params)
            return False
        if wf_in.get("Type") != "Variable" or not isinstance(wf_in.get("Variable"), dict):
            print("FAIL If WFInput must wrap Type=Variable", wf_in)
            return False
    rhr = next(
        a
        for a in finds
        if any(
            t.get("Values", {}).get("Enumeration", {}).get("Value") == "Resting Heart Rate"
            for t in a["WFWorkflowActionParameters"]["WFContentItemFilter"]["Value"][
                "WFActionParameterFilterTemplates"
            ]
        )
    )
    params = rhr["WFWorkflowActionParameters"]
    templates = params["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"]
    last_n = [t for t in templates if t.get("Operator") == 1001]
    if not last_n or last_n[0].get("Values", {}).get("Number") != 2:
        print("FAIL RHR must last-2-days", templates)
        return False
    if params.get("WFContentItemLimitNumber") != 1:
        print("FAIL RHR must Limit 1 latest", params)
        return False
    props = [
        a["WFWorkflowActionParameters"].get("WFContentItemPropertyName")
        for a in wf["WFWorkflowActions"]
        if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.properties.health.quantity"
    ]
    if "Start Date" not in props:
        print("FAIL lagged metric must Get Details Start Date", props)
        return False
    if "Unit" in props:
        print("FAIL do not Get Details Unit from sample lists", props)
        return False
    blob = str(wf)
    if '"unit":"count"' not in blob or '"unit":"kcal"' not in blob:
        print("FAIL JSON must embed registry unit literals")
        return False
    if "is.workflow.actions.getitemfromlist" not in blob:
        print("FAIL overnight metrics must take First Item for Start Date")
        return False
    resp = next(
        a
        for a in finds
        if any(
            t.get("Values", {}).get("Enumeration", {}).get("Value") == "Respiratory Rate"
            for t in a["WFWorkflowActionParameters"]["WFContentItemFilter"]["Value"][
                "WFActionParameterFilterTemplates"
            ]
        )
    )
    if resp["WFWorkflowActionParameters"].get("WFContentItemLimitNumber") != 150:
        print("FAIL overnight Find must Limit 150", resp["WFWorkflowActionParameters"])
        return False
    print("OK quantity shortcut universe + RHR last-2-days + count skip")
    return True


def test_empty_value_hole_in_json(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={
            "X-PHA-Ingest-Token": TOKEN,
            "Content-Type": "application/json",
        },
        content=b'{"user_id":"selfcheck","samples":[{"metric_type":"steps","timestamp":"","value":,"unit":"count","source":"healthkit"}]}',
    )
    if r.status_code != 400 or "empty_value" not in r.text:
        print("FAIL empty value hole", r.status_code, r.text)
        return False
    print("OK empty value hole in JSON fail-closed")
    return True


def test_get_ingest_explains_post_only(client) -> bool:
    r = client.get("/ingest/healthkit")
    if r.status_code != 200:
        print("FAIL GET ingest status", r.status_code)
        return False
    body = r.json()
    if body.get("ok") is not False or body.get("error") != "use_post":
        print("FAIL GET ingest body", body)
        return False
    print("OK GET ingest explains POST-only")
    return True


def test_ingest_last_receipt(client) -> bool:
    from pha.healthkit_ingest_receipt import load_healthkit_ingest_last, receipt_path

    uid = "receipt_user"
    bad = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        content=b"PHA_SLEEP_V1\nuser_id=receipt_user\n---VALUES---\n\n---STARTS---\n\n---ENDS---\n",
    )
    if bad.status_code != 400:
        print("FAIL receipt expected 400", bad.status_code, bad.text)
        return False
    failed = load_healthkit_ingest_last(uid)
    if failed.get("ok") is not False or failed.get("error") != "sleep_stage_list_mismatch":
        print("FAIL receipt after 400", failed, "path", receipt_path())
        return False
    today = _local_today()
    start = _at(today, 2)
    end = _at(today, 6)
    good = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        content=(
            "PHA_SLEEP_V1\n"
            f"user_id={uid}\n"
            "---VALUES---\nCore\n---STARTS---\n"
            f"{start.isoformat()}\n---ENDS---\n{end.isoformat()}\n"
        ).encode("utf-8"),
    )
    if good.status_code != 200:
        print("FAIL receipt success post", good.status_code, good.text)
        return False
    got = client.get(
        f"/ingest/healthkit/last?user_id={uid}",
        headers={"X-PHA-Ingest-Token": TOKEN},
    )
    if got.status_code != 200:
        print("FAIL GET last status", got.status_code, got.text)
        return False
    body = got.json()
    if body.get("ok") is not True or body.get("kind") != "sleep":
        print("FAIL GET last body", body)
        return False
    if (body.get("audit") or {}).get("wake_day") != today.isoformat():
        print("FAIL GET last audit", body)
        return False
    print("OK ingest last receipt records fail then success")
    return True


def test_empty_timestamp_uses_received_at(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "",
                    "value": 99,
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL empty timestamp", r.status_code, r.text)
        return False
    if r.json().get("timestamp_defaulted") != 1 or r.json().get("inserted") != 1:
        print("FAIL empty timestamp body", r.json())
        return False
    print("OK empty timestamp defaults to received_at")
    return True


def test_zip_clear_preserves_healthkit(client) -> bool:
    from pha.sqlite_storage import (
        clear_wearable_storage,
        count_healthkit_samples,
        query_healthkit_days,
        query_wearable_daily_range,
        rebuild_wearable_daily_for_days,
    )

    before = count_healthkit_samples("selfcheck")
    if before < 1:
        print("FAIL preserve healthkit: no rows to keep")
        return False
    clear_wearable_storage("selfcheck", preserve_healthkit=True)
    after = count_healthkit_samples("selfcheck")
    if after != before:
        print("FAIL zip clear wiped healthkit", before, after)
        return False
    days = query_healthkit_days("selfcheck")
    if not days:
        print("FAIL query_healthkit_days empty after preserve")
        return False
    rebuild_wearable_daily_for_days("selfcheck", days)
    rows = query_wearable_daily_range("selfcheck", DAY, DAY)
    if not rows or rows[0].steps != 8123:
        print("FAIL rebuilt daily after preserve", rows)
        return False
    print("OK zip clear preserves healthkit rows + daily rebuild")
    return True


def test_priority_pack_units_and_zip_wins(client) -> bool:
    from pha.models import WearableDailySummary
    from pha.sqlite_storage import count_healthkit_samples, query_wearable_daily_range
    from pha.zip_healthkit_overlay import apply_zip_wins_overlay

    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "unitpack",
            "pack_version": "2026.09.08.priority-1",
            "samples": [
                {
                    "metric_type": "spo2",
                    "timestamp": "2026-08-30T04:00:00+08:00",
                    "value": 0.97,
                    "unit": "%",
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL spo2 fraction ingest", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range("unitpack", DAY, DAY)
    if not rows or rows[0].spo2_pct is None or abs(rows[0].spo2_pct - 97.0) > 0.05:
        print("FAIL spo2 stored percent", rows)
        return False
    bad = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "unitpack",
            "samples": [
                {
                    "metric_type": "spo2",
                    "timestamp": "2026-08-30T05:00:00+08:00",
                    "value": 97,
                    "unit": "stone",
                    "source": "healthkit",
                }
            ],
        },
    )
    if bad.status_code != 400:
        print("FAIL unknown unit must 400", bad.status_code, bad.text)
        return False
    glued = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "unitpack",
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-08-30T12:00:00+08:00",
                    "value": 100,
                    "unit": "count\ncount\ncount",
                    "source": "healthkit",
                }
            ],
        },
    )
    if glued.status_code != 200:
        print("FAIL concatenated unit should take first token", glued.status_code, glued.text)
        return False
    rr = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "unitpack",
            "samples": [
                {
                    "metric_type": "respiratory_rate",
                    "timestamp": "2026-08-30T04:10:00+08:00",
                    "value": 0.25,
                    "unit": "count/s",
                    "source": "healthkit",
                }
            ],
        },
    )
    if rr.status_code != 200:
        print("FAIL respiratory count/s", rr.status_code, rr.text)
        return False
    rows = query_wearable_daily_range("unitpack", DAY, DAY)
    if not rows or abs(float(rows[0].respiratory_rate_bpm or 0) - 15.0) > 0.05:
        print("FAIL respiratory stored bpm", rows)
        return False
    before = count_healthkit_samples("unitpack")
    overlay = apply_zip_wins_overlay(
        "unitpack",
        xml_max_dt=datetime(2026, 8, 30, 12, 0, 0),
        zip_rows=[
            WearableDailySummary(
                user_id="unitpack",
                day=DAY,
                spo2_pct=96.0,
                respiratory_rate_bpm=14.0,
            )
        ],
    )
    after = count_healthkit_samples("unitpack")
    if after >= before or overlay.get("healthkit_deleted", 0) < 1:
        print("FAIL zip overlay should drop overlapping healthkit", before, after, overlay)
        return False
    print("OK priority pack units + zip wins overlay")
    return True


def test_skip_llm_reads_healthkit_steps(client) -> bool:
    from pha.grounded_answer_composer import try_warehouse_metric_focus_skip

    uid = "skip_llm_hk"
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": "2026-08-30T21:00:00+08:00",
                    "value": 8123,
                    "source": "healthkit",
                }
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL skip-LLM ingest", r.status_code, r.text)
        return False
    answer = try_warehouse_metric_focus_skip(
        user_id=uid,
        profile="wearable_only",
        user_message="最近步数",
        manifest=None,
        response_locale="zh",
    )
    if "8123" not in (answer or ""):
        print("FAIL skip-LLM missing healthkit steps", answer)
        return False
    print("OK skip-LLM reads healthkit steps")
    return True


def test_time_grain_binds_time_anchor_slots() -> bool:
    from datetime import date as date_cls

    from pha.wearable_time_grain import resolve_wearable_time_grain

    ref = date_cls(2026, 9, 4)
    cases = [
        ("今天走了多少步？", ref, ref, "point", "time_slot"),
        ("昨天睡眠怎么样", date_cls(2026, 9, 3), date_cls(2026, 9, 3), "point", "time_slot"),
        ("近7天HRV", date_cls(2026, 8, 29), ref, "mean", "rolling_n"),
        ("过去7天的平均步数是多少？", date_cls(2026, 8, 29), ref, "mean", "rolling_n"),
        ("过去七天步数", date_cls(2026, 8, 29), ref, "mean", "rolling_n"),
        ("这个月步数", date_cls(2026, 9, 1), ref, "mean", "time_slot"),
        ("上个月HRV", date_cls(2026, 8, 1), date_cls(2026, 8, 31), "mean", "time_slot"),
        ("how many steps today", ref, ref, "point", "time_slot"),
        ("步数呢", date_cls(2026, 6, 7), ref, "mean", "default"),
        ("和上周比呢", date_cls(2026, 6, 7), ref, "mean", "default"),
    ]
    for msg, start, end, agg, source in cases:
        grain = resolve_wearable_time_grain(msg, reference=ref)
        if (
            grain.start != start
            or grain.end != end
            or grain.aggregation != agg
            or grain.source != source
        ):
            print("FAIL time grain", msg, grain)
            return False
    print("OK time-anchor slots bind wearable window (not catalog aliases)")
    return True


def test_skip_llm_time_grain_not_90d_mean(client) -> bool:
    from datetime import timedelta

    from pha.grounded_answer_composer import try_warehouse_metric_focus_skip
    from pha.health_data import effective_query_reference_date

    today = effective_query_reference_date()
    yesterday = today - timedelta(days=1)
    far = today - timedelta(days=20)
    uid = "skip_llm_grain"

    def _ingest(day, value: int) -> bool:
        r = client.post(
            "/ingest/healthkit",
            headers={"X-PHA-Ingest-Token": TOKEN},
            json={
                "user_id": uid,
                "samples": [
                    {
                        "metric_type": "steps",
                        "timestamp": f"{day.isoformat()}T12:00:00+08:00",
                        "value": value,
                        "source": "healthkit",
                    }
                ],
            },
        )
        return r.status_code == 200

    if not _ingest(far, 1000) or not _ingest(yesterday, 7777) or not _ingest(today, 11259):
        print("FAIL time-grain ingest")
        return False

    today_ans = try_warehouse_metric_focus_skip(
        user_id=uid,
        profile="wearable_only",
        user_message="今天走了多少步？",
        manifest=None,
        response_locale="zh",
    ) or ""
    if "11259" not in today_ans or "7777" in today_ans or "1000" in today_ans:
        print("FAIL today-steps used other days", today_ans)
        return False
    if "近 90 天" in today_ans or "步数均值" in today_ans:
        print("FAIL today-steps still labeled as 90d mean", today_ans)
        return False

    yday_ans = try_warehouse_metric_focus_skip(
        user_id=uid,
        profile="wearable_only",
        user_message="昨天走了多少步",
        manifest=None,
        response_locale="zh",
    ) or ""
    if "7777" not in yday_ans or "11259" in yday_ans:
        print("FAIL yesterday-steps", yday_ans)
        return False

    week_ans = try_warehouse_metric_focus_skip(
        user_id=uid,
        profile="wearable_only",
        user_message="过去7天的平均步数是多少？",
        manifest=None,
        response_locale="zh",
    ) or ""
    if "1000" in week_ans or "8975" in week_ans or "近 90 天" in week_ans:
        print("FAIL 过去7天 still used 90d mean", week_ans)
        return False
    if "步数均值" not in week_ans:
        print("FAIL 过去7天 should be window mean", week_ans)
        return False

    missing_uid = "skip_llm_missing_yday"
    missing_resp = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": missing_uid,
            "samples": [
                {
                    "metric_type": "steps",
                    "timestamp": f"{today.isoformat()}T12:00:00+08:00",
                    "value": 11259,
                    "source": "healthkit",
                }
            ],
        },
    )
    if missing_resp.status_code != 200:
        print("FAIL missing-yday ingest", missing_resp.status_code, missing_resp.text)
        return False
    missing = try_warehouse_metric_focus_skip(
        user_id=missing_uid,
        profile="wearable_only",
        user_message="昨天步数是多少",
        manifest=None,
        response_locale="zh",
    ) or ""
    if "11259" in missing or "14808" in missing or not missing:
        print("FAIL missing yesterday must fail-closed", missing)
        return False
    if "没有" not in missing:
        print("FAIL missing yesterday wording", missing)
        return False

    mean_ans = try_warehouse_metric_focus_skip(
        user_id=uid,
        profile="wearable_only",
        user_message="步数呢",
        manifest=None,
        response_locale="zh",
    ) or ""
    if "步数均值" not in mean_ans or "11259" in mean_ans:
        print("FAIL generic steps should stay 90d mean", mean_ans)
        return False
    print("OK skip-LLM time grain: today/yesterday/7d/90d")
    return True


def _local_today() -> date:
    return datetime.now(ZoneInfo(TZ)).replace(tzinfo=None).date()


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute))


def _audit_ok(payload: dict) -> bool:
    audit = payload.get("audit") or {}
    needed = (
        "kept",
        "skipped_zero",
        "dropped_unknown_label",
        "per_stage_h",
        "union_asleep_h",
        "session_span",
        "window",
        "stage_overlap",
    )
    return all(key in audit for key in needed)


def test_sleep_stage_bundle_last_24h(client) -> bool:
    from pha.sqlite_storage import query_sleep_segments_for_day, query_wearable_daily_range

    uid = "sleep_bundle"
    now = datetime.now(ZoneInfo(TZ)).replace(tzinfo=None, second=0, microsecond=0)
    wake = now.replace(hour=7, minute=30)
    if wake > now:
        wake = wake - timedelta(days=1)
    bed = wake - timedelta(hours=8, minutes=36)
    wake_day = wake.date()
    # One overlapping In Bed + non-overlapping stages that match Health 9/6.
    values = [
        "In Bed",
        "Asleep Core",
        "Asleep Deep",
        "Asleep REM",
        "Awake",
        "In Bed",
    ]
    starts = [
        bed.isoformat(),
        bed.isoformat(),
        (bed + timedelta(hours=4, minutes=36)).isoformat(),
        (bed + timedelta(hours=5, minutes=9)).isoformat(),
        (bed + timedelta(hours=6, minutes=45)).isoformat(),
        (bed - timedelta(days=1)).isoformat(),
    ]
    ends = [
        wake.isoformat(),
        (bed + timedelta(hours=4, minutes=36)).isoformat(),
        (bed + timedelta(hours=5, minutes=9)).isoformat(),
        (bed + timedelta(hours=6, minutes=45)).isoformat(),
        wake.isoformat(),
        (bed - timedelta(days=1) + timedelta(hours=8)).isoformat(),
    ]
    payload = {
        "user_id": uid,
        "sleep_values": values,
        "sleep_starts": starts,
        "sleep_ends": ends,
    }
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json=payload,
    )
    if r.status_code != 200:
        print("FAIL sleep bundle status", r.status_code, r.text)
        return False
    body = r.json()
    if not _audit_ok(body):
        print("FAIL sleep bundle missing audit", body)
        return False
    if body["audit"].get("stage_overlap"):
        print("FAIL 9/6-style fixture should not overlap", body["audit"])
        return False
    rows = query_wearable_daily_range(uid, wake_day, wake_day)
    if not rows:
        print("FAIL sleep bundle missing daily")
        return False
    row = rows[0]
    if abs((row.in_bed_hours or 0) - 8.6) > 0.02:
        print("FAIL in_bed", row.in_bed_hours)
        return False
    if abs((row.sleep_hours or 0) - 6.75) > 0.02:
        print("FAIL sleep_hours", row.sleep_hours)
        return False
    if abs((row.sleep_core_hours or 0) - 4.6) > 0.02:
        print("FAIL core", row.sleep_core_hours)
        return False
    if abs((row.sleep_deep_hours or 0) - 0.55) > 0.02:
        print("FAIL deep", row.sleep_deep_hours)
        return False
    if abs((row.sleep_rem_hours or 0) - 1.6) > 0.02:
        print("FAIL rem", row.sleep_rem_hours)
        return False
    if abs((row.awake_duration_hours or 0) - 1.85) > 0.02:
        print("FAIL awake", row.awake_duration_hours)
        return False
    segs = query_sleep_segments_for_day(uid, wake_day)
    if len(segs) != 5:
        print("FAIL expected 5 kept segments, got", len(segs))
        return False
    again = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json=payload,
    )
    if again.status_code != 200:
        print("FAIL sleep bundle repeat status", again.status_code, again.text)
        return False
    segs2 = query_sleep_segments_for_day(uid, wake_day)
    if len(segs2) != len(segs):
        print("FAIL repeat POST not idempotent", len(segs), len(segs2))
        return False
    rows2 = query_wearable_daily_range(uid, wake_day, wake_day)
    if not rows2 or abs((rows2[0].sleep_hours or 0) - 6.75) > 0.02:
        print("FAIL repeat POST daily drifted", rows2[0].sleep_hours if rows2 else None)
        return False
    bad = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["In Bed", "Asleep Core"],
            "sleep_starts": [bed.isoformat()],
            "sleep_ends": [wake.isoformat()],
        },
    )
    if bad.status_code != 400 or bad.json().get("detail", {}).get("error") != "sleep_stage_list_mismatch":
        print("FAIL mismatch must be 400", bad.status_code, bad.text)
        return False
    print("OK sleep stage lists pair; wake-day noon window; previous night dropped; audit+segments")
    return True


def test_sleep_bundle_marker_text(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_bundle_text"
    today = _local_today()
    start = _at(today, 2)
    end = _at(today, 3)
    body = (
        "PHA_SLEEP_V1\n"
        f"user_id={uid}\n"
        "---VALUES---\n"
        "Asleep Deep\n"
        "---STARTS---\n"
        f"{start.isoformat()}\n"
        "---ENDS---\n"
        f"{end.isoformat()}\n"
    )
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        content=body.encode("utf-8"),
    )
    if r.status_code != 200:
        print("FAIL sleep marker status", r.status_code, r.text)
        return False
    if not _audit_ok(r.json()):
        print("FAIL sleep marker missing audit", r.json())
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows or abs((rows[0].sleep_deep_hours or 0) - 1.0) > 0.02:
        print("FAIL sleep marker daily", rows[0].sleep_deep_hours if rows else None)
        return False
    print("OK PHA_SLEEP_V1 marker text")
    return True


def test_sleep_bundle_optional_source_sections(client) -> bool:
    from pha.sqlite_storage import query_sleep_segments_for_day

    uid = "sleep_bundle_source"
    today = _local_today()
    start = _at(today, 2)
    end = _at(today, 6)
    body = (
        "PHA_SLEEP_V1\n"
        f"user_id={uid}\n"
        "---VALUES---\n"
        "Core\n"
        "---STARTS---\n"
        f"{start.isoformat()}\n"
        "---ENDS---\n"
        f"{end.isoformat()}\n"
        "---SOURCES---\n"
        "文辉的 Apple Watch\n"
        "---DEVICES---\n"
        "Apple Watch\n"
    )
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        content=body.encode("utf-8"),
    )
    if r.status_code != 200:
        print("FAIL source bundle status", r.status_code, r.text)
        return False
    segs = query_sleep_segments_for_day(uid, today)
    if not segs or "Watch" not in str(segs[0].get("source_name") or ""):
        print("FAIL source_name not kept", segs)
        return False
    print("OK optional ---SOURCES---/---DEVICES--- do not break ends pairing")
    return True


def test_sleep_shortcut_d1_plist() -> bool:
    sys.path.insert(0, str(ROOT / "scripts" / "macos"))
    from build_pha_ingest_shortcuts import build_sleep

    class _Spec:
        metric_id = "sleep_time_asleep"
        ingest_key = "sleep_hours"
        label = "睡眠"
        unit = "h"
        health_type = "Sleep"
        stat = "Sum"
        unit_health = "In Bed"

    d1 = build_sleep("http://example.local:8788/ingest/healthkit", "t", [_Spec()], variant="d1")
    today = build_sleep(
        "http://example.local:8788/ingest/healthkit", "t", [_Spec()], variant="is_today"
    )
    dump = str(d1)
    if "健康 App 锚点（9/6）" in dump or "健康 App 锚点（9/6）" in str(today):
        print("FAIL 9/6 anchor text must be gone")
        return False
    find_d1 = d1["WFWorkflowActions"][0]["WFWorkflowActionParameters"]
    if not find_d1.get("WFContentItemLimitEnabled") or find_d1.get("WFContentItemLimitNumber") != 150:
        print("FAIL D1 must Limit 150", find_d1)
        return False
    if find_d1.get("WFContentItemSortOrder") != "Latest First":
        print("FAIL D1 must sort Start Date latest first", find_d1)
        return False
    templates = find_d1["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"]
    if any(t.get("Operator") == 1002 for t in templates):
        print("FAIL D1 must not use is today")
        return False
    last_n = [t for t in templates if t.get("Operator") == 1001]
    if not last_n or last_n[0].get("Values", {}).get("Number") != 2:
        print("FAIL D1 must bound Start Date to last 2 days", templates)
        return False
    find_today = today["WFWorkflowActions"][0]["WFWorkflowActionParameters"]
    today_templates = find_today["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"]
    if not any(t.get("Operator") == 1002 for t in today_templates):
        print("FAIL is-today fallback missing is-today filter")
        return False
    if find_today.get("WFContentItemLimitEnabled"):
        print("FAIL is-today fallback should not Limit")
        return False
    props = [
        a["WFWorkflowActionParameters"].get("WFContentItemPropertyName")
        for a in d1["WFWorkflowActions"]
        if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.properties.health.quantity"
    ]
    if props[:5] != ["Value", "Start Date", "End Date", "Source", "Device"]:
        print("FAIL Get Details props", props)
        return False
    from build_pha_ingest_shortcuts import _find_health, _get_detail

    qty = _find_health("Active Calories", "AAAA", "Samples")["WFWorkflowActionParameters"]
    qty_templates = qty["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"]
    if qty.get("WFContentItemLimitEnabled"):
        print("FAIL quantity Find must not Limit", qty)
        return False
    if not any(t.get("Operator") == 1002 for t in qty_templates):
        print("FAIL quantity Find must keep is today")
        return False
    detail = _get_detail("AAAA", "Samples", "Value", "BBBB", "Value")
    if detail["WFWorkflowActionIdentifier"] != "is.workflow.actions.properties.health.quantity":
        print("FAIL quantity Get Details identifier changed")
        return False
    print("OK sleep shortcut D1 Limit 150 + is-today fallback; no 9/6 copy; quantity Find unchanged")
    return True


def test_shortcut_sleep_date_format(client) -> bool:
    from pha.date_parser import safe_parse_datetime
    from pha.sqlite_storage import query_wearable_daily_range

    parsed = safe_parse_datetime("7 Sep 2026 at 12:01\u202fAM")
    if parsed is None or (parsed.year, parsed.month, parsed.day) != (2026, 9, 7):
        print("FAIL shortcuts date parse", parsed)
        return False

    def shortcut_dt(dt: datetime) -> str:
        months = (
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        )
        hour12 = dt.hour % 12 or 12
        ampm = "AM" if dt.hour < 12 else "PM"
        return (
            f"{dt.day} {months[dt.month - 1]} {dt.year} at "
            f"{hour12}:{dt.strftime('%M')}\u202f{ampm}"
        )

    uid = "sleep_shortcut_dates"
    today = _local_today()
    t0 = _at(today, 1)
    t1 = _at(today, 2)
    t2 = _at(today, 3)
    t3 = _at(today, 4)
    t4 = _at(today, 4, 30)
    body = (
        "PHA_SLEEP_V1\n"
        f"user_id={uid}\n"
        "---VALUES---\n"
        "Core\nDeep\nREM\nAwake\n"
        "---STARTS---\n"
        f"{shortcut_dt(t0)}\n{shortcut_dt(t1)}\n{shortcut_dt(t2)}\n{shortcut_dt(t3)}\n"
        "---ENDS---\n"
        f"{shortcut_dt(t1)}\n{shortcut_dt(t2)}\n{shortcut_dt(t3)}\n{shortcut_dt(t4)}\n"
    )
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        content=body.encode("utf-8"),
    )
    if r.status_code != 200:
        print("FAIL shortcut dates status", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows:
        print("FAIL shortcut dates missing daily")
        return False
    row = rows[0]
    if abs((row.sleep_core_hours or 0) - 1.0) > 0.02:
        print("FAIL core hours", row.sleep_core_hours)
        return False
    if abs((row.sleep_hours or 0) - 3.0) > 0.02:
        print("FAIL asleep hours", row.sleep_hours)
        return False
    print("OK Shortcuts sleep dates with narrow space")
    return True


def test_sleep_zero_duration_skipped_and_overlap_unioned(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_zero_union"
    today = _local_today()
    now = datetime.now(ZoneInfo(TZ)).replace(tzinfo=None, second=0, microsecond=0)
    core_start = _at(today, 2)
    core_end = _at(today, 6)
    blip = _at(today, 4)
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core", "Core", "Core"],
            "sleep_starts": [
                core_start.isoformat(),
                core_start.isoformat(),
                blip.isoformat(),
            ],
            "sleep_ends": [
                core_end.isoformat(),
                core_end.isoformat(),
                blip.isoformat(),
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL zero/union status", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows or abs((rows[0].sleep_core_hours or 0) - 4.0) > 0.02:
        print("FAIL union core hours", rows[0].sleep_core_hours if rows else None)
        return False
    if abs((rows[0].sleep_hours or 0) - 4.0) > 0.02:
        print("FAIL union asleep hours", rows[0].sleep_hours if rows else None)
        return False
    bad = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core"],
            "sleep_starts": [(now - timedelta(hours=1)).isoformat()],
            "sleep_ends": [(now - timedelta(hours=3)).isoformat()],
        },
    )
    err = (bad.json() or {}).get("detail", {}).get("error", "")
    if bad.status_code != 400 or "end_before_start" not in err:
        print("FAIL inverted pair must 400", bad.status_code, bad.text)
        return False
    print("OK skip zero-duration sleep; union overlaps; inverted pair fail-closed")
    return True


def test_sleep_stage_overlap_nulls_stages(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_stage_overlap"
    today = _local_today()
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core", "REM"],
            "sleep_starts": [_at(today, 1).isoformat(), _at(today, 3).isoformat()],
            "sleep_ends": [_at(today, 5).isoformat(), _at(today, 7).isoformat()],
        },
    )
    if r.status_code != 200:
        print("FAIL overlap status", r.status_code, r.text)
        return False
    body = r.json()
    if not body.get("audit", {}).get("stage_overlap"):
        print("FAIL expected stage_overlap", body)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows:
        print("FAIL overlap missing daily")
        return False
    row = rows[0]
    if abs((row.sleep_hours or 0) - 6.0) > 0.02:
        print("FAIL overlap union asleep", row.sleep_hours)
        return False
    if row.sleep_core_hours is not None or row.sleep_rem_hours is not None or row.sleep_deep_hours is not None:
        print(
            "FAIL overlap must null stages",
            row.sleep_core_hours,
            row.sleep_deep_hours,
            row.sleep_rem_hours,
        )
        return False
    print("OK stage_overlap nulls per-stage hours and keeps asleep union")
    return True


def test_sleep_wake_day_noon_window(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_wake_noon"
    today = _local_today()
    yesterday = today - timedelta(days=1)
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core", "Core"],
            "sleep_starts": [
                _at(yesterday, 23).isoformat(),
                _at(today, 23, 30).isoformat(),
            ],
            "sleep_ends": [
                _at(today, 7).isoformat(),
                _at(today, 23, 45).isoformat(),
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL wake-day status", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows or abs((rows[0].sleep_hours or 0) - 8.0) > 0.02:
        print("FAIL wake-day hours", rows[0].sleep_hours if rows else None)
        return False
    tomorrow = query_wearable_daily_range(uid, today + timedelta(days=1), today + timedelta(days=1))
    if tomorrow and (tomorrow[0].sleep_hours or 0) > 0:
        print("FAIL tonight leaked into another day", tomorrow[0].sleep_hours)
        return False
    audit = r.json().get("audit") or {}
    if audit.get("kept") != 1:
        print("FAIL evening extra should be dropped", audit)
        return False
    print("OK wake-day noon window keeps overnight sleep and drops tonight")
    return True


def test_sleep_stale_bundle_rejected(client) -> bool:
    uid = "sleep_stale"
    today = _local_today()
    old = today - timedelta(days=3)
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core"],
            "sleep_starts": [_at(old - timedelta(days=1), 23).isoformat()],
            "sleep_ends": [_at(old, 7).isoformat()],
        },
    )
    err = (r.json() or {}).get("detail", {}).get("error", "")
    if r.status_code != 400 or err != "stale_sleep_bundle":
        print("FAIL stale bundle must 400", r.status_code, r.text)
        return False
    print("OK stale_sleep_bundle rejected")
    return True


def test_sleep_period_not_used_as_in_bed(client) -> bool:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = "sleep_period"
    today = _local_today()
    yesterday = today - timedelta(days=1)
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Deep", "Core"],
            "sleep_starts": [
                _at(yesterday, 20, 30).isoformat(),
                _at(yesterday, 22, 45).isoformat(),
            ],
            "sleep_ends": [
                _at(yesterday, 20, 34).isoformat(),
                _at(today, 6, 27).isoformat(),
            ],
        },
    )
    if r.status_code != 200:
        print("FAIL sleep_period status", r.status_code, r.text)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows:
        print("FAIL sleep_period missing daily")
        return False
    row = rows[0]
    if row.in_bed_hours is not None:
        print("FAIL in_bed must stay empty without In Bed samples", row.in_bed_hours)
        return False
    if abs((row.sleep_period_hours or 0) - 9.95) > 0.02:
        print("FAIL sleep_period", row.sleep_period_hours)
        return False
    if (r.json().get("audit") or {}).get("sleep_efficiency") is not None:
        print("FAIL efficiency must wait for in_bed", r.json().get("audit"))
        return False

    uid2 = "sleep_period_bed"
    bed = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid2,
            "sleep_values": ["In Bed", "Core"],
            "sleep_starts": [
                _at(yesterday, 22, 3).isoformat(),
                _at(yesterday, 22, 45).isoformat(),
            ],
            "sleep_ends": [
                _at(today, 7).isoformat(),
                _at(today, 6, 27).isoformat(),
            ],
        },
    )
    if bed.status_code != 200:
        print("FAIL in_bed fixture status", bed.status_code, bed.text)
        return False
    rows2 = query_wearable_daily_range(uid2, today, today)
    if not rows2 or abs((rows2[0].in_bed_hours or 0) - 8.95) > 0.02:
        print("FAIL in_bed hours", rows2[0].in_bed_hours if rows2 else None)
        return False
    print("OK in_bed from In Bed samples only; sleep_period is derived")
    return True


def test_sleep_bundle_clears_old_daily_keys(client) -> bool:
    from pha.sqlite_storage import list_healthkit_sleep_family_on_day, query_wearable_daily_range

    uid = "sleep_family_cleanup"
    today = _local_today()
    stale = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "samples": [
                {
                    "metric_type": "sleep_core",
                    "timestamp": f"{today.isoformat()}T08:00:00+08:00",
                    "value": 9.9,
                    "unit": "h",
                    "source": "healthkit",
                }
            ],
        },
    )
    if stale.status_code != 200:
        print("FAIL stale daily-key status", stale.status_code, stale.text)
        return False
    before = list_healthkit_sleep_family_on_day(uid, today)
    if not before:
        print("FAIL expected leftover healthkit sleep daily key")
        return False
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": uid,
            "sleep_values": ["Core"],
            "sleep_starts": [_at(today, 2).isoformat()],
            "sleep_ends": [_at(today, 6).isoformat()],
        },
    )
    if r.status_code != 200:
        print("FAIL cleanup bundle status", r.status_code, r.text)
        return False
    left = list_healthkit_sleep_family_on_day(uid, today)
    if left:
        print("FAIL healthkit sleep daily keys should be gone", left)
        return False
    rows = query_wearable_daily_range(uid, today, today)
    if not rows or abs((rows[0].sleep_hours or 0) - 4.0) > 0.02:
        print("FAIL daily after cleanup", rows[0].sleep_hours if rows else None)
        return False
    print("OK sleep bundle deletes leftover healthkit sleep daily keys")
    return True


def main() -> int:
    os.environ["PHA_INGEST_TZ"] = TZ
    db = _bind_temp_db()
    os.environ["PHA_INGEST_TOKEN"] = TOKEN
    receipt = Path(tempfile.mkdtemp(prefix="pha-hk-receipt-")) / "last.json"
    os.environ["PHA_HEALTHKIT_INGEST_LAST"] = str(receipt)
    client = _client()
    ok = all(
        [
            test_token_gates(client),
            test_malformed_drops_batch(client, db),
            test_happy_path_and_idempotent(client),
            test_energy_daily_key_replaces(client),
            test_hrv_sdnn_does_not_write_rmssd(client),
            test_sleep_stages_sum_to_asleep(client),
            test_sleep_stage_bundle_last_24h(client),
            test_sleep_bundle_marker_text(client),
            test_sleep_bundle_optional_source_sections(client),
            test_sleep_shortcut_d1_plist(),
            test_shortcut_sleep_date_format(client),
            test_sleep_zero_duration_skipped_and_overlap_unioned(client),
            test_sleep_stage_overlap_nulls_stages(client),
            test_sleep_wake_day_noon_window(client),
            test_sleep_stale_bundle_rejected(client),
            test_sleep_period_not_used_as_in_bed(client),
            test_sleep_bundle_clears_old_daily_keys(client),
            test_unknown_metric_dropped(client),
            test_shortcuts_quantity_string(client),
            test_steps_sums_multiple_numbers(client),
            test_newline_json_uses_leading_total(client),
            test_quantity_dict_magnitude(client),
            test_object_replacement_char_fail_closed(client),
            test_empty_sample_receipt(client),
            test_quantity_shortcut_p10_p11(),
            test_empty_value_hole_in_json(client),
            test_get_ingest_explains_post_only(client),
            test_ingest_last_receipt(client),
            test_empty_timestamp_uses_received_at(client),
            test_zip_clear_preserves_healthkit(client),
            test_priority_pack_units_and_zip_wins(client),
            test_skip_llm_reads_healthkit_steps(client),
            test_time_grain_binds_time_anchor_slots(),
            test_skip_llm_time_grain_not_90d_mean(client),
        ],
    )
    print("pha_healthkit_ingest_selfcheck:", "PASS" if ok else "FAIL")
    print("temp_db:", db)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

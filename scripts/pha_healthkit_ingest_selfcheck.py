#!/usr/bin/env python3
"""M0-P0 selfcheck: POST /ingest/healthkit writes fake samples into a temp SQLite DB."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

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
    if row.hrv_rmssd_ms != 42.0:
        print("FAIL daily hrv", row.hrv_rmssd_ms)
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
    hrv_avg = hd.summaries["hrv"].average if "hrv" in hd.summaries else None
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


def test_unknown_metric_dropped(client) -> bool:
    r = client.post(
        "/ingest/healthkit",
        headers={"X-PHA-Ingest-Token": TOKEN},
        json={
            "user_id": "selfcheck",
            "samples": [
                {
                    "metric_type": "vo2max",
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
    if r.status_code != 200 or r.json().get("error") != "use_post":
        print("FAIL GET ingest", r.status_code, r.text)
        return False
    print("OK GET ingest explains POST-only")
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


def main() -> int:
    os.environ["PHA_INGEST_TZ"] = TZ
    db = _bind_temp_db()
    os.environ["PHA_INGEST_TOKEN"] = TOKEN
    client = _client()
    ok = all(
        [
            test_token_gates(client),
            test_malformed_drops_batch(client, db),
            test_happy_path_and_idempotent(client),
            test_unknown_metric_dropped(client),
            test_shortcuts_quantity_string(client),
            test_steps_sums_multiple_numbers(client),
            test_newline_json_uses_leading_total(client),
            test_quantity_dict_magnitude(client),
            test_object_replacement_char_fail_closed(client),
            test_empty_value_hole_in_json(client),
            test_get_ingest_explains_post_only(client),
            test_empty_timestamp_uses_received_at(client),
            test_zip_clear_preserves_healthkit(client),
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

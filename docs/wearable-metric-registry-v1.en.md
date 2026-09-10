# Wearable Metric Registry v1 — operations and extension handbook

> **Language / 语言**：English (this document) · [中文](wearable-metric-registry-v1.md)

> **Status**:**encoded** (Wave 3d-δ-c · `pha-v2.3.23`)  
> **Config source of truth**: [`storage/registry/wearable_metric_registry.json`](../storage/registry/wearable_metric_registry.json)  
> **Loader**: `pha/wearable_metric_registry.py`  
> **Governing docs**: [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md) · [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md)

---

## 1. What this solves

| User expectation | PHA ruling |
|------------------|----------|
| Chat says “I want to see metric X” | **Intent maps** to `metric_id` (config / Registry). The LLM **must not** write SQL |
| Background auto-turns Raw into a 90d baseline | Only when the **L1 pipeline + a Registry row** already exist; chat may **trigger** a registered `ingest_module` |
| Adding a metric should not require a Python list edit every time | **Daily column already exists** → JSON only; **new Raw shape** → one L1 PR + one Registry row |

What Gemini called “fully Registry-ized” existed only in Spec **before δ-c**. From **v2.3.23**, `build_wearable_compare_table_v1` reads the daily metric list, workout conditional rows, Chinese labels, and Fallback footnotes from JSON.

---

## 2. Three-layer boundary (lowest maintenance cost)

```text
L0  Parser (one-shot code per Apple/HK type)
      import / backfill_workouts / sleep segment …
         │
L1  Daily facts (wearable_daily columns · workout_sessions · …)
         │  ← Registry: l1.kind + field + rollup
         │
L2  CompareTable (mean/range/verdict · fully deterministic)
         │  ← Registry: compare.* + snapshot.parser
         │
L3  LLM narrative (cite Tier0 table only · Audit intercepts)
```

**Write code**: new `l1.kind` (e.g. future `hk_respiratory_detail`).  
**Config only**: `wearable_daily` already has the column; turn on `comparable_90d` or add `intent_hints`.

---

## 3. Registry field cheat sheet

| Field | Use |
|------|------|
| `metric_id` | Aligns OCR / Compare row / Audit token |
| `l1.kind` | `wearable_daily` · `workout_sessions` |
| `l1.field` | Warehouse column name (daily table) |
| `compare.comparable_90d` | Whether to attempt a 90d baseline |
| `compare.snapshot_only_if_no_baseline` | Still emit a `snapshot_only` row when a screenshot exists but the warehouse does not (deep sleep / REM) |
| `compare.conditional_row` | Workout row only when intent / screenshot hits |
| `ui.label_zh` / `intent_hints` | Matching inside LLM tables and Audit spans |
| `ui.footer_when_snapshot_only` | Fallback footnote (do not hardcode metric names) |
| `ingest.module` | Linked `ingest_modules[].module_id` |
| `fact_card.eligible` | Whether the metric may appear on the fact-card checkbox list |
| `fact_card.enabled_default` | Default checkbox when the user has no prefs (default ≠ unchangeable) |
| `fact_card.ingest_key` | Matching `POST /ingest/healthkit` `metric_type` (may be empty) |
| `fact_card.unit` / `higher_is_better` | Full-card display and band direction |
| `fact_card.daily_key` | Ingest UPSERT one row per calendar day |
| `fact_card.shortcut_health_type` / `shortcut_stat` / `shortcut_unit` | Must match the Find catalog `device_verified` row. Source of truth: [`shortcut_health_find_catalog.json`](../storage/registry/shortcut_health_find_catalog.json). Ban SDK names and Health app browse titles. |
| `fact_card.shortcut_skip_reason` | Has `ingest_key` but the Shortcut deliberately does not sync (must state why; silent mapping is forbidden) |
| `fact_card.include_when_selected` | When the user checks the listed `metric_id`s, this row also enters the **sleep Shortcut pack** (data layer; does not change card display) |
| `fact_card.shortcut_sleep_value` | Sleep Analysis stage labels (`Asleep Deep`, etc.). Rows with this field go into “PHA sync sleep”, not the quantity Shortcut |
| `fact_card.temporal` | Freshness semantics: `kind ∈ {accrual, daily_lagged, overnight, rolling_mean, latest}`; `daily_lagged` / `overnight` may carry `freshness_days` (default 2); `latest` looks back to the most recent sample (VO2max default 90 days) and `coverage_denominator: false`; `rolling_mean` may carry `window_days`. Default = only the as_of calendar-day row |
| `catalog.key` | Legacy bundle catalog key (`sleep`/`hrv`…); shared by chat and schema derivation |
| `catalog.cluster` / `cluster_primary` / `expand_on_cluster_query` | Same-cluster expansion (e.g. sleep stages); Python must not hardcode a frozenset |
| `catalog.label_zh` / `label_en` / `point_*` / `span_*` | Chat Numerics / skip-LLM audit labels; 9 legacy keys are freeze-tested |
| `fact_card.display_fallback_metric_id` | When this row has no value, display another column and use that column for baseline; the label follows the fallback. Do not label SDNN as RMSSD |

### `no_baseline_reason` (Spec enum · row-level `reason_code` waits for ε+)

See [`stage3d-delta-wearable-fact-pipeline-spec.md` §2.2](stage3d-delta-wearable-fact-pipeline-spec.md).

---

## 4. Incremental sync API (not per-metric hardcoded)

| Endpoint | Notes |
|------|------|
| `GET /data/sync-modules` | Lists Registry `ingest_modules` |
| `POST /data/upload` | **Only recommended path**: full import (Apple export is a full snapshot) |
| `POST /data/sync-module/{module_id}` | **Retired** (410) |
| `POST /data/backfill-workouts` | **Retired** (410) |

When adding a module: implement L0 parse + add an `ingest_modules` entry in JSON + wire `main.data_sync_module` **once**. Do not add a dedicated `/data/backfill-xxx` path.

---

### D. Promote to Shortcut-sync metric (priority pack)

The audience is maintainers, not end users customizing metric names on a page. Find types cannot be variables.

1. Confirm `wearable_daily` already has the column; if not, do L1 first (zip parser + aggregator + daily column). Incremental types must already exist on the ledger.  
2. **Look up the Find catalog first** [`shortcut_health_find_catalog.json`](../storage/registry/shortcut_health_find_catalog.json). `shortcut_find_type` must be the Shortcuts Find selector literal, and `status=device_verified`. Health app titles, SDK names, and permission-panel aliases are all forbidden (`never_use_find_labels`: `Active Energy` / `Blood Oxygen` / `Apple Sleeping Wrist Temperature` / `Cardio Fitness`). Unverified rows stay `skipped` — **do not guess them into the Shortcut**.  
3. Registry: `fact_card.eligible`, `ingest_key`, `temporal`, plus a `shortcut_health_type` that matches the catalog (or `shortcut_skip_reason`). `eligible` rows must not be half-finished.  
4. Ingest: `_CANONICAL` / FR-1.4; POST unit with the value; reject unknown units.  
5. Bump `shortcut_pack_version`, generate, and **replace once** on the iPhone the “PHA sync health” Shortcut. The card top warns when the pack is stale. Checkboxes filter the card only; they do not rewrite the Shortcut.  
6. Health app reconciliation: compare only when that day has a value; if neither side has it, both empty counts as pass. Then backfill with zip to correct the same-day increment.

Sparse types (e.g. VO2max) use `temporal.kind=latest` and `coverage_denominator: false`.

---

## 5. SOP: adding a metric

### A. Compare only (column already exists)

1. Append a row to `metrics` in `wearable_metric_registry.json` (`l1.kind=wearable_daily`).  
2. Run `scripts/pha_wearable_registry_selfcheck.py` + `pha_wearable_compare_table_selfcheck.py`.  
3. Bump `build_marker` · restart.

### B. New Raw → new daily column (e.g. future overnight SpO2 detail)

1. L0: `data_importer` / aggregator (one-shot).  
2. One Registry row.  
3. golden_compare / real-device gate.

### C. New chat phrasing

1. **Only edit** `intent_hints` (add zh and en together), or Intent Catalog `goal_markers` / `broad_compare` / `follow_ups`.  
2. Run `python scripts/pha_wearable_bundle_schema_generate.py --check` and `scripts/pha_wearable_registry_selfcheck.py`.  
3. If `metric_id` is unregistered → unified reply “this version does not yet include that comparable metric”.  
4. **Do not** add phrase / metric / label tables in `pha/*.py`.

---

## 6. Current registry snapshot (2026-06-01)

Keep in sync with JSON; **do not** maintain a second list in this table.

| metric_id | l1 | comparable | Notes |
|-----------|-----|------------|------|
| sleep_time_asleep | daily | ✅ | |
| hrv_rmssd_ms | daily | ✅ | |
| resting_heart_rate_bpm | daily | ✅ | |
| spo2_percent | daily | ✅ | Omit the row when there is no OCR |
| respiratory_rate | daily | ✅ | 3d-ε |
| sleep_deep / sleep_rem | daily | ✅ | `snapshot_only` when the warehouse has no data |
| workout_* | workout_sessions | ✅ conditional row | Needs `hk_workout` increment or full import |

---

## 7. Later waves (not done)

| Item | Notes |
|----|------|
| Dashboard dropdown | Read `GET /data/sync-modules` instead of hardcoding the “workout” button copy |
| `reason_code` on CompareRow | Full alignment with Spec §2.2 |
| Chat Discover→Promote | Join `dynamic_slot_registry` (metadata only, not SQL generation) |
| Authorized screenshot-range endpoint | 3d-ε+ to reduce `compare_table_numeric_drift` Fallback |

---

## 8. Acceptance

```bash
cd agent-harness
python scripts/pha_wearable_registry_selfcheck.py
python scripts/pha_wearable_compare_table_selfcheck.py
./scripts/pha_restart_accept.sh
```

`/health` `pha_build` should be `pha-v2.3.23-wave3d-delta-c-metric-registry`.

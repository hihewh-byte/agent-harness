# Stage 3d-δ — Wearable Fact Pipeline & Metric Registry

> **Language / 语言**：English (this document) · [中文](stage3d-delta-wearable-fact-pipeline-spec.md)

> **Status**: **v1.0 signed** (2026-06-01 · PM/Gemini/Cursor architecture alignment)  
> **Governing docs**: [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md) · [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md)  
> **Baseline build**: `pha-v2.3.18-wave3d-gamma-wearable-soul-align` (3d-γ + Soul alignment already coded; **this document is the 3d-δ/ε contract, no implementation**)

---

## 0. Document purpose

Answer: **when the user asks for a 90-day compare and the warehouse has no aggregate yet, what should PHA do?**

**Ruling**:

1. **Support it**, and it must complete in the **L1/L2 deterministic pipeline**. Forbidden: LLM combinatorial math on Raw Data.  
2. Current deep/REM/workout marked `NO_BASELINE` = **`warehouse_not_implemented`** (pipeline gap + 3d-γ MVP anti-hallucination), **not** “Apple Watch has no data”.  
3. The expansion is a **feature iteration (3d-δ)**, not a one-off Compare Audit relaxation.

---

## 1. Four-layer fact pipeline (order is not reversible)

```text
L0  Raw
    Apple export.xml (HK samples) · screenshot OCR (WearableSnapshot)
         │
         ▼  Import / OCR (deterministic)
L1  Curated Daily Facts
    wearable_daily · wearable_sleep_segments* · workout_daily* (δ extension)
         │
         ▼  Window Aggregate (SQL / compute layer)
L2  CompareTable SSO
    mean · range · verdict · reason_code
         │
         ▼  Interpretation Policy constraints
L3  LLM narrative
```

\* Current `wearable_sleep_segments` **does not retain** HK stage types (see §3.1).

---

## 2. Metric Registry

> **Implementation source of truth (δ-c already coded)**: [`storage/registry/wearable_metric_registry.json`](../storage/registry/wearable_metric_registry.json) · ops handbook [`wearable-metric-registry-v1.md`](wearable-metric-registry-v1.md)

**Principle**: one **registration row per `metric_id`**; forbidden to write a Harness patch for a single metric.

### 2.1 Registration fields

| Field | Notes |
|-------|-------|
| `metric_id` | Stable key, aligned with Snapshot / warehouse columns |
| `l1_source` | `wearable_daily` column · `ocr_only` · `workout_daily` · … |
| `comparable_90d` | Whether it participates in 90d compare |
| `rollup` | `mean_minmax` · `snapshot_only` · `omitted` |
| `no_baseline_reason` | Only when `comparable_90d=false` |
| `ocr_required` | Whether a screenshot KPI is required to emit a Compare row |

### 2.2 `no_baseline_reason` enum

| Reason code | Meaning | User wording |
|-------------|---------|--------------|
| `warehouse_not_implemented` | Raw/segments exist, daily aggregate not done | “The system has not yet saved 90-day history for this item” |
| `ocr_only_mvp` | Intentionally screenshot-only (e.g. workout conditional row) | “From this screenshot only” |
| `insufficient_days` | Valid days in window < threshold | “Not enough valid days in the last 90 days” |
| `snapshot_missing` | User asked compare but OCR has no value | Omit the row (not N/A) |

### 2.3 Current registry (v1 · 2026-06-01)

| metric_id | comparable_90d | l1_source | no_baseline_reason | Notes |
|-----------|----------------|-----------|-------------------|-------|
| `sleep_time_asleep` | ✅ | `wearable_daily.sleep_hours` | — | 3d-γ MVP |
| `hrv_rmssd_ms` | ✅ | `wearable_daily.hrv_rmssd_ms` | — | |
| `resting_heart_rate_bpm` | ✅ | `wearable_daily.resting_heart_rate_bpm` | — | |
| `spo2_percent` | ✅ | `wearable_daily.spo2_pct` | — | **omit row** if no OCR |
| `sleep_deep` | ❌ | — | `warehouse_not_implemented` | δ: after HK stage lands, flip ✅ |
| `sleep_rem` | ❌ | — | `warehouse_not_implemented` | same |
| `respiratory_rate` | ❌→**ε** | `wearable_daily.respiratory_rate_bpm` | pending comparable registration | OCR+warehouse already ready |
| `workout_heart_rate_range_bpm` | ❌ | — | `warehouse_not_implemented` | δ: after HKWorkout import, flip ✅ |
| `workout_count_recent` | ❌ | — | `warehouse_not_implemented` | same |
| `heart_rate_range_bpm` | ❌ | — | `ocr_only_mvp` | 6M chart, not a single-day KPI; **keep out of table** to avoid confusion |

---

## 3. Why 90d baseline cannot be computed today (fact audit)

### 3.1 Deep / REM

| Layer | Status |
|-------|--------|
| Apple export | `HKCategoryTypeIdentifierSleepAnalysis` includes Deep / REM / Core |
| Import | `_sleep_is_asleep` accepts deep/rem, but the segment table only stores `is_awake` 0/1 |
| `wearable_daily` | Only `sleep_hours` (union total duration), **no** `sleep_deep_hours` / `sleep_rem_hours` |
| CompareTable | `NO_BASELINE` (contract §3.2) |

**δ plan (deterministic)**:

1. Import: parse HK `value`, write segment `stage` (deep/rem/core/awake/inbed).  
2. Daily rollup: sum each stage duration by `day` → new `wearable_daily` columns or `wearable_sleep_stage_daily`.  
3. Registry: upgrade `sleep_deep` / `sleep_rem` to `comparable_90d=true`.  
4. CompareTable build: same algorithm as total sleep duration for mean/range/verdict.

### 3.2 Workout

| Layer | Status |
|-------|--------|
| Apple export | `HKWorkout` records exist |
| Import | Workout parse **not implemented** |
| CompareTable | OCR only: `76-147 bpm`, `8 次`; `snapshot_only` |

**δ plan**:

1. Import: parse Workout → `workout_sessions` or daily summary `workout_count`, `hr_min/max`.  
2. Registry: workout metrics `comparable_90d=true` (session aggregate in window).  
3. Emit compare rows when user intent includes workout (continue 3d-γ conditional-row logic).

### 3.3 Respiratory rate (3d-ε · low cost)

| Layer | Status |
|-------|--------|
| OCR | `11-17.5` already extracted |
| `wearable_daily` | `respiratory_rate_bpm` has data |
| CompareTable | **not in** MVP |

**ε plan**: add a Registry row + CompareTable build; **no** import change needed.

---

## 4. On-demand rollup

When the user asks “compare the last 90 days” and Registry marks `warehouse_not_implemented` but δ has shipped:

| Step | Actor |
|------|-------|
| 1. Detect registry + user intent | Harness |
| 2. If L1 missing columns → trigger sync job / sync SQL rollup | **Backend** |
| 3. Rebuild CompareTable | Compute layer |
| 4. Then call LLM | chat_service |

**Forbidden**: stuffing export.xml fragments into the prompt and letting the LLM “compute 90-day deep-sleep mean”.

---

## 5. Interface with 3d-γ CompareTable

| Change | Impact |
|--------|--------|
| New comparable rows | `build_wearable_compare_table_v1` reads Registry, not a hardcoded list |
| `NO_BASELINE` rows | Must carry `no_baseline_reason` into `verdict_note` / telemetry |
| Audit | See Interpretation Policy §5; δ does **not** relax no-baseline subjective-word rules |
| Fallback | Automatically extends with Table rows; no new template needed |

---

## 6. Display contract (not an LLM judgment)

| Topic | Ruling |
|-------|--------|
| Sleep range includes 0.4h ultra-short days | δ-ux: optional P5–P95 or footnote “includes abnormally short-sleep days” |
| Telling the user “no history” | Must correspond to `no_baseline_reason`; do not say “Apple has no data” |

---

## 7. Coding waves

| PR | Scope | Gate |
|----|-------|------|
| **3d-ε** | `respiratory_rate` into Registry + Compare + audit subjective words | selfcheck + G-Compare |
| **3d-δ-a** | Sleep stage import + daily aggregate | import unit tests + 90d mean spot check |
| **3d-δ-b** | HKWorkout import + workout comparable | same |
| **3d-δ-c** | Registry-driven `build_wearable_compare_table_v1` | golden_compare bump |

**Depends**: 3d-γ green; Interpretation Policy v1 signed (companion to this document).

---

## 8. E2E increment (fold into D-3d-2)

| ID | Green |
|----|-------|
| **G-Delta-1** | After δ ships, deep/rem Compare rows `comparable_90d`, mean matches SQL |
| **G-Delta-2** | workout 90d count/HR range matches HK aggregate |
| **G-Epsilon-1** | Respiratory rate OCR+warehouse dual-source one-row compare |
| **G-Interp-1** | NO_BASELINE row says “adequate” → audit fail → Fallback |

---

## 9. Revision history

| Version | Date | Notes |
|---------|------|-------|
| **v1.0** | 2026-06-01 | First version: Metric Registry · L0–L3 pipeline · δ/ε waves |

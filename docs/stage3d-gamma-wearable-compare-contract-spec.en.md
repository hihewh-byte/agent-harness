# Stage 3d-γ — Wearable Compare Contract Spec

> **Language / 语言**：English (this document) · [中文](stage3d-gamma-wearable-compare-contract-spec.md)

> **Status**: **v1.0 signed** (2026-05-31 · PM/Gemini final review)  
> **Baseline build**: `pha-v2.3.14-wave3d-gamma-compare-table-b` (3d-γ-a/b already coded)  
> **Governing docs**: [`pha-pm-constitution.md`](pha-pm-constitution.md) · [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md) · [`stage3d-wearable-merge-and-gates-spec.md`](stage3d-wearable-merge-and-gates-spec.md)  
> **E2E checklist**: [`stage3d-wearable-e2e-checklist.md`](stage3d-wearable-e2e-checklist.md) (γ accept items pending merge)  
> **Roadmap ID**: **D-3d-γ**

---

## 0. Document purpose and architectural position

### 0.1 From “patch stream” to “contract stream”

Real-device audit (msg 305 → 311) showed:

| Layer | Status | Problem |
|-------|--------|---------|
| **L0 ledger** | ✅ 9 KPI · Lane-O · `ocr_only` | OCR regex sustainably maintainable (golden fixture closeout) |
| **L2 compare interpretation** | ❌ | LLM freely writes “90d vs screenshot” → deep/REM warehouse hallucination (wording varies, mechanism does not) |
| **C-layer compliance** | ❌ | `wearable_screenshot_review` forbids `NUMERICS_MANIFEST` → audit never ran |

**3d-γ goal**: upgrade PHA from “an assistive tool trying to constrain the LLM with Prompt” to “an on-device audit system with its own compute contract and deterministic output protocol”.

**Core principle**: **CompareTable is the single source of truth (SSO) for compare numbers**; the LLM may only “copy the table and polish”, must not construct 90d compare numbers itself.

### 0.2 Non-goals

- Do not replace `WearableSnapshotLedgerV1` (screenshot-fact SSO)
- Do not replace **macro trends** in `WEARABLE_90D_SUMMARY` such as Pearson / monthly / HRV lowest 5 days (see §5)
- Do not implement Wave 4b full-text CHB Compiler inside 3d-γ
- Do not expand a 150+ metric Catalog; MVP is only the rows in §3

### 0.3 PM ruling (2026-05-31 · Gemini final review)

| Topic | Ruling |
|-------|--------|
| `WEARABLE_90D_SUMMARY` | **Keep** Pearson/monthly etc.; LLM **forbidden** to extract means from it for compare; compare numbers **must and may only** come from CompareTable |
| Audit mode | **Forced Deterministic Fallback** (not warn-only); shape an “unnegotiable” auditor |
| SpO2 no screenshot | **Omit the whole row** (not `[N/A]`), prevent LLM reverse-inference |
| 90d comparable MVP | Four: `sleep_time_asleep` · `hrv_rmssd_ms` · `resting_heart_rate_bpm` · `spo2_percent` |

---

## 1. Problem statement (real-device audit summary)

### 1.1 msg-311 reproducible fault

- **Ledger trustworthy**: 9 KPIs (incl. workout 76–147 / 8 sessions)
- **Warehouse inject trustworthy**: sleep 8.0[0.4-9.9], HRV 32.8, RHR 57.4…; constraint block states “no deep/REM history”
- **Reply untrustworthy**: “warehouse-summary average: about 1h 25m / about 2h 36m” — warehouse has no such fields
- **Audit never ran**: Harness plan forbids `NUMERICS_MANIFEST` → `numerics_manifest is None`
- **repair miss-delete**: bullet-split wording bypassed line-level regex

### 1.2 Root cause (architecture-level)

```text
WearableSnapshot (facts) + WEARABLE_90D_SUMMARY (partial facts)
        ↓
   LLM open-ended “compare + conclusion”          ← 3d-γ cuts this path
        ↓
   Fill missing dimensions (stage 90d hallucination)
```

---

## 2. CompareTableV1 — data structure

### 2.1 Schema (JSON · machine-readable)

```json
{
  "schema_version": "wearable_compare_table_v1",
  "reference_date": "2026-05-31",
  "window_90d": { "start": "2026-03-03", "end": "2026-05-31", "n_days": 80 },
  "rows": [
    {
      "metric_id": "sleep_time_asleep",
      "row_kind": "comparable_90d",
      "snapshot_value": "8hr43min",
      "snapshot_unit": "hr",
      "snapshot_source": "WEARABLE_SNAPSHOT",
      "baseline_90d_value": "8.0",
      "baseline_90d_unit": "hr",
      "baseline_90d_range": "[0.4-9.9]",
      "baseline_source": "wearable.summary",
      "verdict": "above_mean",
      "verdict_note": "略高于 90d 均值"
    },
    {
      "metric_id": "sleep_deep",
      "row_kind": "snapshot_only",
      "snapshot_value": "1hr9min",
      "snapshot_unit": "hr",
      "snapshot_source": "WEARABLE_SNAPSHOT",
      "baseline_90d_value": "NO_BASELINE",
      "baseline_source": "none",
      "verdict": "snapshot_only",
      "verdict_note": "数仓无睡眠分期历史；禁止与 90d 对比"
    }
  ]
}
```

### 2.2 Field definitions

| Field | Type | Notes |
|-------|------|-------|
| `metric_id` | string | Align with `WearableSnapshotLedgerV1.metrics[].metric_id` or warehouse canonical |
| `row_kind` | enum | `comparable_90d` · `snapshot_only` · `omitted` (telemetry only, not into Tier0) |
| `snapshot_value` | string \| null | From WEARABLE_SNAPSHOT; null if none |
| `baseline_90d_value` | string \| `NO_BASELINE` | Only `comparable_90d` is number/range; stages fixed `NO_BASELINE` |
| `baseline_90d_range` | string | Optional, e.g. `[23.1-45.0]` |
| `baseline_source` | string | `wearable.summary` · `none` |
| `verdict` | enum | See §2.3; **produced by compute layer, LLM may not change** |
| `verdict_note` | string | Short Chinese note for LLM polish |

### 2.3 Verdict enum (compute layer)

| verdict | Condition (illustrative) |
|---------|--------------------------|
| `within_range` | snapshot falls inside baseline range |
| `above_mean` | snapshot > mean and still in range or slightly over |
| `below_mean` | snapshot < mean |
| `snapshot_only` | `row_kind=snapshot_only`; report screenshot value only |
| `no_snapshot` | 90d has baseline but screenshot has no KPI (omit row when comparable and snapshot null, see §3) |
| `insufficient_data` | both 90d and snapshot missing |

**Forbidden**: LLM qualitative that contradicts `verdict` (e.g. REM 137min vs invented 45min mean yet writes “decreased”).

---

## 3. MVP row matrix (mandatory contract)

### 3.1 Four 90d comparable items (mandatory)

| metric_id | 90d warehouse key | When screenshot has no KPI |
|-----------|-------------------|----------------------------|
| `sleep_time_asleep` | sleep mean + range | **Omit whole row** (prevent LLM inventing screenshot) |
| `hrv_rmssd_ms` | HRV mean + range | Omit whole row |
| `resting_heart_rate_bpm` | RHR mean + range | Omit whole row |
| `spo2_percent` | SpO2 mean + range | **Omit whole row** (PM ruling: no `[N/A]`) |

### 3.2 Mandatory NO_BASELINE rows (must appear if screenshot has them)

| metric_id | baseline_90d | Notes |
|-----------|--------------|-------|
| `sleep_deep` | `NO_BASELINE` | If screenshot ledger has a value, list snapshot; **strictly forbid** any 90d number |
| `sleep_rem` | `NO_BASELINE` | same |

### 3.3 Conditional rows — Workout (when user names it)

Trigger: `user_message` contains workout/锻炼/跑步 etc. (reuse existing intent vocab, **forbid brand/date hardcoding**).

| metric_id | row_kind | baseline |
|-----------|----------|----------|
| `workout_heart_rate_range_bpm` | `snapshot_only` | `NO_BASELINE` |
| `workout_count_recent` | `snapshot_only` | `NO_BASELINE` |

Screenshot has no workout KPI → single row `verdict=insufficient_data` + fixed copy “截图/定账暂无锻炼 KPI”.

### 3.4 3d-ε already in comparable

| metric_id | Warehouse column | Notes |
|-----------|------------------|-------|
| `respiratory_rate` | `respiratory_rate_bpm` | OCR+warehouse dual source; omit row if no screenshot |

### 3.5 P2 expansion (3d-δ)

- `activity_kcal` / `steps` (when export has data)
- Sleep-stage daily aggregate · HKWorkout import (see δ Spec)

---

## 4. CompareTable build (compute layer · not LLM)

### 4.1 Inputs

| Source | Module |
|--------|--------|
| Screenshot KPI | `WearableSnapshotLedgerV1` / `parsed_payload.wearable_metrics` |
| 90d mean and range | `get_health_data` + `build_analytics_snapshot` (or equivalent precomputed row) |
| Reference day / window | `effective_query_reference_date` · `default_wearable_window` |

### 4.2 Algorithm points

1. Walk §3.1 four: emit `comparable_90d` row only when **both snapshot and 90d exist**
2. Walk §3.2: if `sleep_deep` / `sleep_rem` snapshot exists → force `snapshot_only` + `NO_BASELINE`
3. SpO2: no snapshot → **do not emit a row** (not an N/A row)
4. Compute `verdict`: deterministic rules (thresholds env-configurable; default “align with mean ± semantic band”)
5. Output `CompareTableV1` + Tier0 markdown block

### 4.3 Suggested module boundary

| Module | Duty |
|--------|------|
| `pha/wearable_compare_table_v1.py` (new) | build · to_markdown · to_manifest_sidecar |
| `pha/harness_plan.py` | profile adds slot `WEARABLE_COMPARE_TABLE` |
| `pha/chat_service.py` | assemble Tier0; **do not** change LLM compare logic |

---

## 5. Harness inject flow

### 5.1 Tier0 Slot change (`wearable_screenshot_review`)

**Current**:

```text
WEARABLE_SNAPSHOT · WEARABLE_90D_SUMMARY · TASK
```

**After 3d-γ**:

```text
WEARABLE_SNAPSHOT · WEARABLE_COMPARE_TABLE · WEARABLE_90D_SUMMARY · TASK
```

| Slot | Permission |
|------|------------|
| `WEARABLE_SNAPSHOT` | Screenshot KPI original / ledger markdown |
| `WEARABLE_COMPARE_TABLE` | **Compare SSO**; LLM compare numbers may only cite this block |
| `WEARABLE_90D_SUMMARY` | Pearson · monthly · HRV lowest 5 days · lab anchors; **forbid** LLM extracting means from it for compare |
| `TASK` | See §5.3 |

`NUMERICS_MANIFEST` **may still be forbidden** (save tokens); Compare compliance **does not depend** on that slot (§6).

### 5.2 CompareTable Tier0 block format (human-readable)

```markdown
【Wearable Compare Table · Tier0 · SSO】
对比数字仅允许引用下表；禁止自行构造 90d 均值。
| metric_id | 截图 | 90d基线 | 区间 | verdict | 说明 |
| sleep_time_asleep | 8hr43min | 8.0 hr | [0.4-9.9] | above_mean | 略高于均值 |
| sleep_deep | 1hr9min | NO_BASELINE | — | snapshot_only | 数仓无分期历史 |
...
```

### 5.3 TASK contract (replace open-ended “three-step consult”)

**Must**:

- Only restate each `WEARABLE_COMPARE_TABLE` row + `verdict_note`
- Macro trends may cite non-mean sentences in `WEARABLE_90D_SUMMARY` (Pearson, monthly)
- User names workout → cite workout row in the table or insufficient copy

**Forbidden**:

- Extract “sleep/HRV/HR/SpO2 mean” from Summary for compare
- Write any 90d number or “warehouse-summary average” for `NO_BASELINE` rows

---

## 6. C-layer Audit strong decoupling + forced Fallback

### 6.1 Design principles

- Audit **always-on**: execute whenever `profile=wearable_screenshot_review`, **no need** for `NUMERICS_MANIFEST` Tier0 slot
- Audit inputs: `CompareTableV1` (structured) + reply text
- Mode: **forced Fallback** (PM ruling); not warn-only

### 6.2 Violation types

| Violation code | Detection |
|----------------|-----------|
| `compare_table_numeric_drift` | Reply has decimals/ranges inconsistent with Table |
| `compare_forbidden_90d_stage` | deep/rem co-occurs with 90d/warehouse-summary/average/mean |
| `compare_summary_mean_hijack` | Extract mean from Summary format to replace Table |
| `compare_verdict_contradiction` | Qualitative vs Table verdict clearly contradicts |
| `compare_incomplete:*` | User broadly asks “is this normal” but CompareTable rows not covered |
| `compare_missing_snapshot:*` | Discusses a metric but does not cite screenshot ledger value |
| `compare_no_baseline_subjective:*` | **3d-ε ✅** · [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md) §4 |

### 6.2.1 Intra-paragraph match (v2.3.17+)

`compare_forbidden_90d_stage` **forbids** cross-paragraph regex (`re.S` cross-line false kills already removed). Compliant wording: “深睡 … 无法与过去 90 天对比” and “睡眠总时长 … 90 天平均 8.0” in different paragraphs do not constitute a violation.

### 6.3 Deterministic Fallback (execution)

Any violation → **discard LLM compare paragraphs**, replace with:

```markdown
【穿戴对比 · 系统定账摘要】
{CompareTable markdown 全文}

说明：本轮对比仅以上表为准。数仓不含深睡/REM 90 天历史；分期仅报告截图定账。
```

Optional: keep one LLM-generated **non-numeric** greeting sentence (env switch, default off).

### 6.4 Relation to Numerics Manifest

| Component | After 3d-γ |
|-----------|------------|
| `NUMERICS_MANIFEST` slot | May still be forbidden |
| `build_numerics_manifest` | Optional sidecar; **not** a Compare-audit precondition |
| `audit_response_numerics` | lipid/combined path unchanged |
| `audit_wearable_compare_table` (new) | Wearable-specific; reads Table + text |

---

## 7. Deprecated flow (already cleaned · 3d-γ-b)

The following were physically deleted in **3d-γ-b**, replaced by Compare Audit + Fallback:

| Deleted item | Original location | Replacement |
|--------------|-------------------|-------------|
| ~~`repair_wearable_screenshot_numerics_reply`~~ | `wearable_harness.py` | `apply_compare_table_fallback_if_needed` |
| ~~`_audit_wearable_sleep_stage_90d_claims`~~ | `numerics_manifest.py` | `audit_wearable_compare_table` |
| 90d-summary stacked constraint sentences | `harness_plan.py` | CompareTable header + short footnote |

**Keep**:

- L0 OCR regex + golden fixture (§8)
- `maybe_deterministic_wearable_reply` (refuse when no KPI)
- Lane-O / `WearableSnapshotLedgerV1`

---

## 8. Golden OCR Fixture closeout (L0 maintenance contract)

### 8.1 Paths

```text
tests/fixtures/wearable/golden_ocr.json              ✅ γ-1.1
tests/fixtures/wearable/README.md                      ✅ γ-1.2
tests/fixtures/wearable/golden_wearable.py             ✅ γ-1.2
tests/fixtures/wearable/golden_compare_table.json      ✅ γ-1.3
scripts/pha_wearable_golden_fixture.py                 ✅ γ-1.R
```

### 8.2 Gate rules

- Any `wearable_snapshot_v1.py` regex / screen-rule change → **must** run golden OCR selfcheck
- Any expected KPI drift → **forbid merge** (unless fixture version bump + audit note)
- v1 sample source: real-device msg-310 six-screen OCR excerpt (de-identified)

### 8.3 Relation to 3d-β

3d-β adds split-screen L0.2 and async UX; **does not weaken** golden-fixture gates.

---

## 9. Coding waves (after Spec sign-off)

| PR | Scope | Gate |
|----|-------|------|
| **3d-γ-a** | `CompareTableV1` build + Harness slot + TASK | golden_compare unit test | ✅ |
| **3d-γ-b** | Audit decoupling + forced Fallback + deprecated cleanup | E2E G-Compare-* | ✅ |

**Parallel**: 3d-β Spec/coding (async pre-parse) does not block γ-a.

---

## 10. E2E acceptance (fold into D-3d-2)

| ID | Green | Red |
|----|-------|-----|
| **G-Compare-1** | Tier0 has `WEARABLE_COMPARE_TABLE` | Summary-prose compare only |
| **G-Compare-2** | Sleep/HRV/RHR match Table | unauthorized compare decimals |
| **G-Compare-3** | deep/rem snapshot only + NO_BASELINE | “warehouse-summary average” style |
| **G-Compare-4** | User mentions workout → Table has workout row | Completely unmentioned and ledger has KPI |
| **G-Compare-5** | Inject deliberate out-of-bound → Fallback ledger summary | Hallucination lands as-is |
| **G-T** | Latency does not regress vs 145s | — |

---

## 11. Relation to waves

```text
3c/3d (L0 Ledger + Lane-O)     ✅
        ↓
3d-γ (Compare Contract)        ✅ coded · Soul align v2.3.18
        ↓
3d-ε (Interpretation Audit)    ← wearable-interpretation-policy-v1
3d-δ (Fact Pipeline)           ← stage3d-delta-wearable-fact-pipeline-spec
        ↓
3d-β (split-screen + async UX)  parallel
        ↓
4a (OSS)                       can tell Compare SSO narrative externally
4b (CHB)                       full-text Compiler · reuse Table pattern
```

**Scientific ship order (revised · 2026-06-01)**:

```text
Read correctly  →  L0 + WearableSnapshot (3c/3d)
Compute clearly →  CompareTable SSO (3d-γ)
Don’t invent    →  Compare Audit + Fallback (3d-γ) + Interpretation Policy (3d-ε)
Expand facts    →  Metric Registry + daily aggregate (3d-δ)
Interpret       →  LLM (type-A judgments only) · CHB (4b)
OSS             →  4a + 5
```

---

## 12. PM final rulings (Q1–Q3 · closed)

| # | Question | **Ruling (2026-05-31)** |
|---|----------|-------------------------|
| Q1 | `above_mean` vs `within_range` threshold | **Range-align method**: inside 90d Baseline Range → `within_range`; only when outside Range or clearly drifted → `above_mean` / `below_mean` |
| Q2 | Does Fallback keep LLM non-numeric greeting | **No (default forbid)**. After Fallback, only CompareTable fact summary; no greeting hook |
| Q3 | Does CompareTable write into `parsed_json` | **Yes**. Follow-up reuse + Wave 4b CHB intermediate fact snapshot |

---

## 13. Phase 1 deliverables (γ-1.1 ~ γ-1.3 · already started)

| ID | Deliverable | Path | Status |
|----|-------------|------|--------|
| **γ-1.1** | Golden OCR six-screen fixture | `tests/fixtures/wearable/golden_ocr.json` | ✅ |
| **γ-1.2** | Fixture notes + assert module | `tests/fixtures/wearable/README.md` · `golden_wearable.py` | ✅ |
| **γ-1.3** | Golden CompareTable expected | `tests/fixtures/wearable/golden_compare_table.json` | ✅ |
| **γ-1.R** | Offline regression script | `scripts/pha_wearable_golden_fixture.py` | ✅ |

Gate: `python3 scripts/pha_wearable_golden_fixture.py` exit 0.

---

## 14. Revision history

| Version | Date | Notes |
|---------|------|-------|
| **v1.2** | 2026-06-01 | 3d-δ/ε dedicated-doc cites · Audit rule family complete · intra-paragraph match |
| **v1.1** | 2026-05-31 | 3d-γ-b: Audit always-on + forced Fallback + patch-debt cleanup |
| **v1.0** | 2026-05-31 | PM/Gemini sign-off · Q1–Q3 closed · γ-1.1~1.3 fixtures landed |
| v0.1 | 2026-05-31 | First draft: CompareTable SSO · Audit decoupling · MVP row matrix · Deprecated flow · PM/Gemini rulings folded in |

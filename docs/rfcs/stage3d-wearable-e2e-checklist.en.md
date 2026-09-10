# Stage 3d — Wearable real-device E2E red/green acceptance checklist (D-3d-2)

> **Language / 语言**：English (this document) · [中文](stage3d-wearable-e2e-checklist.md)

> **Status**: ✅ **Ratified (jurisprudence locked)** — real-device sign-off standard  
> **Version**: v1.0 (2026-06-27)  
> **Bound coding tasks**: C-1 (E1) · C-2 (E2–E3)  
> **Governing docs**: [`stage3d-gamma-wearable-compare-contract-spec.md`](../stage3d-gamma-wearable-compare-contract-spec.md) · [`wearable-interpretation-policy-v1.md`](../wearable-interpretation-policy-v1.md) · [`stage3d-delta-wearable-fact-pipeline-spec.md`](../stage3d-delta-wearable-fact-pipeline-spec.md) · [`stage3c-wearable-snapshot-bridge.md`](../stage3c-wearable-snapshot-bridge.md)  
> **Automation refs**: `scripts/pha_e2e_browser_battery_20x.py` · `scripts/pha_wearable_golden_fixture.py` · `scripts/pha_wearable_compare_table_selfcheck.py`

---

## 0. Acceptance principles

1. **Red/green table beats subjective feel**: any hard assert failure is **FAIL**, even if the answer “looks reasonable”.  
2. **CompareTable is the compare-number SSO**: 90-day compare numbers in the user-visible reply must match `WEARABLE_COMPARE_TABLE`, otherwise Fallback (G-Compare) must fire.  
3. **No 90-day compare hallucination on no-baseline metrics** (G-Interp): deep/REM and other `NO_BASELINE` rows must not use “warehouse-summary average” style sentences.  
4. **Real device ≡ API**: browser or `POST /api/chat` SSE both OK; judge by Harness `done.harness.plan.profile` and `compare_table_audit`.  
5. **Fixed env**: `PHA_UNIVERSAL_ATTACHMENT_LANE=1` · `PHA_HEALTH_INTENT_CATALOG=1` · build ≥ `pha-v2.3.32-full-import-only`.

---

## 1. Preflight

| # | Check | Expectation |
|---|-------|-------------|
| P1 | `GET /health` | `pha_build` non-empty |
| P2 | Warehouse | user `default` has ~90 days wearable import baseline |
| P3 | Assets | 6 Apple Watch screenshots (`IMG_6900`–`IMG_6905` or equivalent golden set) |
| P4 | Model | local Ollama `qwen2.5:7b-instruct` (or production-equivalent) reachable |

---

## 2. Scenario cases E1–E8

| ID | Scenario | Input | Expected Profile | Hard asserts (FAIL conditions) |
|----|----------|-------|------------------|--------------------------------|
| **E1** | First upload of 6 images | New session · upload 6 screens · “分析一下这张截图” | `wearable_screenshot_review` | `wearable_metrics` ingest ≥4 items; first answer has Compare structure or skip_llm ledger summary; **forbid** lifestyle; user answer has no “定账/数仓/Tier0” |
| **E2** | No-image follow-up reuse | Same session · no attachment · “图片里是什么” / “HRV 怎么样” | `wearable_screenshot_review` | Reuse session parse; `ingest` or compare audit non-empty; **forbid** inventing KPIs that contradict round 1 |
| **E3** | No-image empty session | New session · no attachment · same questions | Refuse or weak `wearable_only` | **Forbid** inventing concrete HR/HRV numbers; if profile empty, must clearly prompt upload |
| **E4** | Cross-family mix | Supplement Facts + Watch 6 screens same turn | hard conflict or specialized-lane split | Must SSE-status the conflict; **forbid** silent mix of supplement ledger and wearable KPIs |
| **E5** | Compare SSO | After E1, follow-up “和过去 90 天比怎么样” | `wearable_screenshot_review` | See **G-Compare-1～5** all green |
| **E6** | No-baseline subjective words | After E1, compare follow-up includes sleep stages | `wearable_screenshot_review` | See **G-Interp-1** |
| **E7** | Respiratory rate | 6 images include respiratory-rate screen | `wearable_screenshot_review` | See **G-Epsilon-1** |
| **E8** | Stage 90d | δ shipped and warehouse has sleep-stage import | `wearable_screenshot_review` | See **G-Delta-1～2** |

---

## 3. Guard asserts G-Compare (γ contract)

| ID | Assert | PASS | FAIL |
|----|--------|------|------|
| **G-Compare-1** | Tier0 contains `WEARABLE_COMPARE_TABLE` | Compare-turn plan assembly has Compare block | Prose-only “90-day average” with no table |
| **G-Compare-2** | Sleep/HRV/RHR number SSO | Compare values in user answer ∈ CompareTable rows | `compare_table_audit.violations` non-empty and no fallback |
| **G-Compare-3** | Deep/REM no 90d hallucination | `row_kind=snapshot_only` or `NO_BASELINE` | Phrases like “warehouse-summary average” / “last 90 days deep sleep” |
| **G-Compare-4** | Workout conditional row | User mentions workout and ledger has workout KPI → Table has a row | Ledger has workout but Table is completely missing |
| **G-Compare-5** | Forced Fallback | Deliberately out-of-bound reply is audit-replaced | Hallucinated compare numbers land to the user as-is |

---

## 4. Guard asserts G-Interp (ε interpretation compliance)

| ID | Assert | PASS | FAIL |
|----|--------|------|------|
| **G-Interp-1** | NO_BASELINE subjective words | No-baseline rows use “this screenshot only” style wording | NO_BASELINE rows say “adequate” / “low, be alert” etc. with no baseline and audit did not stop |
| **G-Interp-2** | Audit fire | When `compare_no_baseline_subjective` hits, `fallback_applied=true` | Violation still ships LLM original |

---

## 5. Guard asserts G-Delta / G-Epsilon (δ/ε fact pipeline)

| ID | Assert | PASS | FAIL |
|----|--------|------|------|
| **G-Delta-1** | Deep/REM 90d | δ enabled and warehouse has stages → Compare row `comparable_90d` matches SQL | Warehouse has data but Table marks `snapshot_only` and user asked trend |
| **G-Delta-2** | Workout aggregate | After HK Workout import, count/HR range match Table | Deviation > contract tolerance (see δ Spec) |
| **G-Epsilon-1** | Respiratory rate | Screenshot has respiratory rate → Compare has at least one `respiratory_rate` row | OCR has a value but Table has no row |

---

## 6. Execution and persistence

```bash
# Real-device/API full (needs 8788 + assets)
PHA_PORT=8788 PHA_UNIVERSAL_ATTACHMENT_LANE=1 \
  .venv/bin/python scripts/pha_e2e_browser_battery_20x.py

# Wearable golden fixture (offline)
.venv/bin/python scripts/pha_wearable_golden_fixture.py
.venv/bin/python scripts/pha_wearable_compare_table_selfcheck.py
```

**Report persistence**: JSONL + markdown summary under `PHA_E2E_REPORT_DIR`; FAIL items must cite this table’s IDs (e.g. `E1`, `G-Compare-3`).

---

## 7. Public Gate binding

| Gate | Condition |
|------|-----------|
| **3d real-device sign-off** | E1–E3 **PASS** (C-1/C-2) |
| **Compare contract** | E5 + G-Compare **all green** |
| **δ/ε extension** | E7–E8 **PASS** after warehouse/import ready |
| **OSS Wave 4a** | This checklist E1/E5 + Nightly 148/164 same-green |

---

## 8. Revision history

| Date | Notes |
|------|-------|
| 2026-06-27 | v1.0 first version: promoted from doc-roadmap D-3d-2 to RFC red/green table |

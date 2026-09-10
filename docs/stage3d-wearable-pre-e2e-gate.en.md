# Stage 3d · Real-device E2E pre-gate (architectural completeness)

> **Language / 语言**：English (this document) · [中文](stage3d-wearable-pre-e2e-gate.md)

> **Current build**: `pha-v2.3.27-wave3d-post-e2e-task-audit-ux`  
> **Purpose**: close the coding loop before 6-image real-device; avoid “UI/model” masking pipeline gaps.  
> **E2E**: ✅ see [`stage3d-wearable-e2e-pass-2026-06-04.md`](stage3d-wearable-e2e-pass-2026-06-04.md)

---

## 1. Coding-wave status

| Wave | Content | Build | Status |
|------|---------|-------|--------|
| **3d-γ** | CompareTable + Audit + Fallback | v2.3.18+ | ✅ |
| **3d-ε** | Respiratory rate into table + NO_BASELINE subjective-word audit | v2.3.19 | ✅ |
| **3d-δ-a** | Deep/REM daily aggregate + comparable | v2.3.20 | ✅ |
| **3d-δ-b** | HKWorkout import + workout comparable | v2.3.21 | ✅ code · ⏳ **needs Workout incremental backfill** (see G3) |
| **3d-δ-c** | Registry-driven build (de-hardcode) | v2.3.23 | ✅ JSON + `wearable_metric_registry.py` · `GET/POST /data/sync-module*` |
| **3d-ε+** | Screenshot-anchored day + range-endpoint audit authorization | v2.3.24 | ✅ `snapshot_reference_date` · `17.5` drift fix |
| **3d-ux-a** | Hybrid Fallback keeps LLM advice | v2.3.26 | ✅ |
| **3d-ux-b** | TASK/audit: stages with baseline must not claim “no history” | v2.3.27 | ✅ C-18 |

---

## 2. Must-do before real device (ops)

| # | Action | Acceptance |
|---|--------|------------|
| **G0** | `/health` → `pha-v2.3.21-wave3d-delta-b-workout-import` | JSON `pha_build` matches |
| **G1** | `python3 scripts/pha_wearable_compare_table_selfcheck.py` | PASS |
| **G2** | `python3 scripts/pha_sleep_stage_rollup_selfcheck.py` | PASS |
| **G3** | **Workout incremental backfill** (recommended, do not empty current warehouse): `python3 scripts/pha_backfill_workouts_from_zip.py /path/to/export.zip` | `wearable_workout_sessions` row count > 0 |
| **G3′** | Full re-import zip (**will empty** that user’s wearable tables then import) | Only when no zip or a full repair is needed |
| **G4** | `python3 scripts/pha_workout_import_selfcheck.py` | `workout sessions > 0` and HR comparable |
| **G5** | (optional) `recompute_user_data_integrity` / start dedupe | Sleep union + stages + workout rollup |

> **Note**: δ-b only parses **newly imported** `<Workout>` elements; if the historical DB has no `wearable_workout_sessions` rows, CompareTable workout stays `NO_BASELINE` (matches the facts).

---

## 3. Real-device 6-image scenarios (**E1 passed · 2026-06-04**)

| ID | Steps | Expectation |
|----|-------|-------------|
| **E1** | New session · 6 images · standard questions (incl. work out / 90 days / sleep) | ✅ script + real device; deep/REM narrative hallucination tightened by C-18 |
| **E2** | Same session, no-image follow-up | Reuse `parsed_json` · status “already reused attachment parse” |
| **E3** | DeepSeek vs Qwen | If audit fails, **the same Fallback**; do not judge data truth from model style |
| **E4** | DB spot check | `parsed_json.wearable_compare_table_v1` numbers match the UI reply |

Audit companion doc: [`stage3d-wearable-real-device-audit-2026-06-01.md`](stage3d-wearable-real-device-audit-2026-06-01.md)

---

## 4. Known limits (non-blocking for real device, but know them)

| Item | Notes |
|------|-------|
| **UI-1** | Chat bubbles do not show attachment thumbnails (already on roadmap) |
| **ε+ drift** | v2.3.24 already authorizes screenshot range endpoint `17.5`; warehouse max may still be 15.0 (verdict follows the table) |
| **Sleep range 0.4h** | Warehouse includes abnormally short-sleep days; δ-ux may later switch to P5–P95 |
| **Workout count** | OCR “last 4 weeks 8 times” ↔ baseline **28-day rolling count** (see `workout_storage.WORKOUT_RECENT_WINDOW_DAYS`) |

---

## 5. Revision history

| Date | Notes |
|------|-------|
| 2026-06-01 | First version: δ-a/δ-b coding done · real-device pre-gate G0–G5 |

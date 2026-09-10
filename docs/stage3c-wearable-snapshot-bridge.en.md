# Stage 3C-Wearable — Wearable Snapshot Bridge spec

> **Language / 语言**：English (this document) · [中文](stage3c-wearable-snapshot-bridge.md)

> **Version**: v0.1 (2026-05-27)  
> **Status**: ✅ Wave 3c coded · ✅ Wave 3d merge-coerce coded (`pha-v2.3.9-wave3d-wearable-merge-coerce`) · ⏳ live E2E pending green  
> **Governing law**: [`pha-pm-constitution.md`](pha-pm-constitution.en.md) §4 · [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) v0.3  
> **Review**: Wenhui · Gemini joint review board approved (Apple Watch live red-light audit)

---

## 0. Purpose

Define the full contract from **Apple Health / Watch UI screenshots** to a **Harness answer** when `document_family=wearable`, ending the “wearable screenshots wrongly enter supplement `LabelLedgerV1` ledger → supplement-refusal template” same-treatment-for-different-diseases bug.

**Readers**: perception Worker, Harness, session focus, Telemetry, F-layer Fixture engineers.

---

## 1. Problem (live red light · audited)

| Symptom | Root cause (architecture) |
|------|----------------|
| User uploads 6 Health screenshots asking “are these metrics normal” | Chat attachments **always** `finalize_attachment_parse` → `LabelLedgerV1` |
| Reply “please retake Supplement Facts” | `maybe_deterministic_attachment_reply` **only serves the supplement family** |
| Gemini can answer, PHA refuses | Gemini multimodal reads the image; PHA **did not** write screenshot facts into Tier0 |

**Not the root cause (do not spend more people)**: tweaking supplement Prompt, adding NOW/Choline assertions, Watch-specific hardcoded crop targets.

---

## 2. Anti-corruption constitution (Wearable-specific)

| ID | Rule |
|------|------|
| **W1** | `document_family=wearable` **must not** call LabelLedgerV1 G1–G6 (`no_ingredient_rows` etc.) |
| **W2** | `document_family=wearable` **must not** call `maybe_deterministic_attachment_reply` (supplement copy) |
| **W3** | Wearable facts come **only** from `WearableSnapshotLedgerV1` + OCR/VLM structured fields; L3 must not invent unseen numbers |
| **W4** | F-layer Fixture `apple_health_screens_6panel` **must not** assert NOW/Choline/Facts table |
| **W5** | zh/en key names follow Spec §0.1 (`metric_id`, `source_screen`, `parse_confidence`) |

---

## 3. L0 data chain (target)

```text
[attachment bytes]
  → L0.0 media_route (raster_photo)
  → L0.2 layout_region[] (generic UI blocks, see stage3b §7.2)
  → L0.4 Lane-O / Lane-V (wearable-specific Schema, not lab/supplement JSON)
  → L0.5 document_family = wearable (structure triggers: HRV|Sleep|SpO2|Heart Rate|Apple Health…)
  → L0.6 WearableSnapshotLedgerV1 ledger
  → P-layer G_wearable_* (not G1 ingredient rows)
  → Harness profile = wearable_screenshot_review
  → L3 synthesis (may cite WEARABLE_90D_SUMMARY warehouse compare “vs the past”)
```

**Physically isolated from the supplement chain**: do not call `enrich_parsed_payload` / `finalize_parsed_payload(LabelLedger)` before `document_family` is decided.

---

## 4. `WearableSnapshotLedgerV1` Schema

```json
{
  "schema_version": "wearable_snapshot_v1",
  "attachment_count": 6,
  "source_app_hint": "apple_health",
  "screens": [
    {
      "index": 0,
      "screen_type": "heart_rate",
      "date_hint": "2026-05-19",
      "ocr_excerpt": "…",
      "layout_region_types": ["dense_text_block"]
    }
  ],
  "metrics": [
    {
      "metric_id": "hrv_rmssd_ms",
      "value": "40",
      "unit": "ms",
      "window": "today_average",
      "source_screen_index": 4,
      "source_line": "AVERAGE 40 ms"
    },
    {
      "metric_id": "sleep_time_asleep",
      "value": "7",
      "unit": "hr",
      "sub_value": "1 min",
      "window": "2026-05-17",
      "source_screen_index": 3
    }
  ],
  "parse_confidence": "high",
  "reject_reasons": [],
  "warnings": ["layout_panel_hint_missing"],
  "perception_channel": "vision_structured",
  "ledger_markdown": "【穿戴截图定账 · 供核对】\n- HRV …"
}
```

### 4.1 `metric_id` enum (extensible · not an exhaustive hardcode)

| `metric_id` | Chinese note | Typical UI source |
|-------------|----------|----------------|
| `hrv_rmssd_ms` | HRV | Heart Rate Variability |
| `resting_heart_rate_bpm` | Resting HR | Heart Rate / Resting |
| `heart_rate_range_bpm` | HR range | 52–64 BPM |
| `spo2_percent` | SpO2 | Blood Oxygen |
| `respiratory_rate` | Respiratory rate | Respiratory Rate |
| `sleep_time_asleep` | Sleep duration | Sleep · Time Asleep |
| `sleep_deep` | Deep sleep | Deep |
| `sleep_rem` | REM | REM |
| `sleep_awake` | Night awake | Awake |
| `workout_energy_kcal` | Workout energy | Workouts |
| `workout_duration_min` | Workout duration | Workouts |

**Rule**: `metric_id` comes from a **config table + OCR line patterns** (BPM, %, hr, min, ms). **Forbid** branches like “if NOW then…”.

### 4.2 `screen_type` enum

`heart_rate` | `spo2` | `respiratory_rate` | `sleep` | `hrv` | `workout` | `unknown`

---

## 5. P-layer gates (G_wearable · split from supplement G1–G6)

| ID | `parse_confidence=low` condition |
|------|------------------------------|
| **GW1** | `metrics` empty and no `screens` have `ocr_excerpt` |
| **GW2** | User asks “is this normal / compare” and parseable `metric_id` rows < 1 |
| **GW3** | Multi-image `attachment_count` ≥ 2 and merged `screens` missing > 50% |

**Forbidden**: using `no_ingredient_rows` / `missing_authoritative_panel` (supplement-only) for wearable.

**`warnings[]`**: `ocr_sparse`, `vlm_json_unstable`, `layout_panel_hint_missing` — **do not alone cause low**.

---

## 6. Harness · `wearable_screenshot_review` Profile

### 6.1 Dispatch (C layer · deterministic)

Any one of these takes this profile first (above `attachment_asset_qa`):

1. `document_family=wearable` (L0.5 post-classify); or
2. User message hits `intent_gates._WEARABLE_RE` **and** this turn has an attachment parse result.

**Forbidden**: defaulting to `attachment_asset_qa` while `document_family` is unknown.

### 6.2 Tier0 slots

| Slot | Content |
|------|------|
| `MASTER_ANCHOR` | User master ledger |
| `WEARABLE_SNAPSHOT` | `WearableSnapshotLedgerV1.ledger_markdown` + structured JSON summary |
| `WEARABLE_90D_SUMMARY` | SQLite last 90 days (compare “vs the past”) |
| `TASK` | Wearable-screenshot review task (see §6.3) |
| `DATA_AVAILABILITY` | optional · same as episodic_bridge |

**Forbidden inject**: `ATTACHMENT_LABEL` (supplement ledger block) when `document_family=wearable`.

### 6.3 TASK points (template-level · not case-by-case)

- Must cite **each metric** in `WEARABLE_SNAPSHOT`; must not cite `ingredient_rows`.
- When comparing with `WEARABLE_90D_SUMMARY`, must state “screenshot day” vs “warehouse interval” sources.
- Forbid suggesting a Supplement Facts retake.
- Forbid attributing screenshot numbers to a supplement ingredient (unless the user explicitly asks drug interaction and K-layer lookup hits).

---

## 7. Session focus · `session_turn_focus`

| Field | Rule |
|------|------|
| `document_type` | `wearable` (**forbid** default `supplement_label`) |
| Focus switch | If previous turn `supplement`, this turn `wearable` → `merge_family_conflict` + clear focus or explicit overwrite |
| `RECALL_FOCUS` | Anchor `WEARABLE_SNAPSHOT` facts, **not** `ATTACHMENT_LABEL` |

---

## 8. Gemini collaboration boundary (§ SOTA · do not copy wholesale)

| Gemini practice | PHA adopts | PHA rejects |
|-------------|----------|----------|
| Whole-image multimodal KPI read | Lane-V + wearable Schema | Structure-less over-narrative |
| Historical-date compare narrative | WEARABLE_90D_SUMMARY + user master ledger | Invention without Telemetry |
| Training advice | L3 under TASK constraints | Writing advice into `metrics[]` |

---

## 9. F-layer Fixture · `apple_health_screens_6panel`

| Item | Notes |
|------|------|
| Input | 6 desensitized Health UI screenshots (HR / SpO2 / respiratory / sleep / HRV / workout) |
| Assert | `document_family=wearable`; `metrics` contain `hrv_rmssd_ms`, `spo2_percent`, `sleep_time_asleep`, etc. **≥N items** |
| Forbidden | `brand=NOW`, `choline`, `parse_confidence=low` + supplement-refusal copy |
| Script | `scripts/pha_e2e_wearable_screens_real.py` (planned) |

---

## 10. Implementation waves (Wave 3b → 3c)

| Wave | Delivery | Gate |
|------|------|------|
| **3b** | This spec + routing stop-bleed (non-supplement family does not enter LabelLedger / supplement refusal) | Self-check + live no longer shows Facts refusal |
| **3c** | `WearableSnapshotLedgerV1` + perception Worker + Harness profile | F-layer 6-image Fixture |
| **3d** | `unknown+wearable` coerce · no-data refusal · follow-up reuse | ✅ coded · see [`stage3d-wearable-merge-and-gates-spec.md`](stage3d-wearable-merge-and-gates-spec.md) · ⏳ E2E |
| **3d-β** | Per-screen KPI · 6-image async UX · F-layer fixture | 📋 Spec pending |

---

## 11. Industry SOTA benchmark

| Capability | Industry reference | PHA localization |
|------|----------|------------|
| Multimodal screen read | GPT-4V / Gemini whole image | Lane-V + layout_region slices |
| Structured health data | Apple Health export / FHIR | `WearableSnapshotLedgerV1` |
| Traceability | OpenAI JSON mode + log | `merge_trace` / Telemetry |
| Low compute | — | Lane-O first + optional local 11B |

---

## 12. Revision log

| Date | Version | Notes |
|------|------|------|
| 2026-05-27 | v0.1 | First draft: Gemini review board approved; WearableSnapshotLedgerV1; profile; focus isolation; F-layer plan |
| 2026-05-27 | v0.2 | Wave 3c merge: `wearable_snapshot_v1` · `wearable_screenshot_review` Harness · multi-image merge |
| 2026-05-30 | v0.3 | Wave 3d merge: merge coerce · wearable refusal · attachment recall; live E2E pending green |

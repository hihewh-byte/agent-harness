# Stage 3A.1 — Attachment single-asset Q&A governance (RFC)

> **Language / 语言**：English (this document) · [中文](stage3a1-attachment-qa-governance.md)

> **Baseline**: `pha-v2.3.3-stage3a-vision-ocr-guard`  
> **Target build**: `pha-v2.3.3-stage3a1-attachment-qa-governance`  
> **Status**: ✅ coded

## 0. Problem

When the user “uploads a supplement / product label + short question (what is it / how does it help me)”, the system should:

- **Must** cross-reason against individual background (meds, training, contraindications);
- **Must not** recite the full supplement schedule, lipid / HRV textbook as the answer body.

Root cause: full `SUPPLEMENT_BG` + wide `combined_review` TASK + Soul three-step consult → LLM pleasing.

## 1. Ruling

| Item | Conclusion |
|------|------|
| Combine with history? | ✅ Must (focused slice, not a full dump) |
| Hardcoded drug names | ❌ Forbidden; routing/filter use layout, category, OCR token only |
| Relation to Stage 3 | 3A.1 fixes the experience first; Stage 3 Guided fetch does not replace this governance |

## 2. Mechanism

### 2.1 Profile: `attachment_asset_qa`

Trigger (all must hold):

1. This turn’s attachment parsed successfully (`vision_summary` or `narratives` non-empty);
2. User raw text ≤220 chars and matches short-question intent (what is it / how does it help / is it suitable for me, etc.);
3. User raw text does **not** explicitly ask lipids / labs / HRV / wearable compare.

Slots:

- Tier0: `MASTER_ANCHOR`, `TASK`, `SUPPLEMENT_BG` (focused background)
- Forbidden: `PATIENT_STATE_*`, `DOSSIER_*`, `WEARABLE_*`, `EVIDENCE_CATALOG`, `fetch_evidence_by_id`

### 2.2 Output constitution (TASK + Soul addendum)

See `ATTACHMENT_ASSET_QA_TASK` / `ATTACHMENT_QA_SOUL_ADDENDUM` in `pha/attachment_asset_qa.py`.

### 2.3 Focused background `build_focused_background_for_attachment_qa`

- Always include `medication` notes (char cap);
- `supplement` / `sleep_lifestyle` / `symptom` / `general` only when OCR/summary **tokens** intersect the note body;
- Exclude `unstructured_vision` audit rows;
- Total length about ≤ `PHA_ATTACHMENT_QA_BG_MAX_CHARS` (default 1400).

## 3. Environment variables

| Variable | Default | Notes |
|------|------|------|
| `PHA_ATTACHMENT_QA_BG_MAX_CHARS` | `1400` | Focused-background cap |

## 4. Acceptance

- [ ] Upload supplement label + “how does it help me” → Harness `plan.profile=attachment_asset_qa`
- [ ] Answer contains this-turn asset ledger + 1–3 cross-points; **no** full historical plan log
- [ ] Same question + explicit “lipids/HRV” → **does not** enter `attachment_asset_qa`
- [ ] Self-check `scripts/pha_stage3a1_attachment_qa_selfcheck.py` passes

## 5. Follow-on (3A.3 / Stage 3)

- Cross-check JSON shim (`current_asset_facts` / `conflict_flags` / `forbidden_topics`)
- Harness `response_obesity` telemetry
- Guided fetch shares the focus-asset contract with `attachment_asset_qa`

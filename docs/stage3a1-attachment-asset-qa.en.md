# Stage 3A.1 — Attachment Asset QA

> **Language / 语言**：English (this document) · [中文](stage3a1-attachment-asset-qa.md)

> **Baseline**: `pha-v2.3.3-stage3a-vision-ocr-guard`  
> **Build**: `pha-v2.3.3-stage3a1-attachment-qa`  
> **Status**: coding

## 0. Problem

When the user uploads a supplement / product-label image and asks “what is this? how does it help me?”:

- **Correct**: cross-reason against individual background (meds, training, sleep, etc.).
- **Wrong**: reciting the full `SUPPLEMENT_BG` regimen plus lipid / HRV textbook (answer obesity).

Root cause: **full background dump + wide profile (`combined_review`) + no output constitution**, amplified by LLM pleasing.

## 1. Goals

| Must | Forbidden |
|------|------|
| Ledger the current-turn asset (ingredients, dose, label warnings) | Recite the user’s entire known supplement schedule |
| Write only individual cross-points related to this asset | Unrelated drugs / meal slots / HRV textbook |
| Write a medication conflict if present; one sentence if none | Ask the user to “send labs again” unless they explicitly ask about labs |

**Iron rule**: classify and trim using **layout / category / OCR token** only. **Do not** hardcode any product name or ingredient name in code.

## 2. Mechanism

### 2.1 Profile: `attachment_asset_qa`

Trigger (all must hold):

1. This turn’s attachment parsed successfully or OCR fallback (`parsed_payload` non-empty).
2. User raw text (**excluding** the attachment summary block) matches a short-question intent (structural regex: what is it / help / suitable for me, etc.) and length ≤ `PHA_ATTACHMENT_QA_MAX_USER_CHARS` (default 120).

Routing calls `build_turn_evidence_plan` on **user raw text** so unrelated words in the Vision summary do not trigger `combined_review`.

### 2.2 Slots

| Tier | Slots |
|------|--------|
| tier0 | `MASTER_ANCHOR`, `TASK`, `SUPPLEMENT_BG` (focused slice) |
| tier1 | (empty) |

Forbidden: `DOSSIER_*`, `WEARABLE_90D_SUMMARY`, `EVIDENCE_CATALOG`, `LDL_AUTHORITY`, `NUMERICS_MANIFEST`, tools, snapshot.

### 2.3 Focused background (3A.2 input trim)

`build_focused_background_for_attachment_qa(focus_text)`:

- Extract **structure tokens** (≥4 alphanumeric chars) from this turn’s `vision_summary` / OCR text.
- Background-row keep rules:
  - `medication` / `symptom`: always keep (conflict check).
  - `supplement` / `sleep_lifestyle`: keep only on substring match with any token.
- Caps: row count + total chars (env-configurable).

### 2.4 Output-behavior constitution (TASK + Soul addendum)

See `ATTACHMENT_QA_TASK_TEXT` / `ATTACHMENT_QA_SOUL_ADDENDUM` in `pha/attachment_asset_qa.py`.

## 3. Relation to Stage 3

| Stage | Relation |
|------|------|
| 3A.1 | Prompt/TASK + profile + background slice (this file) |
| 3A.3 | Optional: cross-check JSON shim into Context header |
| Stage 3 | Guided fetch; does not replace this section’s “no recitation” governance |

## 4. Environment variables

| Variable | Default | Notes |
|------|------|------|
| `PHA_ATTACHMENT_QA_ENABLED` | `1` | Master switch |
| `PHA_ATTACHMENT_QA_MAX_USER_CHARS` | `120` | Short-question cap |
| `PHA_ATTACHMENT_QA_BG_MAX_CHARS` | `900` | Focused-background char cap |
| `PHA_ATTACHMENT_QA_BG_MAX_ROWS` | `6` | Focused-background row cap |

## 5. Acceptance

- [ ] Attachment + “what is it / how does it help me” → profile=`attachment_asset_qa`
- [ ] Answer contains this-turn label points and **does not** contain a full historical regimen log
- [ ] Harness: `intent_route.authoritative_profile` is `attachment_asset_qa`
- [ ] No new product-name / ingredient-name hardcoding in the codebase

## 6. 3A.3 reserved (not in this build)

`TurnFocusCrossCheck` JSON: `current_asset_facts`, `relevant_background_hits`, `conflict_flags`, `forbidden_topics` — for Harness telemetry and Stage 3 reuse.

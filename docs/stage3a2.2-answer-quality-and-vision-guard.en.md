# Stage 3A.2.2 — Answer-quality tighten + Vision ledger and multi-image merge (RFC)

> **Language / 语言**：English (this document) · [中文](stage3a2.2-answer-quality-and-vision-guard.md)

> **Baseline**: `pha-v2.3.3-stage3a2.1-response-ux-causal-anchor`  
> **Target build**: `pha-v2.3.3-stage3a2.2-answer-quality-vision-guard`  
> **Status**: ✅ coded  
> **Depends on**: [3A.2.1](stage3a2.1-response-ux-and-causal-anchor.en.md)

---

## 0.1 Chief-designer ruling (2026-05)

| # | Issue | Ruling |
|---|------|------|
| 1 | **Single-image strategy** | **Do not force** a back-photo; **do not forbid** outputting choline/inositol (extract faithfully if Facts are visible). Require: **read the visible face correctly + structured ledger + do not collapse interpretation into a single “lecithin”**. |
| 2 | **Multi-image** | **V1 must-do**: multi-select upload + front/back **merged ledger** (in this stage, not 3A.3). |
| 3 | **NOW two-image ground truth** | Front: PS **100 mg** hero; back Facts: PS 100 mg, Choline 100 mg, Inositol **50 mg**. |

---

## 1. Goals

| # | Goal |
|---|------|
| G1 | Single image: output only ingredients/doses **visible in the image**; forbid evidence-free “lecithin” monopoly |
| G2 | Multi-image: merge into an **ingredient-table ledger** + **label excerpt** injected into Context |
| G3 | Ecommerce-screen guard: Vision hallucinating a lab report → OCR / refuse hallucination |
| G4 | User-visible **label excerpt (please verify)** |
| G5 | Answer quality: grounds-contradiction fuse, lipid causal sentence, Harness `attachment_qa_mode`, etc. |

---

## 2. Vision ledger (`vision_label_ledger.py`)

### 2.1 Layout

- `ecommerce_product_screenshot` (cart / buy-now / pagination dots, etc.)
- `supplement_facts_panel` (Supplement Facts + Serving Size)
- `supplement_front` (hero ingredient + mg, no Facts table)

### 2.2 Single-image principle

- Front-only: **list visible rows faithfully** (e.g. PS 100 mg); **must not** invent inositol/choline doses that exist only on the back.
- **Do not force** a second photo; if the model must mention an ingredient not seen in the image, it must write “not seen in the label excerpt”.

### 2.3 Multi-image merge (V1 must-do)

- API: `attachment_paths[]` + `attachment_names[]` (compatible with single `attachment_path`)
- Server parses each image → `merge_parsed_payloads()`
- Facts face wins ingredient rows; front fills brand / claims / size

### 2.4 User-visible block

```text
【标签摘录 · 系统自动识别 · 请核对】
- …
【成分定账 · 每份】
- …
```

### 2.5 Environment variables

| Variable | Default |
|------|------|
| `PHA_VISION_ECOMMERCE_GUARD` | `1` |
| `PHA_VISION_OCR_REQUIRED_FOR_ATTACH` | `1` |
| `PHA_LABEL_LEDGER_MAX_CHARS` | `2200` |

---

## 3. Answer quality (TASK / Harness)

- §3.1–3.3 same as the previous version (grounds contradiction, lipid causality, anti-list)
- `intent_route` extensions: `attachment_qa_mode`, `session_focus_turns_remaining`, `vision_parse_confidence`, `document_type`

---

## 4. Implementation order

```text
V0  vision_label_ledger + OCR guard + ledger block
V1  multi-image upload/parse/merge (API + app.js)
V2  TASK quality + Harness fields
V3  selfcheck + golden (IMG_6800/6801)
```

---

## 5. Acceptance

- [ ] Front-only upload: ledger contains PS 100 mg (or excerpt equivalent); no CBC-dominated answer
- [ ] Dual upload 6800+6801: ledger contains PS/Choline 100 mg, Inositol 50 mg
- [ ] First paragraph of the dialog contains “label excerpt”; do not call the three ingredients “lecithin”
- [ ] `pha_stage3a22_selfcheck.py` PASS

---

*Revised: Cursor · 2026-05*

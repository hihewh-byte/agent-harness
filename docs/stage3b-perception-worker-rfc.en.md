# Stage 3B — Perception Worker (platform-level attachment ledger) RFC

> **Language / 语言**：English (this document) · [中文](stage3b-perception-worker-rfc.md)

> **Version**: v1.0 (2026-05-26 文辉 approved start)  
> **Status**: 🚧 **3B-α implementing** — `pha-v2.3.3-stage3b-perception-worker-alpha`  
> **β Spec** (anti-corruption red lines · weight Merge · **media routing + post-hoc `document_family`**): [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) **v0.2** §1.4 · §7.0–§7.8  
> **Priority**: **P0 · blocking** — not green, do not claim “two-image supplement Q&A” production-ready  
> **Depends**: 3A routing/focus/causal ([`stage3a-regression-checklist-v1.md`](stage3a-regression-checklist-v1.md))  
> **Blueprint**: [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) §2.1 · §2.2 · Stage 3B

---

## 0. Problem statement

Real-device retro (DeepSeek-R1, Qwen2.5 7B) consistently showed:

| Symptom | Root-cause layer |
|---------|------------------|
| Brand ZENS/ZENESSE, missed Inositol 50mg | **L0 perception** did not produce a reliable ledger |
| Only answered “what is it”, missed “how does this help me” | TASK/structure (3A) + missing ledger stacked |
| “Harness pre-inject” misleads | Product copy; attachment mode does not call tools by design |
| Lipid attribution chaos | 3A causal anchor; **must not** use L3 to invent off-ledger doses |

**Conclusion**: L3 (7B/14B) duty is **natural-language synthesis**; OCR, multi-image merge, and ingredient tables must be produced by a **3B-α deterministic Perception Worker** as **`LabelLedgerV1`**, C-layer validated, then injected into the protected `ATTACHMENT_LABEL` slot.

---

## 1. Goals and non-goals

### 1.1 Goals (3B-α)

| ID | Goal |
|----|------|
| G1 | 1–N images → single `LabelLedgerV1` (auditable JSON) |
| G2 | **v1 blocking golden**: IMG_6800 + IMG_6801 all green |
| G3 | On low confidence **hard refuse/ask** (UI + TASK); forbid inventing doses |
| G4 | L3 **forbidden to invent** numbers outside Manifest/ledger (TASK constitution) |
| G5 | On send, **reuse** picker-time ledger; forbid default double full Vision |
| G6 | Telemetry: paths, merge, ingredients, confidence, channel |

### 1.2 Non-goals (this RFC)

- ❌ Brand/ingredient allowlist regex tables  
- ❌ LangChain replacing Harness  
- ❌ 3B-β multi-LLM sub-agents (separate RFC)  
- ❌ Hybrid Guided fetch to production  
- ❌ Extracting pha-core as a package  

---

## 2. Sub-phases (no skipping)

| Phase | Shape | LLM | Admission |
|-------|-------|-----|-----------|
| **3B-α** | OCR → classify → extract → merge → Schema validate | Optional Vision **validate** only (Flag, T2+) | **Current** |
| **3B-β** | Vision structured Worker (JSON ledger) | VLM inside Worker; not into Harness main chat | See [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) |

---

## 3. `LabelLedgerV1` ledger Schema

### 3.1 Top-level fields

```json
{
  "schema_version": "label_ledger_v1",
  "attachment_count": 2,
  "brand": "NOW",
  "product_title": "Phosphatidyl Serine",
  "package_size": "120 Veg Capsules",
  "layout_hints": ["ecommerce_product_screenshot", "supplement_facts_panel"],
  "ingredient_rows": [
    {
      "name": "Phosphatidyl Serine",
      "amount": "100",
      "unit": "mg",
      "source_image_index": 0,
      "source_line": "Phosphatidyl Serine 100 mg"
    }
  ],
  "parse_confidence": "high",
  "reject_reasons": [],
  "perception_channel": "ocr_only",
  "ocr_char_count": 842,
  "ledger_markdown": "【标签摘录】…【成分定账】…"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `schema_version` | ✅ | Fixed `label_ledger_v1` |
| `attachment_count` | ✅ | Input image count |
| `brand` | Conditional | Required at high confidence; may be empty at low |
| `product_title` | Recommended | Front main title |
| `package_size` | Optional | Spec |
| `layout_hints[]` | ✅ | See §3.3 |
| `ingredient_rows[]` | Conditional | See §3.2 |
| `parse_confidence` | ✅ | `high` \| `low` |
| `reject_reasons[]` | Optional | Enum, see §5 |
| `perception_channel` | ✅ | `ocr_only` \| `ocr_plus_vision_validate` |
| `ledger_markdown` | ✅ | Text injected into `ATTACHMENT_LABEL` (compatible with 3A.2.2 block) |

### 3.2 `ingredient_rows` elements

| Field | Required | Notes |
|-------|----------|-------|
| `name` | ✅ | Copy OCR-visible name; forbid generalizing to “lecithin” unless that is the only original word |
| `amount` | Conditional | Required if a dose row exists; **must not be filled by L3 if absent** |
| `unit` | Conditional | `mg` / `mcg` / `g` / `iu` |
| `source_image_index` | Recommended | 0-based |
| `source_line` | Recommended | For audit |

### 3.3 `layout_hints` enum

| Value | Meaning |
|-------|---------|
| `ecommerce_product_screenshot` | Cart/price/pagination dots |
| `supplement_front` | Front large-print main ingredient |
| `supplement_facts_panel` | Supplement Facts / nutrition table |
| `single_ingredient_product` | Legal single-ingredient (see §5.2) |

---

## 4. Multi-image Merge contract

### 4.1 Input/output

- **Input**: `PerceptionPageResult[]` (per-image OCR text + layout + row-level extract)  
- **Output**: single `LabelLedgerV1`

### 4.2 Rules (deterministic)

> **⚠️ Deprecated (Week 1 · 2026-05-26)**: the following “Facts first / image0·image1” drawing-board rules are replaced by  
> [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) **§5 layout weight matrix**.  
> Implementation: `pha/perception_merge.py` + `merge_parts_to_ledger`; upload order independent.

1. ~~**Facts first**~~ → `ingredient_rows` take max by `layout_hints` weight (`supplement_facts_panel` = 1.0 etc.).  
2. ~~**Front completeness**~~ → `brand` / `product_title` / `package_size` merge by field-weight matrix.  
3. **Dedupe key**: `normalize(name)|amount|unit`; on conflict keep the **higher-weight** page and record `ingredient_conflict`.  
4. **E-commerce noise**: `ecommerce_product_screenshot` rows **must not** alone generate lab-style `metrics`.  
5. **Merge audit**: `ledger_markdown` per-image blocks + `merge_trace[]` / `layout_hints_per_image[]`.

### 4.3 Relation to current modules

| Current | After 3B |
|---------|----------|
| `vision_label_ledger.merge_parsed_payloads` | Implementation converges to `LabelLedgerV1` generator |
| `enrich_parsed_payload` | Output must satisfy Schema |
| Chat send | **Prefer** `attachment_parsed_parts`; forbid double Vision when no OCR |

---

## 5. Confidence, refuse, and ask (rule-of-law rails)

> **Gemini note adopted**: do not one-cut on `ingredient_rows.length < 2`; must combine `layout_hints` and legal single-ingredient scenes.

### 5.1 `parse_confidence = low` triggers (any one)

| # | Condition | `reject_reasons` |
|---|-----------|------------------|
| R1 | User uploaded **≥2** images and **no** `supplement_facts_panel` and `ingredient_rows` empty | `missing_facts_panel` |
| R2 | `supplement_facts_panel` present but `ingredient_rows` empty | `facts_panel_unreadable` |
| R3 | `ocr_char_count` < `PHA_PERCEPTION_MIN_OCR_CHARS` (default 80) | `ocr_too_short` |
| R4 | OCR mean token confidence < `PHA_PERCEPTION_OCR_CONF_THRESHOLD` (default 0.75, when Tesseract available) | `ocr_low_confidence` |
| R5 | After multi-image merge expected ingredients ≥2, actual <2, and **not** `single_ingredient_product` | `incomplete_merge` |
| R6 | E-commerce screen + no dose row | `ecommerce_only_no_dose` |

### 5.2 Legal single-ingredient scene (do not false-hurt)

When **all** hold:

- `layout_hints` contains `single_ingredient_product` **or** (only 1 image + front has only 1 dose row + no Facts table), and  
- `ingredient_rows.length == 1` and that row has `amount`+`unit`  

→ `parse_confidence` **may be `high`**, **does not** trigger R5.

### 5.3 L0/L2/L3 behavior

| Confidence | C layer | TASK addendum | L3 |
|------------|---------|---------------|-----|
| `high` | Normal `attachment_asset_qa` | Standard TASK | Copy the ledger |
| `low` | Write `parse_confidence=low` to Telemetry | “Ledger incomplete; must mark uncertainty; **forbid writing concrete doses**” | Only describe visible/invisible; guide a Facts retake |

### 5.4 UI

- Status bar: `定账置信度偏低 · 已合并 N 张 · 建议补拍 Supplement Facts`  
- Optional: frontend “retake the back” hint (orthogonal to 3A.2.3 preview, P2)

---

## 6. L3 forbidden to invent doses (Gemini note · must-write TASK)

Dead command in `ATTACHMENT_ASSET_QA_TASK` / followup / lipid_bridge:

```text
若 LabelLedgerV1 / ATTACHMENT_LABEL 中某成分无 amount+unit：
  - 禁止用预训练常识填写剂量（例如不得写「建议每日 100mg」）；
  - 仅允许写「标签摘录中未见该成分剂量」或「请补拍 Facts 面」。
```

With Manifest Tier: **ledger row = T0 user-visible fact**; no row = no T0 number to cite.

---

## 7. Hardware Tier and Perception capability

See [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) §2.2.

| Tier | Perception default |
|------|-------------------|
| T1 | `perception_channel=ocr_only`; `PHA_PERCEPTION_VISION_VALIDATE=0` |
| T2 | Optional Vision validate |
| T3 | Concurrent OCR pages |

Env vars (draft):

| Variable | Default | Notes |
|----------|---------|-------|
| `PHA_HARDWARE_TIER` | `auto` | `1`/`2`/`3` override |
| `PHA_PERCEPTION_MIN_OCR_CHARS` | `80` | R3 |
| `PHA_PERCEPTION_OCR_CONF_THRESHOLD` | `0.75` | R4 |
| `PHA_PERCEPTION_VISION_VALIDATE` | `0` | T2+ |
| `PHA_ATTACHMENT_LABEL_TIER0_MAX` | `2400` | Tier0 slot cap |

---

## 8. Telemetry (merge with track 3)

Each turn `HarnessBuildReport.intent_route` extends:

| Field | Type | Notes |
|-------|------|-------|
| `attachment_path_count` | int | Request path count |
| `merge_count` | int | Merged image count |
| `ingredient_row_count` | int | Ledger row count |
| `parse_confidence` | string | high/low |
| `perception_channel` | string | ocr_only / … |
| `client_parse_reuse` | bool | Whether picker parse was reused |
| `reject_reasons` | string[] | §5.1 |
| `l0_qa_mode` | string | initial/followup/… |
| `l3_focus_violation` | bool | See [`telemetry-review-playbook.md`](telemetry-review-playbook.md) |

---

## 9. v1 Blocking golden (IMG_6800 + IMG_6801)

### 9.1 Ground-truth table (chief designer ruling)

| Item | Expected |
|------|----------|
| Brand | **NOW** (not ZENS / ZENESSE) |
| Front | Phosphatidyl Serine **100 mg**; 120 Veg Capsules; Cognitive Health |
| Back Facts | Choline **100 mg**; Phosphatidyl Serine **100 mg**; Inositol **50 mg** |
| `attachment_count` | 2 |
| `parse_confidence` | `high` (when OCR is normal) |

### 9.2 Assert script (v1.0 implementation)

- Path: `scripts/pha_perception_golden_6800_6801.py` (**code after sign-off**)  
- Input: fixed samples or synthetic OCR text (when CI has no images)  
- Asserts: Schema validate + ingredient-name fuzzy match + dose exact match  
- **Blocking**: must be green before CI / release

### 9.3 User-question golden (3A + 3B joint)

| Question | Expected structure |
|----------|-------------------|
| `这是什么？对我有什么帮助？` | ① what it is ② how it helps me (≤3 evidence inferences) ③ what to watch |
| `对我的血脂有什么影响？` | lipid_bridge; do not credit this turn’s new product |

---

## 10. Implementation order (after RFC v1.0 sign-off)

```text
B1  LabelLedgerV1 pydantic/jsonschema + validator
B2  perception_worker module (ocr → page → merge → ledger)
B3  chat path: reuse cache, ban double Vision, ATTACHMENT_LABEL inject
B4  Low-confidence branch + UI copy + TASK ban invent
B5  pha_perception_golden_6800_6801.py + CI
B6  runtime_capabilities + Tier Flag mapping
```

**Suggested build**: `pha-v2.3.3-stage3b-perception-worker-alpha`

---

## 11. Acceptance

- [ ] Golden script 10/10 green locally  
- [ ] 文辉 real device: two images one send, ledger contains 3 ingredients + NOW  
- [ ] DeepSeek / Qwen 1 round each: two-section structure required; lipid follow-up no hallucinated attribution  
- [ ] Telemetry exportable and `L0_L3_Alignment_Rate` computable  
- [ ] T1 default: no Vision main path, TTFT not worse by >30%  

---

## 12. Open questions (rule before v1.0)

1. **OCR language**: `eng` only or `eng+chi_sim`? (Chinese e-commerce screens)  
2. **Tesseract confidence**: page-level mean vs row-level min?  
3. **Golden image storage**: in-repo `tests/fixtures/images/` or CI secret path only?  

---

## Appendix A: Relation to 3A.2.2

3A.2.2 already delivered `vision_label_ledger`, multi-image API, `ATTACHMENT_LABEL` slot prototype. 3B **does not overturn**; it:

- **Promotes** parsed dict to a `LabelLedgerV1` contract;  
- Turns confidence/refuse **from advice into law**;  
- Turns golden **from “probably testable” into blocking CI**.

---

## Appendix B: Review sign-off

| Role | Sign | Date |
|------|------|------|
| 文辉 | ⏳ | |
| Grok | ⏳ | |
| Gemini | ⏳ | |
| Cursor | v1.0 implement α | 2026-05-26 |
| 文辉 | ✅ approved start | 2026-05-26 |

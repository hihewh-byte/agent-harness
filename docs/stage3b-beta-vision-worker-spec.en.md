# Stage 3B-β — Vision Perception Worker Spec

> **Language / 语言**：English (this document) · [中文](stage3b-beta-vision-worker-spec.md)

> **Version**: v0.3 (2026-05-27)  
> **Status**: 🔒 Spec locked · **Wave 3 perception-generalization rebuild** pending start (L0.2 layout crop + multi-engine arbitration + G6 degrade); Wave 1/2 partially coded  
> **Governing docs**: [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) · [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) §2.1 · §2.2  
> **Review**: 文辉 · Gemini joint review judge · Grok hardcoding-audit feedback (already absorbed)  
> **Depends**: 3B-α `LabelLedgerV1` contract, 3A attachment QA routing (do not recode)

---

## 0. Document purpose

On top of **3B-α** (OCR + deterministic merge + generalization gates), define the **3B-β Vision Worker**: close the **L0 capability gap** between local PHA and Gemini/Grok on the “two-image supplement label” scene with structured visual perception, while **strictly forbidding** any debug case (NOW / PS / Choline / Inositol) from entering production logic.

**Readers**: engineers and reviewers implementing the Perception Worker, Harness slots, Telemetry, and CI Fixtures.

---

## 0.1 EN/ZH terminology (Terminology · mandatory 1:1)

> **文辉 ruling (2026-05-27)**: all Specs, code comments, Telemetry fields, logs, and UI copy **must** use the English keys in the table below; Chinese is explanation only. **Forbidden** to mix two naming sets for the same concept (e.g. logs write `营养成分表`, code writes `supplement_facts`, with no mapping).

| English key (unique) | Chinese note | Forbidden mix |
|----------------------|--------------|---------------|
| `media_route` | Media route (L0.0) | Do not write “file-type routing” without the key |
| `document_family` | Business family (L0.5) | Do not mix-call `doc_kind` |
| `layout_region` | Layout region (L0.2 crop unit) | Do not use “nutrition-table region” as a generic name |
| `layout_hints` | Layout hints (for merge weights) | Do not write “layout tags” without the key |
| `perception_channel` | Perception channel | Do not write “recognition mode” |
| `parse_confidence` | Parse confidence | Do not write “ledger credibility” without the key |
| `reject_reasons` | Reject-reason code list | Do not ingest Chinese reject reasons |
| `ingredient_rows` | Ingredient rows (KV rows) | Semantics only when `document_family=supplement` |
| `dense_text_block` | Dense text block (region type) | **Generic**, not supplement-specific |
| `tabular_block` | Tabular text block (region type) | **Generic** |
| `vision_structured` | Vision structured channel | Do not write “VLM success” |
| `ocr_only` | OCR-only channel | Do not write “pure text recognition” |
| `merge_trace` | Merge trace | Do not omit |

**Region type (`layout_region.region_type`)** and **layout hints (`layout_hints`)** are two layers: the former is L0.2 physical crop; the latter is a structure tag on the L0.4 IR for the §5 weight matrix. Implementation and docs must mark the English key in both.

---

## 1. Anti-corruption constitution (Anti-Corruption · hard red lines)

The following three are **Spec highest-priority constraints**; violating them is architecture rollback and must not merge to production.

### 1.1 Gates and golden thoroughly isolated (P / F boundary)

| Layer | Code | Allowed | Forbidden |
|-------|------|---------|-----------|
| **Production Gate** | **P** | JSON Schema / Pydantic structure validate; abstract rules G1–G6 (§4); `parse_confidence` enum | Any concrete **brand name**, **ingredient name**, **mg value** as a sufficient condition for `high` |
| **Fixture / Benchmark** | **F** | Asserts on NOW, PS 100mg, etc. in `tests/fixtures/`, `scripts/pha_perception_golden_*.py` | Moving those asserts into `label_ledger_v1` runtime, `assess_confidence` production path, or TASK body |
| **Asset Knowledge** | **K** | Interactions, allergies, mechanisms in Metadata Catalog / asset JSON | `if ingredient == …` on `fixture-med` / `soy` / `槲皮素` etc. in mid-platform Python or Harness |

**Wording rules**:

- CI script titles use **“Fixture golden”**, must not write **“production blocking gate”**.  
- In architecture docs, `IMG_6800 + 6801` is a **Benchmark example** only, with a note “not a generalization-rule source”.

### 1.2 Merge permission is tagged, not drawing-boarded

- **Forbidden**: “image 0 = front, image 1 = Facts, Facts necessarily overrides front”.  
- **Must**: merge by each page’s `layout_hints` and the **field-weight matrix** (§5); upload order independent.  
- **Must**: emit `merge_trace[]` so each field is traceable to `(image_index, hint, weight)`.

### 1.3 Interaction rails are config, strictly no if-else firefighting

- Allergies, drug interactions, contraindications in “what to watch”: only **K-layer Lookup** (normalized ingredient name → asset config).  
- C-layer code shape: `warnings = catalog.lookup_interactions(normalized_rows, user_profile)`.  
- L3 only polishes lookup results; when lookup is empty **must not** invent interactions.

### 1.4 Ignorant routing and post-hoc classification (Asset-Agnostic · constitution-level)

> **Review**: 文辉 · Gemini architecture re-check (2026-05-26) — forbid a god’s-eye “already know it is supplement/lab/medication before upload”.

| Principle | Notes |
|-----------|-------|
| **L0 entry has zero business semantics** | Worker entry **must not** choose a toolchain by `supplement_label` / `lab_report` / drug name. |
| **Media first, family second, Schema last** | `media_route` (§7.0) → L0.2 crop → perception IR → `document_family` (§7.8) → Schema ledger. |
| **Structure marks, not brands** | Business family only allows layout/regulatory fields (`Supplement Facts`, `参考范围`, `国药准字`, etc.); **forbid** NOW/ingredient-name allowlists. |
| **Same-family multi-image merge** | Cross-family attachments (lab image + pill-box image) → `merge_family_conflict`; hard merge forbidden. |

**Anti-pattern (forbidden in Spec or production)**:

```text
# ❌ inverted causality / hidden hardcoding
if asset_type == "supplement_label":
    use_florence()
elif asset_type == "lab_report":
    use_marker()
```

**Current-prod gap (3B-β debt, not this Spec’s target state)**:

- `classify_document_from_ocr` produces `doc_kind` **after first-round Tesseract, before full IR**, and affects VLM degrade branch and `parsed_payload_from_extraction` selection.  
- Already repealed: `len(ocr) >= 25` skip Vision; **not repealed**: `doc_kind` pre-binding the parser (see §7.10 migration).  

---

## 2. Strategic position: align Gemini/Grok, keep PHA layering

### 2.1 Cloud strong-model data chain (summary)

```text
pixels (multi-image) → Vision structured → ledger facts → (optional) knowledge match → NL
```

### 2.2 PHA target data chain (after 3B-β)

```text
pixels (multi-image)
    → [3B-β Vision Worker | 3B-α OCR degrade]
    → LabelLedgerV1 (JSON) + merge_trace
    → [P-layer gate] high | low
    → high: L0 routing + ATTACHMENT_LABEL + L3 narrative
    → low:  refuse template (do not call L3 to complete the ledger)
```

**L3 (7B/14B) forbidden**: OCR, multi-image merge, ingredient-table completion, dose invention.

---

## 3. Sub-phase relations (no skipping)

| Phase | Perception means | LLM role | Admission |
|-------|------------------|----------|-----------|
| **3B-α** | OCR → layout classify → regex/heuristic row extract → weight merge | None (optional T2 Vision **validate**, Flag) | Current baseline; P-layer gates G1–G6 |
| **3B-β** | Dedicated VLM / cloud Vision **Worker only** → JSON Mode | Structured inside Worker; **does not** enter Harness main chat | 3B-α P-layer stable + Fixture green + Telemetry 2 weeks |
| **3B-γ** (later) | Multi asset types (TCM, liquids, barcodes) | Choose Worker by asset profile | Multi-layout Benchmark set |

This Spec **only defines 3B-β**; 3B-α R1–R6 are governed by [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) §5, and gradually converge with §4 G rules.

---

## 4. Production gates (P layer · generalization rules G1–G6)

> **Relation to RFC R1–R6**: G rules are **product-agnostic** upper statements; implementation may map R to G, but **must not** add product-ward `reject_reasons` such as “missing Choline/Inositol”.

### 4.1 `parse_confidence = low` (any one → low)

| ID | Condition (abstract) | Suggested `reject_reasons` |
|----|----------------------|----------------------------|
| **G1** | Attachment QA needs ingredient ledger, and `ingredient_rows` empty | `no_ingredient_rows` |
| **G2** | `ingredient_rows` non-empty, but **no row** simultaneously has parseable `name` + (`amount`+`unit` or legal amount string) | `no_parseable_dose` |
| **G3** | Request path count `N` ≥ 2, and after merge `attachment_count` < `N` or `parts` missing | `merge_incomplete` |
| **G4** | `perception_channel == ocr_only` and `ocr_char_count` < `PHA_PERCEPTION_MIN_OCR_CHARS` and **no page** has an authoritative-ingredient layout hint (§5.1 table) | `ocr_too_short` |
| **G5** | Row names have **structure pollution** (pure dose as name, name length < 2, name matches OCR-fragment rules, **do not write a concrete chemical allowlist**) | `polluted_ingredient_rows` |
| **G6** | Multi-image input, and **no page** `layout_hints` hits a **high-weight text/tabular block** (`tabular_block` corresponding hint in §5.1), **and** G1 or G2 also fires | `missing_authoritative_panel` |

> **2026-05-27 revision (generalization gate)**: `missing_authoritative_panel` **alone must not** drop `parse_confidence` to `low`. Missing a standard “box/header” only writes `warnings[]` (Telemetry: `layout_panel_hint_missing`); the **fact layer** is judged by parseable K-V rows (G2 negation). Forbid killing long-tail packs for layout formalism.

### 4.1.1 `warnings[]` (non-blocking · separate from `reject_reasons`)

| Code | Meaning | Alone causes `low`? |
|------|---------|---------------------|
| `layout_panel_hint_missing` | No tabular / dense_text class hint, but parseable rows already exist | **No** |
| `vision_json_unstable` | VLM JSON failed, already fused OCR/transcript | **No** (if G2 satisfied) |
| `local_vlm_resolution_limited` | On-device VLM pixel/row-align capability insufficient (Telemetry record) | **No** |

### 4.2 `parse_confidence = high` (necessary, not sufficient)

All of:

1. G1–G6 none fire;  
2. `ingredient_rows.length >= 1` and at least one parseable dose (G2 negation);  
3. At least one of `brand` or `product_title` non-empty (OCR noise allowed; **do not** validate equals a brand).

### 4.3 Legal single-ingredient scene (do not false-hurt)

When **all** hold:

- `layout_hints` contains `single_ingredient_product`, **or**  
- Only 1 image + only 1 parseable dose row + no standard Facts box (long-tail pack), and  
- `ingredient_rows.length == 1` and that row satisfies G2;

→ **may be `high`**, does not trigger G6.

### 4.4 System behavior at low confidence (L0/L2/L3)

| Confidence | C layer | L3 |
|------------|---------|-----|
| `high` | Inject full `ATTACHMENT_LABEL`; standard `ATTACHMENT_ASSET_QA_TASK` | Copy the ledger; “help” section may cite archive |
| `low` | Telemetry writes `reject_reasons`; optional short **refuse template** (§8) | **Forbid** calling the main model to complete ingredient table or dose; forbid affirmative “this product contains XX mg” |

---

## 5. Multi-image Merge: layout weight matrix

### 5.1 `layout_hints` enum (extensible)

| Value | Meaning |
|-------|---------|
| `supplement_facts_panel` | Dietary-supplement Facts box (**hint**, not L0.2 region-type name) |
| `nutrition_facts_table` | Nutrition-table layout (**hint**) |
| `tabular_block` | Tabular dense block (aligns with L0.2 `region_type`) |
| `dense_text_block` | Dense plain-text block (aligns with L0.2 `region_type`) |
| `ingredient_list_text` | No box, plain-text ingredient list (TCM, compound instructions, etc.) |
| `supplement_front` | Front marketing, large-print main ingredient |
| `product_marketing` | Efficacy claims, product name |
| `ecommerce_product_screenshot` | Cart, price, platform UI |
| `traditional_text` | Traditional pack, flat instructions |
| `single_panel_label` | Single-face full info |
| `single_ingredient_product` | Legal single-ingredient product |
| `unknown` | Unclassified |

**Detection**: 3B-β from Vision Worker output; 3B-α from OCR heuristics + Worker validate. Must not hardcode “2nd image = Facts”.

### 5.2 Field-weight matrix (deterministic)

For each page `p`, each field `f`, take weight `w_p(f)`; at merge pick **max weight** as primary source; same weight → semantic dedupe; conflict → `low` + `ingredient_conflict`.

| layout_hint (any on page) | brand / title / package | ingredient_rows | allergens / claims |
|---------------------------|-------------------------|-----------------|---------------------|
| `supplement_facts_panel`, `nutrition_facts_table`, `tabular_block` | 0.3 | **1.0** | 0.8 |
| `dense_text_block`, `ingredient_list_text`, `traditional_text` | 0.5 | **0.95** | 0.6 |
| `single_panel_label` | 0.7 | **0.85** | 0.5 |
| `supplement_front`, `product_marketing` | **0.8** | 0.2 | 0.3 |
| `ecommerce_product_screenshot` | 0.4 | 0.1 | 0.1 |
| `unknown` | 0.5 | 0.5 | 0.3 |

**E-commerce noise**: `ecommerce_product_screenshot` alone **must not** generate lab-style `metrics` or act as the sole ingredient source (same as RFC §4.2).

### 5.3 `merge_trace` (audit)

Each field merge result carries:

```json
{
  "field": "ingredient_rows",
  "source_image_index": 1,
  "layout_hints": ["supplement_facts_panel"],
  "weight": 1.0,
  "rule": "max_weight"
}
```

Telemetry and debug logs **must** be able to emit `merge_trace` (see §10).

---

## 6. `LabelLedgerV1` extended Schema (production)

Extend [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) §3 (**backward compatible**):

```json
{
  "schema_version": "label_ledger_v1",
  "attachment_count": 2,
  "brand": "",
  "product_title": "",
  "package_size": "",
  "serving_size": "",
  "ingredient_rows": [
    {
      "name": "",
      "amount": "",
      "unit": "",
      "source_image_index": 0,
      "source_line": ""
    }
  ],
  "allergens": [],
  "claims": [],
  "layout_hints": [],
  "layout_hints_per_image": [
    { "index": 0, "hints": ["supplement_front", "ecommerce_product_screenshot"] }
  ],
  "parse_confidence": "high",
  "reject_reasons": [],
  "perception_channel": "ocr_only",
  "ocr_char_count": 0,
  "merge_trace": [],
  "ledger_markdown": ""
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `serving_size` | Recommended | Per serving/capsule, e.g. `1 Veg Capsule` |
| `layout_hints_per_image` | Recommended for multi-image | Per-page layout, for merge and Telemetry |
| `merge_trace` | Recommended for multi-image | §5.3 |
| `claims` | Optional | Marketing claims (**not** ingredient-dose authority) |
| `perception_channel` | ✅ | `ocr_only` \| `vision_structured` \| `ocr_plus_vision_validate` |

**Production validator** only checks: types, required enums, G1–G6 logic. **Does not** validate concrete brand or ingredient strings.

---

## 7. 3B-β Vision Worker interface

### 7.0 L0.0 media route (Media Route · ignorant entry)

On attachment upload, split tracks **only** by physical features; **do not** guess supplement/lab/medication.

| `media_route` | Predicate (example) | Pipeline |
|---------------|---------------------|----------|
| `pdf_native` | PDF with extractable text layer / vector tables | PDF text extract → optional table structured (§7.7 ADP-PDF-*) |
| `pdf_scan` | PDF with no reliable text layer (scan) | Rasterize → **same OCR+Layout chain as raster** |
| `raster_photo` | `image/jpeg` · `image/png` · phone photo/screenshot | **Forbid** Marker as first entry; OCR + Layout + optional VLM |
| `unknown` | Other MIME | Try raster; fail → `parse_confidence=low` |

**Telemetry (required)**: `media_route`, `page_count`, `has_native_text_layer` (PDF).

```text
[Unknown attachment bytes]
        │
        ▼
   L0.0 media_route (MIME + PDF probe)
        │
   ┌────┴────┐
   ▼         ▼
 pdf_*    raster_photo
   │         │
   └────┬────┘
        ▼
   L0.2 layout_region crop (§7.2 · all image types · required)
        ▼
   L0.4 perception IR (§7.7 adapter chain · parallel on crops)
        ▼
   L0.5 document_family (§7.8)
        ▼
   L0.6 Schema ledger + P gates G*
```

### 7.2 L0.2 layout-region crop (Layout Region Crop · all-media generalization)

> **文辉 ruling (2026-05-27)**: L0.2 **must not** bind a business-image class (supplement/lab/medication). All `raster_photo` and `pdf_scan` raster pages **must** produce `layout_regions[]` before the VLM/OCR main path; `pdf_native` with embedded image blocks may optionally get the same treatment.

**Purpose**: reduce Logo, background, UI noise diluting downstream Encoder attention; raise effective resolution of small-type K-V rows inside the pixel budget. **Do not** choose crop targets by brand name, ingredient name, or business words such as “nutrition table”.

#### 7.2.1 `layout_region` structure (unified IR)

```json
{
  "region_id": "r0",
  "region_type": "dense_text_block",
  "bbox_norm": [0.12, 0.34, 0.88, 0.91],
  "source_page_index": 0,
  "crop_bytes_ref": "…",
  "detector": "ADP-LAYOUT-01",
  "confidence": 0.82
}
```

| `region_type` (English key · generic) | Chinese note | Typical downstream |
|---------------------------------------|--------------|--------------------|
| `dense_text_block` | Dense text block | Full OCR + optional VLM JSON |
| `tabular_block` | Tabular aligned block | Row cluster + TABLE substep |
| `header_block` | Header/title zone | brand / title candidates |
| `figure_block` | Figure/Logo/decoration | Low weight, **not** a primary ingredient source |
| `barcode_block` | Barcode/QR zone | Metadata, not primary ledger source |
| `full_page` | Whole-image floor when detect fails | Last hop of the degrade chain |

#### 7.2.2 Detector (implementation swappable · Spec only constrains interface)

| Implementation candidate | Role | Notes |
|--------------------------|------|-------|
| **ADP-LAYOUT-01** (e.g. Florence-2 `OCR_WITH_REGION`) | Region boxes + coarse classify | **Must not** hardcode “only detect nutrition tables”; output must map to the `region_type` table above |
| Heuristic split | Degrade when no model | Whole-page `full_page` + warning `layout_detector_degraded` |

**Forbidden**: `if document_family == supplement: crop_facts_panel` or equivalent business-front crop.

#### 7.2.3 Downstream consume rules

1. **OCR / VLM default input**: run ADP-OCR / ADP-VLM **separately** on `dense_text_block` + `tabular_block` crops, then merge back to page-level IR.  
2. **`figure_block` / `barcode_block`**: do not enter the ingredient/lab-number ledger main path.  
3. **Multi-crop conflict**: arbitrated by §5 weight matrix + `merge_trace`; **forbid** hard override by upload order.

**Telemetry (required)**: `layout_region_count`, `layout_detector`, `regions[].region_type`.

### 7.3 Input

```json
{
  "task": "perception_v1",
  "attachments": [
    { "path": "…", "filename": "…", "mime": "image/jpeg" }
  ],
  "user_locale": "zh-CN",
  "hardware_tier": "auto"
}
```

> `task` at entry **does not** contain a business family; `document_family` is written into output by §7.8 after perception.

### 7.4 Output

- **Success**: §6 JSON (`perception_channel` see §7.6 lane arbitration).  
- **Fail/timeout**: degrade chain (§7.6); must not be filled by L3.

### 7.5 Prompt / decode constraints (principles)

- **Single task**: JSON only, Schema-conformant; forbid Markdown prose.  
- **Per-image instruction**: list `layout_hints` and `ingredient_rows` per image; Worker must not do “how does this help me”.  
- **Dose**: only copy what is visible on the label; if invisible, omit the row or leave amount empty (triggers G2).  
- **Compound names**: keep label original (Phosphatidyl Serine); forbid simplifying to Serine.

### 7.6 Multi-engine perception matrix and degrade chain (Multi-Engine · generalization)

> **Principle**: local on-device VLM (e.g. `llama3.2-vision:11b`) is only **one lane**; real-device red-light root causes include **Encoder resolution/attention physical limits** and **full-frame noise**, not a single-case Prompt problem.

| Lane ID | English key | Input | Tool class | Applies |
|---------|-------------|-------|------------|---------|
| **Lane-L** | `layout_crop` | Original image | ADP-LAYOUT-01 | All `raster_photo` / `pdf_scan` pages |
| **Lane-O** | `ocr_cluster` | L0.2 crops | Tesseract / PaddleOCR / Apple Vision | same |
| **Lane-V** | `vision_structured` | L0.2 crops | Local VLM JSON | T2+ |
| **Lane-C** | `cloud_vision_byok` | L0.2 crops | User-configured API (e.g. gpt-4o-mini) | Local joint confidence continuously below threshold and Key configured |

**Arbitration (C layer · deterministic)**:

1. Row-level K-V: any lane that produces a parseable row is a candidate; conflict prefers **OCR row anchors + crop bbox**, VLM NL second.  
2. `perception_channel` takes the **highest-capability lane** that participated in the ledger (`cloud_vision_byok` > `vision_structured` > `ocr_cluster`).  
3. Forbid raising a lane’s weight to pass a Fixture.

```text
L0.2 layout_region crop (Lane-L)
    → parallel Lane-O + Lane-V (+ optional Lane-C)
    → L0.4 IR merge
    → L0.5 document_family
    → L0.6 ledger + P gates G*
    → still G1/G2/G3… → parse_confidence=low
    → warnings only (e.g. layout_panel_hint_missing) → may be high
```

**VRAM strategy** (§2.2 hardware Tier):

| Tier | Default channel |
|------|-----------------|
| T1 | `ocr_only` only |
| T2 | `vision_structured` optional; `PHA_PERCEPTION_VISION_VALIDATE=1` |
| T3 | Multi-page concurrent OCR + Vision validate |

Env vars reuse RFC §7; new (draft):

| Variable | Default | Notes |
|----------|---------|-------|
| `PHA_PERCEPTION_VISION_MODEL` | — | Worker-dedicated VLM name (separate from chat model) |
| `PHA_PERCEPTION_VISION_TIMEOUT_S` | `45` | Worker timeout |
| `PHA_PERCEPTION_FORCE_SERVER_PARSE` | `1` | Multi-image force server re-perception on chat send |

### 7.7 L0.4 perception adapter chain (by media · not by business family)

> **Status**: 📋 design (not started) · real-device accept see [`stage3b-e2e-real-label-fixture.md`](stage3b-e2e-real-label-fixture.md)

Adapters hang **only** after `media_route`; **must not** use `document_family` as an entry condition.

| ID | Tool | Applies `media_route` | Phase | Output (into unified IR) |
|----|------|----------------------|-------|--------------------------|
| **ADP-PDF-01** | pdfium / PyMuPDF text layer | `pdf_native` | Extract | `pages[].lines[]` |
| **ADP-PDF-02** | Marker / Unstructured | `pdf_native` · `pdf_scan` | Tables | `pages[].tables[]` |
| **ADP-OCR-01** | Apple Vision / PaddleOCR | `raster_photo` · `pdf_scan` | Full OCR | `lines[]` + conf |
| **ADP-LAYOUT-01** | Florence-2 `OCR_WITH_REGION` (swappable) | `raster_photo` · `pdf_scan` | L0.2 crop | `layout_regions[]` (`region_type` see §7.2.1) |
| **ADP-TABLE-01** | Row-align / Marker **substep** | `raster_photo` (crop nearly flat) | Table → rows | `tables[]` → row parse |
| **ADP-VLM-01** | Qwen2-VL / llama3.2-vision | `raster_photo` · optional `pdf_scan` | Validate/complete | JSON (**family chooses Schema in §7.8**) |
| **ADP-CLOUD-01** | Gemini Flash Vision | Authorized scenes | same | same |

**Principles**:

- **JPEG/PNG real photos**: first entry is **not** Marker; **must** ADP-LAYOUT-01 → ADP-OCR (+ optional ADP-VLM) on **crops**, not naked full-frame.  
- **PDF**: probe text layer first; `pdf_native` prefers ADP-PDF-01; scanned PDF takes the raster-equivalent chain (incl. L0.2).  
- **ADP-TABLE-01** is called on `tabular_block` crops; it is **generic table-row align**, not a business-family special.  
- Each adapter: timeout, fail signal, next hop, `perception_channel` → Telemetry.  

**Spike order (by media)**: S0 PDF text-layer probe → S1 raster multi-OCR compare → S2 **L0.2 generic region crop** → S3 VLM JSON legal rate on crops → S4 `tabular_block` row cluster.

Details: [`stage3c-vision-capability-matrix.md`](stage3c-vision-capability-matrix.md) §4–§5.

### 7.8 L0.5 post-perception business-family classify (Post-Perception · `document_family`)

After **L0.4 IR** (`lines` + `regions` + `tables`) is ready, C layer assigns business semantics for the **first** time.

| `document_family` | Structure triggers (examples, configurable) | Bound Schema (L0.6) |
|-------------------|---------------------------------------------|---------------------|
| `supplement` | `Supplement Facts` · nutrition table · serving + mg dose rows | `LabelLedgerV1` |
| `lab` | Reference ranges · test items · mmol/μmol · hospital letterhead | Lab metrics ingest |
| `medication` | `国药准字` · approval number · indications · Drug Facts (§7.9) | `MedicationLedgerV1` (3B-γ) |
| `wearable` | HRV · Apple Watch · RHR panel | wearable ingest |
| `unknown` | Insufficient triggers | **low refuse**; forbid defaulting to supplement |

**Output fields**:

- `document_family` · `family_confidence` · `family_evidence_spans[]` (hit-fragment offsets, for audit)  

**Rules**:

- The classifier **must not** skip any required §7.7 adapter (e.g. must not skip L0.2 Layout because it guessed the family).  
- Relation to current-prod `classify_document_from_ocr`: **v0 may reuse its scoring function**, but semantics migrate to this table; **forbid** using its return value to choose “whether to call VLM” (3B-β debt).  
- Multi-image: inconsistent `document_family` → `merge_family_conflict` (P-layer low).

### 7.9 Medication extension port (3B-γ · Spec reserved)

| Item | Notes |
|------|-------|
| **Goal** | OTC/Rx labels and inserts, **≠** dietary-supplement ledger |
| **Trigger** | `国药准字`, `批准文号`, `适应症`, `禁忌`, `Drug Facts` (config table, not product names) |
| **Schema** | `MedicationLedgerV1`: generic name, strength, lot (if any), warning fragments |
| **K layer** | Drug interaction / contraindication Lookup (separate table from supplement catalog) |
| **P layer** | **Forbid** applying “missing some supplement ingredient” class G rules to the medication family |
| **Fixture** | Separate F-layer benchmark; **does not** enter NOW/PS golden |

### 7.10 Current-prod → target-state migration list (3B-β coding)

| Current-prod behavior | Target state |
|-----------------------|--------------|
| `doc_kind` after OCR chooses VLM prompt / parse branch | `media_route` chooses the chain; `document_family` only chooses Schema |
| No VLM → `supplement_label` OCR-only only | Choose degrade template by `document_family`; unknown → refuse |
| Worker `task: supplement_label_v1` | Entry `perception_v1`; family written post-hoc |
| §7.7 old table “asset type” column | Repealed; see §7.7 media column |

**New Telemetry**: `media_route`, `document_family`, `family_confidence`, `merge_family_conflict`.

---

## 8. Active Recall (L2.5 · cross-ref)

7B **attention decay** in multi-turn focus sessions causing “forgot round-1 ledger” is **not** in L0 perception Spec scope.

- **Separate RFC**: [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.md)  
- **Principle**: `ActiveRecallLedger` written by C layer from `ATTACHMENT_LABEL` / Patient State slices; **Bottom-Anchor** slot `RECALL_FOCUS` adjacent to the user question; small model (1.5B) may optionally output `recall_plan`, **forbid** generating assertion body.  
- **Depends**: `anchored_asset` assertions only after L0.6 ledger `high`.

---

## 9. Refuse template (low confidence · generalized copy)

**Forbidden** to write “please upload NOW” or “need Choline/Inositol” in the template.

Recommended structure (C-layer assembled):

1. **Stance**: could not get a reliable ledger from the label; will not guess ingredients or doses.  
2. **Reason-code translation** (from `reject_reasons`, mapping table configured): e.g. `merge_incomplete` → “not all images were merged”.  
3. **User action**: retake a clear ingredient table / wait for “merged N images” / reduce e-commerce UI in frame.  
4. **Optional fragment**: list low-confidence OCR rows (marked “for check, not a complete ledger”).  
5. **Intent protection**: if the user asks “how does this help me”, state clearly **answer after the ledger is reliable**.

---

## 10. L3 duty narrowing (plan C′ · merge with 3A)

| Output block | Producer | Rules |
|--------------|----------|-------|
| **What is this supplement** | **C-layer template** | Render `ingredient_rows` + brand/title/package/serving; L3 may not add/delete rows |
| **How does this help me** | **L3** | Cite only: ledger + `SUPPLEMENT_BG` + K-layer `benefit_claims` lookup |
| **What to watch** | **K-layer Lookup + L3 polish** | `catalog.lookup_interactions(normalized_rows, profile)` |

**TASK constitution** (continue RFC §6): ledger has no amount/unit → forbid common-sense filling mg; consistent with Manifest Tier.

---

## 11. Telemetry (align track 3)

Extend RFC §8:

| Field | Type | Notes |
|-------|------|-------|
| `merge_trace` | object[] | §5.3 |
| `layout_hints_per_image` | object[] | Per-image layout |
| `perception_worker` | string | `alpha` \| `beta` |
| `vision_model` | string | Worker model name (if applicable) |
| `gate_triggered` | string[] | G1–G6 hit list |
| `deterministic_reply` | bool | Whether L3 was skipped |
| `l0_l3_alignment_ok` | bool | Whether the answer contains off-ledger doses (KGI) |

Retro: [`telemetry-review-playbook.md`](telemetry-review-playbook.md) · `L0_L3_Alignment_Rate`.

---

## 12. Acceptance system (P / F separated)

### 11.1 Production accept (P · any brand)

- [ ] Schema validate passes;  
- [ ] `high` has ≥1 parseable-dose row; multi-image has `merge_trace`;  
- [ ] `low` attachment QA has **no** affirmative concrete-dose statement (Telemetry audit);  
- [ ] Codebase has **zero** production-path string match of `NOW` / `Choline` / `Inositol` as a gate (static scan + review).

### 11.2 Fixture accept (F · CI only)

**Example**: `tests/fixtures/supplement/now_ps_6800_6801/` (OCR de-identified or synthetic images)

| Assert | Notes |
|--------|-------|
| `brand` contains `NOW` | **This fixture only** |
| `ingredient_rows` cover PS / Choline / Inositol with parseable doses | **This fixture only** |
| `layout_hints_per_image[1]` contains `supplement_facts_panel` | **This fixture only** |

Scripts: `scripts/pha_perception_golden_6800_6801.py` (synthetic OCR golden) + future real-device fixture directory.

### 11.3 Generalization Benchmark set (P1 · non-blocking)

| Layout class | Image count | P-layer assert |
|--------------|-------------|----------------|
| US two-face bottle | 2 | high rate, merge_trace contains facts weight 1.0 |
| Single-face full ingredients | 1 | ≥1 dose row |
| Chinese flat | 1–2 | `ingredient_list_text` weight takes effect |
| E-commerce screenshot | 1 | Should not high alone (G5/G6) |
| Single ingredient | 1 | `single_ingredient_product` may be high |

---

## 13. Mapping to current-prod modules

| Current prod | After 3B-β |
|--------------|------------|
| `perception_worker.finalize_attachment_parse` | Call β Worker or α degrade |
| `vision_label_ledger.merge_parsed_payloads` | Converge to §5 weight merge |
| `assess_confidence` | Implement G1–G6 only; remove product-ward `missing_choline_row` etc. |
| `attachment_asset_qa` | Low-confidence `maybe_deterministic_attachment_reply` (generalized copy) |
| `harness_plan` · `ATTACHMENT_LABEL` | Inject `ledger_markdown` / JSON summary |
| Metadata Catalog | K-layer interaction lookup |

---

## 14. Suggested implementation order

```text
Week 0  ✅ this Spec + anti-corruption review
Week 1  P layer: G1–G6 converge, merge weights, merge_trace Telemetry; strip production hardcoding
Week 2  Two-image contract: send gate, server-forced re-perception (product layer, see 3A.2.3)
Week 3  Wave 3: L0.2 layout_region + multi-engine arbitration (§7.6) + G6 warning split
Week 4  3B-β Worker: VLM JSON on crops, Lane-C BYOK optional, T2 pilot
Week 5  Fixture set expand + Telemetry 2-week retro → whether full T2
```

**Out of this Spec**: LangChain replacing Harness, extracting pha-core, HRV by time-of-day (separate RFC).

---

## 15. Real-device audit and Wave 3 Backlog (2026-05-27 · generalization · not a case)

> **Highest instruction**: forbid production hardcoding for NOW / specific ingredients; Fixture red light means **L0 base capability** is insufficient.

### 15.1 Root causes (family-agnostic)

| ID | Root cause (English key) | Notes |
|----|--------------------------|-------|
| **RC-1** | `local_vlm_resolution_limited` | On-device VLM Encoder physically loses small-type K-V rows; Prompt-tuning is ineffective |
| **RC-2** | `full_frame_noise` | Full image fed straight to VLM/OCR, no L0.2 `layout_region` crop |
| **RC-3** | `gate_formalism_over_block` | `missing_authoritative_panel` blocks alone, detached from fact-layer G2 |
| **RC-4** | `single_engine_dependency` | Only Tesseract + one VLM; no Lane-O multi-OCR / Lane-C floor |

### 15.2 Wave 3 coding Backlog (pending 文辉 confirm start)

| Item | Deliverable | Gate |
|------|-------------|------|
| **W3-1** | `layout_regions[]` IR + ADP-LAYOUT-01 wired | All `raster_photo` Telemetry contains `layout_region_count` |
| **W3-2** | Parallel Lane-O + Lane-V on crops + deterministic arbitration | Synthetic + real device: parseable-row count ≥ baseline, **no** brand hardcoding |
| **W3-3** | `warnings[]` decoupled from G6 | `layout_panel_hint_missing` does not alone cause `low` |
| **W3-4** | Lane-C `cloud_vision_byok` adapter (optional) | No outbound call without Key |
| **W3-5** | PaddleOCR / Apple Vision as Lane-O plugins | Spike report: small-type K-V recall |

**Real-device Benchmark (F layer)**: 6800/6801 are regression samples only; pass standard is **abstract G rules + multi-engine Telemetry**, not “must read NOW”.

---

## 16. Revision history

| Date | Version | Notes |
|------|---------|-------|
| 2026-05-26 | v0.1 | First draft: absorb Gemini/Grok audit; P/F/K layers; weight merge; β Worker interface |
| 2026-05-26 | v0.2 | §1.4 ignorant routing; §7.0–7.8 media split + post-hoc `document_family` + Medication reserved; repeal business-front split table |
| 2026-05-26 | v0.2.1 | §8 cross-ref [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.md) (L2.5 multi-turn memory) |
| 2026-05-27 | v0.3 | §0.1 EN/ZH terminology; §7.2 L0.2 all-type `layout_region`; §7.6 multi-engine lanes; §4 G6/`warnings` decouple; §15 real-device audit Backlog |

---

## Appendix A · Fixture example (F layer · not a production rule)

**Benchmark name**: `now_ps_6800_6801`  
**Input**: front e-commerce screenshot + back Supplement Facts (user real-device images de-identified then stored as fixture)  
**Expected (CI only)**:

- `brand` → contains `NOW`  
- `product_title` → contains `Phosphatidyl Serine`  
- `ingredient_rows` → contains `(Choline*, 100, mg)`, `(Phosphatidyl Serine, 100, mg)`, `(Inositol, 50, mg)` (name may contain `(from Choline Bitartrate)` substring)  
- `package_size` → contains `120` + `Caps`  
- `allergens` → contains `soy` (P1 optional assert)

**Counter-example fixture (suggest add)**: `cgn_berberine_single_ingredient` — only 1 dose row, must be `high`, and **must not** refuse for missing Choline.

---

## Appendix B · `reject_reasons` enum (production)

| Value | Corresponds G |
|-------|---------------|
| `no_ingredient_rows` | G1 |
| `no_parseable_dose` | G2 |
| `merge_incomplete` | G3 |
| `ocr_too_short` | G4 |
| `polluted_ingredient_rows` | G5 |
| `missing_authoritative_panel` | G6 (must conjoin G1/G2, see §4.1) |
| `layout_panel_hint_missing` | warnings only (§4.1.1) |
| `ingredient_conflict` | merge conflict |
| `merge_family_conflict` | Multi-image business family inconsistent |
| `facts_panel_unreadable` | Has facts hint but G2 failed (finer, optional) |

**Deprecated (must not add to production)**: `missing_choline_row`, `missing_inositol_row`, and other reasons pointing at a **specific ingredient**.

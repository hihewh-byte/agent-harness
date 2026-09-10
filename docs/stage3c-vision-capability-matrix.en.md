# PHA vision capability matrix and tool selection

> **Language / 语言**：English (this document) · [中文](stage3c-vision-capability-matrix.md)

> **Version**: v0.3 (2026-05-27)  
> **Readers**: architecture decisions, 3B-β selection  
> **Related**: [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) §0.1 · §7.2 · §7.6

---

## 1. Direct answer: is PHA “weak at reading images”?

**Yes, but split it into two layers. Do not mix them.**

| Layer | Insufficient? | Notes |
|------|----------|------|
| **A. Product pipeline choice** | ✅ **was the main cause** | Supplement OCR≥25 short-circuit **retired** (2026-05-26); **`doc_kind` still pre-binds parse branches** (see §3.1) |
| **B. The tool itself** | ✅ **Tesseract is insufficient for ecommerce screenshots + small-type Facts** | Live logs: front 175-char fragments, back no ingredient rows; not “7B can’t see” |
| **C. Main chat LLM** | ❌ not a vision model | Qwen 7B is **text reasoning**; reading pixels was never its job |

**Conclusion**: it is not that “PHA as a product has no vision”. The **current production path demotes supplement labels to OCR-only**, and the OCR toolchain mismatches the scene. Gemini/Grok win by **defaulting to multimodal Vision**, not by “a larger chat model”.

---

## 2. What “tools” do Grok / Gemini use?

Both emphasize a **reproducible toolchain** in public descriptions; the essence is **cloud multimodal models + file read**, not Tesseract regex.

| Product | Self-described path | Actual capability |
|------|----------|----------|
| **Gemini** | pixels → Vision Embedding → structure → knowledge → text | **Native multimodal** (Gemini 2.x Pro/Flash etc.); whole-image layout, tables, trademarks |
| **Grok** | `read_file` / attachment path → HD visual description + OCR-grade extract | **Host multimodal** + tools reading local/attachment bytes; not local Tesseract |

**Shared**:

- **Do not** treat “25 OCR characters exist” as a reason to skip Vision
- **Do not** “stitch” Supplement Facts from broken text with a single-line regex
- Structure happens in the **perception stage**; the chat model only consumes structured results

**PHA prod contrast (historical)**:

```text
(fixed) supplement image → Tesseract → if chars≥25 → skip Vision  ← retired
(target) media-route → perception IR → document_family → Schema ledger
```

---

## 3. PHA prod tool stack (fact table)

| Component | Tech | Use | Supplement-label status |
|------|------|------|----------------|
| OCR | **Tesseract 5** (`pytesseract`) | 0 VRAM, local | **primary path** |
| Vision | **Ollama** `llama3.2-vision:11b` / `llava` / env `PHA_VISION_MODEL` | lab PDF/screenshot JSON extract | **often skipped for supplements** |
| Row extract | regex `vision_label_ledger` | pull mg rows from OCR text | fragile (Serine split, no back rows) |
| Chat | Qwen2.5 7B etc. | text Harness | does not read pixels |

### 3.1 Architecture target vs prod gap

| Dimension | Prod (2026-05-27) | Target (3B-β Spec v0.3) |
|------|-------------------|-------------------------|
| Entry routing | first OCR then `classify_document_from_ocr` → `doc_kind` | **L0.0** `media_route` (PDF / raster) |
| Layout slice | whole image to VLM/OCR | **L0.2** `layout_region` (`dense_text_block` / `tabular_block` etc., **all image types**) |
| Tool choice | `doc_kind` affects VLM degrade and parser | **only** `media_route` + L0.2 slices; multi-engine Lane-O/V/C (§7.6) |
| Business semantics | OCR stage already `supplement_label` / `lab_report` | **L0.5** `document_family` (after IR) |
| Gate | `missing_authoritative_panel` can alone cause low | G6 jointly with G1/G2; `warnings[]` split (§4.1.1) |
| Medication | no independent family | `medication` reserved (§7.9) |

```text
# ❌ Forbidden (Spec §1.4 anti-pattern)
if supplement_label: florence elif lab_report: marker

# ✅ Target (Spec v0.3)
if raster_photo: layout_region crop → ocr + vlm on slices [+ cloud byok]
elif pdf_native: pdf_extract [+ table]
elif pdf_scan: raster-equivalent chain (incl. layout_region)
→ then classify document_family from structure markers
```

Live still often: `vision JSON failed; OCR fallback` — VLM stability is **P0.5**, orthogonal to the media philosophy.

---

## 4. Are there “stronger tools” PHA can use directly?

Yes. Classify by **media and pipeline stage** (**3B-β Perception Worker only**, not into the 7B main dialog). See Spec §7.5.

### 4.1 Local / alongside Ollama (evaluate first)

| Tool | Type | Media | PHA attach |
|------|------|----------|----------------|
| **Apple Vision** | system OCR | `raster_photo` | M4-first Spike (ADP-OCR-01 candidate) |
| **PaddleOCR / Surya** | deep-learning OCR | `raster_photo` | replace/augment Tesseract |
| **Florence-2** | layout regions | `raster_photo` | ADP-LAYOUT-01; optional TABLE substep after crop |
| **Marker / Unstructured** | PDF/tables | `pdf_native` · `pdf_scan` | **not** the first entry for live photos |
| **llama3.2-vision / Qwen2-VL** | local VLM | `raster_photo` (optional) | ADP-VLM-01; Schema decided by `document_family` |
| **LLaVA 1.6** | local VLM | same | fallback |
| **docTR** | document OCR | `pdf_scan` | table-line detection |

### 4.2 Cloud API (T3 · optional, Worker only)

| Service | Strength | Caution |
|------|------|------|
| **Google Gemini Flash / Pro Vision** | same family as the benchmark product | privacy, cost, API key; Worker only |
| **OpenAI GPT-4o / 4.1 mini** | stable structured JSON | same |
| **Anthropic Claude Sonnet Vision** | long-image detail | same |
| **Azure Document Intelligence** | industrial layout+tables | supplement Facts-like layouts |
| **Google Cloud Vision OCR** | general OCR stronger than Tesseract | OCR-layer upgrade |

### 4.3 Not recommended as the main fix

| Approach | Why |
|------|------|
| Only lengthen Tesseract language packs | cannot fix layout/table structure |
| Let Qwen 7B look at base64 images | 7B multimodal is weak; mixed into Harness is hard to audit |
| Brand/ingredient whitelist regex | violates 3B anti-corruption constitution |

---

## 5. Recommended roadmap (aligned with Spec v0.2)

```text
Phase 1 (architecture Spec · already drafted)
  §1.4 ignorant routing + §7.0 media-route + §7.6 post document_family
  retire “supplement→Florence / lab→Marker” business-pre-route narrative
  prod: OCR≥25 short-circuit retired; doc_kind pre-branch → pay down in 3B-β

Phase 2 (implement · local T2)
  media_route detect + raster/pdf dual pipeline
  PHA_PERCEPTION_VISION_MODEL; fail → Paddle/Apple OCR → low refuse

Phase 3 (Spike · by media)
  S0 PDF text layer → S1 raster OCR → S2 Layout → S3 VLM JSON → S4 TABLE substep

Phase 4 (3B-γ)
  medication family + MedicationLedgerV1 + K-layer interaction

Phase 5 (optional T3)
  cloud Vision Worker (Gemini Flash) desensitized/authorized only
```

**Hardware** (see v2.3 §2.2):

- **T1**: OCR + low-confidence refuse (do not invent)
- **T2**: local VLM Worker (split VRAM/process from chat 7B)
- **T3**: cloud Vision API

---

## 6. Capability compare (supplement two-image golden)

| Capability | Tesseract only (prod supplement) | Ollama Vision | Gemini/Grok class |
|------|---------------------------|---------------|----------------|
| Read NOW small mark | poor | mid–high | high |
| Supplement Facts table | poor | mid–high | high |
| Ecommerce UI noise | easy pollution | ignorable | ignorable |
| Offline/privacy | ✅ | ✅ | ❌ API |
| Auditable JSON | needs regex | ✅ | ✅ |
| Feasible on M4 8GB | ✅ | needs quant/small VLM | N/A |

---

## 7. Revision log

| Date | Version | Notes |
|------|------|------|
| 2026-05-26 | v0.1 | First draft: pipeline vs tools, Grok/Gemini benchmark, selection table |
| 2026-05-26 | v0.2 | Media-route + prod gap table; roadmap aligned with Spec §7; retire business-pre tool selection |

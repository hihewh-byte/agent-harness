# PHA long-term development constitution (PM Constitution)

> **Language / 语言**：English (this document) · [中文](pha-pm-constitution.md)

> **Version**: v0.1 (2026-05-27) · aligned with [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) v0.3

## Core vision

This constitution is the highest standing rule for PHA. Goal: stay inside on-device M4 Air compute and local latency, absorb proven agent-development ideas, and eradicate defensive hardcoding and patches aimed at a single test case.

**Terms**: code, telemetry, logs, and API fields use **English keys only**. The zh/en 1:1 table lives in [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) **§0.1** (`layout_region`, `document_family`, `parse_confidence`, `warnings`, …). Do not mix two names for one concept.

---

## Article 1: Mandatory SOTA benchmarking

1. **Rule**: every **new stage** spec (including 3B-γ drug-asset join, Stage 4 autonomous execution) must include a fixed section in §2 or §3: `§X. State-of-the-Art Benchmarking`. **Day-to-day bugfix / Wave patches** may summarize SOTA in the PR description; they need not open a chapter in every small doc.
2. **Audit bar**: before writing private logic, compare pixel-level with mature work such as Claude Code CLI terminal protocol, OpenAI-class native tool-use routing, Vercel AI SDK cache and context trim.
3. **Anti-pattern**: inventing slow, high-latency, non-extensible private wheels. New mechanisms need a cited practice.

---

## Article 2: Telemetry-driven needs

1. **Rule**: feature evolution, harness gate upgrades, and prompt edits must be 100% driven by `Telemetry Track` (real-device logs) or automated tests that actually failed.
2. **Anti-pattern**: god’s-eye feature invention and “pseudo-code hype” in chat.
3. **Canonical contract**: `RECALL_FOCUS` floor slots and Active Recall exist because real multi-turn R3 showed an 11B local model forgetting turn-1 ledger facts (fixture-med start) under long-context noise. Features must “see the words, book the fact, start from the pain”.

---

## Article 3: Deterministic local mesh of “advanced ideas”

1. **Rule**: absorb ideas like Claude Code Active Recall; do **not** copy cloud-scale token stacking.
2. **On-device limits**: every imported agent mechanism is filtered into a local-compliant form:
   - **Low compute**: a background 1.5B shadow model on memory distill may emit **only** a strategy enum (`recall_plan`); it must not write assertion prose or disturb the L3 main thread.
   - **Deterministic state machine**: routing, wake, intercept = L2 harness rules, linear, no inner loops.
   - **Immutable ledger**: core facts (asset names, doses, lab baselines) come only from `LabelLedgerV1` or joined Tier0 clean warehouse rows. The LLM may not “fill in” or rewrite history.

---

## Article 4: Generalized perception infrastructure

1. **Rule**: when real-device E2E (e.g. `scripts/pha_e2e_attachment_label_real.py`) goes red, **do not** prompt-tune or hardcode a brand (NOW) or ingredient (Choline) to pass that fixture.
2. **Root-cause work**: red means the perception base is too weak. Flatten the road, business-family-agnostic (Spec §7.2 · §7.6):
   - **L0.2 physical slices (`layout_region`)**: every `raster_photo` / `pdf_scan` page must emit `layout_regions[]` before VLM/OCR. Crop to generic region types (English keys): `dense_text_block`, `tabular_block`, `header_block`, … — **not** supplement/lab/drug or “Nutrition Facts” as the crop gate. Implementation may swap (Florence-2 `ADP-LAYOUT-01`, heuristic bands); the interface only exposes `region_type` + `bbox_norm`.
   - **Multi-channel fallback (L0 adapter matrix)**: `ocr_cluster` (local OCR line clusters) and optional `cloud_vision_byok` (user-supplied key); arbitrate by confidence; **do not** boost one lane to pass one fixture.
   - **Strip formalist P-layer G\***: `layout_panel_hint_missing` must **not alone** drop `parse_confidence` to `low`; only together with fact-layer refusals such as `no_ingredient_rows` / `no_parseable_dose`. Do not `UNKNOWN_REJECT` clear K-V text because a typical header box is missing.

> **Example (not a rule)**: a US bottle “Supplement Facts” panel may map to `layout_hints.supplement_facts_panel` **after** `document_family=supplement`; it must **not** be the only L0.2 crop target.

---

## Revision

| Date | Version | Note |
|------|---------|------|
| 2026-05-27 | v0.1 | Initial; Article 4 aligned to Spec v0.3 `layout_region`; §0.1 terms; Article 1 SOTA chapter only for new-stage specs |

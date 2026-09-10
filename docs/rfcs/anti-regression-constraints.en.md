# PHA coding-agent anti-regression constraints (Anti-Regression Constraints)

> **Language / 语言**：English (this document) · [中文](anti-regression-constraints.md)

> Warning: the items below are real failure modes captured by Stage 3H stress tests. If any later PR (including Stage 4) causes any of these constraints to regress, Harness has a physical veto over that code.

> Generated at: 2026-09-09 18:54:11 +0800 ｜ seed=20260626 ｜ L1 18/18 ｜ L2 0/0 ｜ captured failure modes 0

---

✅ This elastic long-round stress run is all-green; no new failure modes were captured. Below are the **standing hard red lines** frozen by this battery (even if this run passed, a future PR that violates them is a regression):

- [ERR_GROUNDED_ROUTING] trigger phrase: `“分析检验结果”`
  - Original state: attachment type `lab/medication/unknown`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: after resolve_attachment_qa_mode kicked non-wearable actionable attachments to 'none', control flow slipped into lifestyle and hallucinated
  - Hard intercept: future changes must keep lab/medication/unknown/other (non-explicit cross-year) always routed grounded, and TurnRoutingDecision.attachment_grounded_review=True

- [ERR_WAREHOUSE_FORBIDDEN] trigger phrase: `“看看这张化验单”`
  - Original state: attachment type `lab`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: the universal fallback lane did not physically ban warehouse tools, so the model reached historical data and mismatched it, then control flow slipped into lifestyle and hallucinated
  - Hard intercept: future changes must ensure build_turn_evidence_plan(grounded).forbidden ⊇ {NUMERICS_MANIFEST, PATIENT_STATE_LAB, …} and tools_allowed==[]

- [ERR_FACT_TABLE] trigger phrase: `“帮我看下这张图”`
  - Original state: attachment type `unknown`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: metrics[] was not serialized as an immutable fact table, so the fallback lane lost its unique numeric source and control flow slipped into lifestyle and hallucinated
  - Hard intercept: future changes must ensure focus_summary_from_parsed, when metrics[] is non-empty, emits an “attachment parse facts” table covering each metric

- [ERR_GAMMA_FALLBACK] trigger phrase: `“分析检验结果”`
  - Original state: attachment type `wearable-shaped carrying lab metrics`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: when a specialized lane lacked data but still carried landable metrics, it did not fall back to the universal lane, so control flow slipped into lifestyle and hallucinated
  - Hard intercept: future changes must ensure try_specialized_fallback_to_grounded rebinds attachment_grounded_review and keeps the warehouse ban

- [ERR_PROFILE_LIFESTYLE] trigger phrase: `“分析一下这张截图”`
  - Original state: attachment type `wearable/unknown`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: first-round control flow with an attachment slipped into lifestyle and discarded upstream parse facts, then hallucinated
  - Hard intercept: future changes must ensure the first-round harness profile for an actionable attachment is never lifestyle/empty

- [ERR_TONE_JARGON] trigger phrase: `“HRV 怎么样”`
  - Original state: attachment type `wearable`, previous-round Profile `(first round / consecutive follow-up)`
  - Failure root cause: user-visible answers leaked internal jargon (定账 / warehouse / Tier0 / lane, etc.), then control flow slipped into lifestyle and hallucinated
  - Hard intercept: future changes must ensure user answers are polish-scrubbed and never contain any internal term in JARGON_BLOCKLIST


## Historically closed failure modes

- [ERR_PROFILE_LIFESTYLE] first-round collapse to lifestyle on corrupt/malformed `document_family` (closed 2026-06-26: `resolve_attachment_qa_mode` structural-signal hard takeover of paths+metrics/vision_summary → grounded)

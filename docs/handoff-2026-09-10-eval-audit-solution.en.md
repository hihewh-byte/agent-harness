# Handoff · 40+40 eval audit solution (v1.15 · M1-P19)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-10-eval-audit-solution.md)

> For the successor coding / on-device acceptance agent · 2026-09-10  
> Maintainer authorization: write the three-option audit as the final solution and start work.  
> The first implementation reply must output:

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.15** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) §15–§16 · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md)  
Predecessor: [`handoff-2026-09-09-outline-and-context-lookup.md`](handoff-2026-09-09-outline-and-context-lookup.md) (P17/P18 closed)

**Forbidden**: must-cover / retry on missing rows; clip chat cluster expansion with iOS prefs ∩; Python metric names / if-for-one-golden-sentence; flip Data > Context; start P15 early; weaken Numerics; change TASK before this document and the PRD/RFC.

---

## 0. Why this ticket exists (Constitution §2)

2026-09-09 interpretation 40 + 2026-09-10 chat 40 (`qwen3:14b` · 8788):

| # | Observed | Not this | Architecture gap |
|---|----------|----------|------------------|
| A | Golden-sentence interpretation starts at RHR and only writes the four named items; active energy / SpO2 0/20 | Classifier wrong (still emphasis) | TASK never required sentence 1 to be overall; the model treated “focus on” as exclusive |
| B | Smoke `tier0_budget_exceeded`; Manifest KV truncated at the tail; FACT_CARD_CONTEXT six rows still present | Card has no numbers | Default T0 budget 4500; when soul+T0 exceeds `SYSTEM_CONTENT_MAX_CHARS`, `_cap_system_content` **tail-cuts** (Manifest is last) |
| C | Golden-sentence chat SSE includes `workout_heart_rate_range_bpm` / `workout_count_recent` | User checked workout items | `workout` cluster `intent_hints` include bare “运动/training”; “运动训练/力量训练” are daily_readiness outline words, not workout metrics |
| D | Eval `selected_gap` used “checked and valued must be mentioned” | PRD regression red | Conflicts with the frozen emphasis rule “may mention in the same paragraph; do not sweep the whole card”. Pain is real; gold label is wrong |

Original three-option audit (rejected/rewritten before coding; see conversation 2026-09-10):

| Option | Verdict | This ticket ships |
|--------|---------|-------------------|
| 1 Checked must + retry missing rows + fix Tier0 | **Partially rejected** | **Fix Tier0 only**: KV for rows already on the card must not be tail-truncated. No must/retry |
| 2 Sentence 1 overall, no metric label in that sentence | **Conditional pass** | English TASK only; exclusive must not require an overall opening; acceptance via catalog outline-mode family |
| 3 Card emission ⊆ checked ∩ scope | **Original rejected; rewritten then adopted** | `wearable_daily_review` SSE ⊆ this turn’s FACT_CARD_CONTEXT metric rows; sleep cluster may still expand on “all sleep stages”; training words must not inject `workout_*` into scope |

---

## 1. Frozen contract

1. **emphasis ≠ cover-card.** Do not turn “may mention in the same paragraph” into “valued rows must be named”. Do not run a second LLM pass because rows were missing after generation.
2. **Tier0 survival.** Harness hard constraint #2: TASK / FACT_CARD_CONTEXT metric rows / NUMERICS_MANIFEST KV **must not be squeezed out by tail truncation**. Fact-card profiles **must not** use `format_manifest_tier0_block`’s default 600-character KV chop. On overflow, compress FACT_CARD_CONTEXT advice/summary first (min still keeps values), then ERROR; `_cap_system_content` must not cut T0.
3. **Structure sentences live in TASK only.** Python does not parse metric ids from the assessment prompt (v4 §4.3). Do not hard-weld any one Chinese golden sentence.
4. **Card emission source of truth is this turn’s card, not infer fallback.** When `FACT_CARD_CONTEXT` is present, SSE `metrics_in_scope` / entries ⊆ that card’s `enabled_metric_ids` (including rows merged into the card this turn via cluster expansion). Only without a card may `infer_wearable_metric_ids` be used.
5. **Training words ≠ workout cluster.** Registry `workout_*` `intent_hints` only accept language that names workout metrics (workout heart rate, workout count, …). `goal_markers.daily_readiness` “训练/力量训练/运动类型” only upgrades the profile / enters the outline; it does not fetch `workout_*` numbers.
6. **Red lines unchanged.** Do not flip Data > Context; do not start P15; do not write an if for one golden sentence; do not weaken Numerics.

---

## 2. Task card M1-P19

| Item | Content |
|------|---------|
| ID | **M1-P19** |
| Flag | No new flag. Outline still `PHA_ASSESSMENT_OUTLINE`; cluster expand still `PHA_WEARABLE_CLUSTER_EXPAND` |
| Harness class | **P1** (TASK contract + Tier0 survival + Registry hints + card-emission scope) |
| Out of scope | must-cover, retry missing rows, prefs∩, P15, C3 brief slice (still the established Data>Context cost; separate ticket) |

Acceptance (offline selfcheck; assert via enums/registry; no Python equals on a specific Chinese prompt):

| ID | Scene | Pass |
|----|-------|------|
| P19-T | emphasis TASK contains Sentence 1 = overall and no metric id / Chinese metric name; exclusive TASK **does not** contain an overall opening sentence | `pha_p19_selfcheck` |
| P19-K | Contains daily_readiness training words, no named workout HR/count → `infer_wearable_metric_ids` **excludes** `workout_*`; naming “workout heart-rate range” still includes it | same |
| P19-S | “睡眠的各项” still expands the sleep cluster (deep/REM/core/awake) | same |
| P19-C | When a fact_card payload exists, SSE `metrics_in_scope` ⊆ card `enabled_metric_ids`, even if the user sentence contains “运动训练” | same |
| P19-B | Large `fact_card_interpret` card: assembled T0 contains every Manifest value; no “system prompt fused/truncated” cutting T0; `protect_tier0` path does not tail-cut | same |

On-device (this ticket does not block closeout; maintainer schedules separately): golden-sentence interpretation sentence 1 talks overall then named items; chat card emission has no `workout_*`.

---

## 3. Rollback

- TASK emphasis structure sentence: git revert the corresponding section of `harness_plan.py` (cache key `_interpret_prompt_rev` changes automatically).
- Tier0: revert `harness_tier0_assembly.py` / `chat_message_stack.py`.
- workout hints: revert registry + `pha_wearable_bundle_schema_generate.py --write`.
- Card emission: revert `grounded_answer_composer.py`.

---

## 4. Explicitly not this ticket

- Checked-and-valued must-cover / retry missing rows
- Copy Apple Readiness 0–10 into the notification or TASK
- C3 “medication vs HRV” pouring the brief (do not flip Data > Context)
- Compile CHB / P15 early
- Write eval `selected_gap` gold into the product

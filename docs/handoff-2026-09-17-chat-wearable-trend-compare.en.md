# Handoff · 2026-09-17 · Chat wearable trend/compare evidence recipe (focal + compare → Manifest)

> **Language / 语言**：[中文](handoff-2026-09-17-chat-wearable-trend-compare.md) · English (this doc)

> For the coding agent that picks this up · **Docs only; zero production code until the maintainer orders coding**  
> Trigger: Mac chat “How have my HRV and deep sleep changed over the past week?” + “Compare with previous labs” → model cited only 2026-09-11–17 means and said prior HRV/deep-sleep data was missing.  
> Maintainer ruling: not Loop; not online LLM→harness re-fetch. Fix as an **evidence-shape recipe** (not a single-utterance corner case).  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.en.md`](prd-pha-ios-proactive-agent-v1.en.md) **v1.33** · card **M1-P23** · FR-6.16

First implementation reply must print:

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

If touching restart/listen: also `CONSENSUS_ACK: stability-plan-v2026-06-10 read`

---

## 0. One line

For chat turns whose goal is change / trend / compare / vs-history on **wearable** metrics, the rule layer must assemble **focal-window stats + compare-side stats** into the Numerics Manifest **before** the LLM. If compare is missing, disclose via rules/skip-LLM. **Forbidden**: focal means alone while allowing rise/fall talk; **forbidden**: Loop aliases or online Reflection mutating Plan to backfill. Same shape as fact-card M1-P22 (`assessment_compare`); this card closes the **chat-side gap**.

---

## 1. Problem and frozen judgment

| Observation | Judgment |
|-------------|----------|
| Reply had only last-week HRV/deep means; claimed no history for trend | Upstream **compare evidence not in Manifest (or not required)**; “cannot judge” is an honest symptom, not the root cause |
| Ledger has long HRV/sleep history; `wearable_only` mounts `WEARABLE_90D_SUMMARY` by design | Likely grain-bound focal without compare atoms / TASK duty, or follow-up scope confusion — verify on disk at coding time |
| Follow-up “compare with previous **labs**” | **Cross-domain**: labs ≠ wearable history → clarify; do not answer labs with one-week wearable means |
| Ring R / Loop live harvest? | **No.** Loop = catalog aliases; Ring R offline, **Plan immovable**; online Core does not mid-turn self-heal |
| LLM asks for more data then re-fetch? | **Forbidden.** Steering wheel stays with Harness |

Maintainer-agreed: infinite phrasing ≠ infinite evidence shapes. Recognition collapses to few recipes; this card only adds **trend/compare = focal + compare**.

---

## 2. Non-goals

- No Python utterance `if` / golden-sentence patch for “last week + HRV + deep sleep”.
- No Numerics relaxation so the model invents “prior” means.
- No online Reflection / tool loop **overturning** `TurnEvidencePlan` to fetch baseline.
- No Loop A alias proposal as a substitute for compare numbers.
- Do not change HTML fact-card progressive baseline; primary surface is **`/api/chat` wearable**. Reuse P22 compiler ideas; do not bind chat to interpret-only APIs.
- Out of scope: cross-domain causation; new evidence shapes → new cards.
- No string-match exemptions for “no prior data” to game evals.

---

## 3. Design principles

```text
User utterance ──resolve──► metrics + focal_window + goal∈{lookup, trend_compare, …}
                                    │
                    goal = trend_compare │
                                    ▼
               Rule recompute: focal_stats + compare_stats
                                    ▼
               Manifest ⊇ focal atoms ∪ compare atoms (or compare_insufficient)
                                    ▼
               TASK: cite both sides; insufficient → skip-LLM / ledger template
                                    ▼
               LLM may only copy ──► Numerics audit (still ⊆ Manifest)
```

1. **Evidence before LLM.**
2. **Shape acceptance, not golden sentences** — ≥2–3 grain/metric variants.
3. **Isomorphic to P22, separate path** — share parse/recompute libraries; no conflicting definitions.
4. **Cross-domain clarify** before mixing lab and wearable.
5. **Loop/catalog only widen recognition** into `trend_compare`; recipe topology stays fixed.

---

## 4. Intent and trigger contract

### 4.1 Recipe key

| Key | Meaning | This card |
|-----|---------|-----------|
| `lookup` | Point/window readout | Status quo; no forced compare |
| **`trend_compare`** | change / trend / vs prior / up-down | **Force focal + compare** |
| `lab_*` | Lab dossier | Not this recipe; see §4.3 |

Triggers live in **Intent Catalog / schema** (zh/en). No long hard-coded lists in `harness_plan.py`.

### 4.2 Focal window

Reuse `wearable_time_grain` / `HealthTurnScope.wearable_window`. Disclose default window in TASK if user omitted one.

### 4.3 Compare-side default

| Priority | Strategy |
|----------|----------|
| 1 | Progressive personal baseline (90d→365d→all, FR-2.6) mean + n + `baseline_window` |
| 2 | Or mount ~90d summary **with means/n as Manifest atoms** (prose-only `WEARABLE_90D_SUMMARY` is insufficient) |
| 3 | Optional backlog: equal-length prior window |

Insufficient samples → `compare_insufficient` + real n; **no** fake percentiles/directions; prefer skip-LLM template.

### 4.4 Cross-domain clarify

Wearable-trend thread + “previous **labs**/bloodwork” → clarify: wearable history only / labs only / both.

---

## 5. Manifest / TASK / failure modes

Manifest must include focal atoms + compare atoms (or insufficient marker). Dual tokens OK (focal N + compare 90). TASK: both sides required for change talk; no rise/fall without compare atoms. Weak causation only.

---

## 6. Likely code touchpoints

Intent catalog/schema · `health_turn_resolver` · shared recompute (prefer reuse from `fact_card_assessment_window` / fact-card baseline) · `harness_plan` wearable profiles · chat numerics compose · `clarify_turns` · flag `PHA_CHAT_TREND_COMPARE` (default on).

Do **not** change `packages/harness_core`, Loop promote, or HTML baseline defaults.

---

## 7. Acceptance (shape)

| ID | Example | Pass |
|----|---------|------|
| T1 | Past-week HRV + deep sleep changes | With history: Manifest has focal + compare; body must not claim “no prior data” |
| T2 | 14-day resting HR trend | Same recipe; different metric/window |
| T3 | Follow-up vs previous labs | Clarify or lab path — not one-week wearable means alone |
| T4 | Focal ok, compare n short | Disclose; no direction claim |
| T5 | “How much deep sleep yesterday?” | Must **not** force compare |

---

## 8. Order of work

| Step | Work | Status |
|------|------|--------|
| 0 | Disk-verify plan/Manifest | ✅ 2026-09-17 |
| 1 | Catalog `trend_compare` | ✅ T1/T5 |
| 2 | Compare into Manifest | ✅ T1/T2; build `pha-v2.3.59` |
| 3 | TASK + skip-LLM insufficient | ✅ T4; build `pha-v2.3.60-p23-task-insuff` |
| 4 | Cross-domain clarify | **Cut** (presentation_filter false demand) |
| 5 | Mark M1-P23 DONE | ⏳ pending maintainer 8788 device OK |

Local commit OK when coding steps land; no push unless asked.

---

## 9. Loop / Reflection boundary

Loop may add aliases that land in `trend_compare`. Ring R offline attribution only. Stage 3G: Plan immovable. If a later “3-week SpO2 change” needs a parallel card, the implementation was a corner case — reject.

---

## 10. Open / cuttable

Equal-length prior window; special post-audit for “ignored injected compare”; full merge of chat+interpret compare APIs.

---

## 11. Rollback

`PHA_CHAT_TREND_COMPARE=0`.

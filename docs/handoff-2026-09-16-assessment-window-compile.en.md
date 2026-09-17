# Handoff · 2026-09-16 · Option B: compile assessment window into Manifest (then interpret)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-16-assessment-window-compile.md)

> For the next coding agent · **docs only; zero production code until the maintainer orders implementation**  
> Trigger: fact-card interpretation discarded on `unauthorized_window:14`; maintainer asked whether accurate “last 10 days / last 2 weeks” should pass.  
> Draft SoT: [`prd-pha-ios-proactive-agent-v1.en.md`](prd-pha-ios-proactive-agent-v1.en.md) **v1.32** · card **M1-P22**

**Status: M1-P22 DONE (2026-09-16).** Arbitrary explicit N generalized; dual 90 + assessment tokens; vs-yesterday included. build `pha-v2.3.57-p22-assess-window`.

First implementation reply must emit:

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

---

## 0. One sentence

Explicit “last N days / N weeks” in the user assessment prompt must **not** be fixed by relaxing Numerics or by letting the model compute. The rule layer must recompute compare stats for N **before** the LLM, write them into the interpretation inject card and Numerics Manifest, and keep fail-closed audit. The HTML-visible progressive baseline (90d→365d→all) **does not change**.

---

## 1. Problem and evidence

| Symptom | Evidence |
|---------|----------|
| Assessment can name any window phrase | prefs `assessment_prompt` → `USER_ASSESSMENT_PROMPT` (outline, **not** a numeric source) |
| Card baseline is progressive only | `pha/fact_card.py`: `90d`→`365d`→`all` |
| Manifest window tokens ⊆ card | `build_fact_card_numerics_manifest` from `baseline_window` |
| Model “近 14 日” → whole block dropped | interpret cache `unauthorized_window:14` |
| FR already frozen | FR-6.8 window wording must match rule layer; FR-6.10 assessment prompt **cannot unlock S-tier** |

“If the N-day numbers are accurate they should pass” is right as a product goal, but today there is **no compute step for accuracy**—audit only membership-tests the whitelist.

---

## 2. Non-goals

- Do **not** relax `unauthorized_window` for arbitrary N.
- Do **not** let the LLM invent N-day means/percentiles.
- Do **not** change the HTML progressive baseline (P7); this knife only changes the **interpret inject** view (same layering as P20 exclusive inject).
- Do **not** unlock other S-tier classes without Manifest membership.
- No Python metric/drug name tables; extend `wearable_time_grain`.
- Not option A (show “latest” for empty accrual today).
- Not “vs yesterday” point-day delta compile in this knife (open question §8).

---

## 3. Design

```text
assessment text ──parse──► assessment_window (N or fail)
                              │
                              ▼
                 rule-layer compare_* per metric
                              │
                              ▼
            inject card + Manifest tokens (N + compare nums)
                              │
                              ▼
                 LLM copies only ──► Numerics audit (still ⊆ Manifest)
```

1. Evidence before LLM.  
2. Dual card: HTML = progressive baseline; inject = card ∪ `assessment_compare` when present.  
3. No window phrase → behavior unchanged.  
4. Insufficient n → still emit n / tokens; no fake percentile.  
5. Orthogonal to exclusive: slice named rows first, then attach compare on the slim card.

---

## 4. Parse contract

**Input:** `assessment_prompt` only.

| Example | `window_days` | Manifest spoken tokens |
|---------|---------------|----------------------|
| last 10 days / 近 10 天 | 10 | `10` |
| last 2 weeks / 近 2 周 | 14 | `14` (+ `2` if copy says “2 weeks”) |
| last 7 days / 近一周 | 7 | `7` |

Extend grain for “N weeks” / “two weeks”. Multiple distinct N → fail-closed, no compare (`assessment_window_ambiguous`). Clamp N to `[1, 365]` and disclose the **adopted** N. Vague “recently” → no compare.

---

## 5. Recompute

For each inject metric with a value, same field as baseline samples; same exclude-anchor-day convention as P7; write `assessment_compare.per_metric.{id}.{n,mean,min,max,percentile,band}`. Never relabel progressive-baseline numbers as the assessment window.

---

## 6. Manifest / audit / TASK

- Union window tokens and compare numerics into Manifest.  
- Keep S/E/commons philosophy; do not weaken audit.  
- TASK: when `assessment_compare` present, rolling phrases and compare stats must match that block.  
- Cache key includes assessment-window digest.

Default: keep progressive `90` tokens alongside assessment `14` (see §8).

---

## 7. Code touchpoints (when coding)

`wearable_time_grain` → `attach_assessment_compare` → `fact_card_interpret` (after exclusive slice) → `build_fact_card_numerics_manifest` → TASK copy → selfcheck. Optional flag `PHA_ASSESSMENT_WINDOW_COMPARE` default on. HTML `/view` must **not** attach.

---

## 8. Maintainer decisions before code

1. Keep both 90 and 14 tokens (recommended) vs strip baseline compare from inject when assessment window present?  
2. Exclude anchor day like P7 (recommended) vs include today in “last N days”?  
3. Fold “vs yesterday” into a later phase?  
4. Agree N clamp at 365?

---

## 9. Acceptance

W1–W6 as in the Chinese doc: 14 whitelisted after compile; inventing 14 without prompt still rejected; ambiguous dual-N fail-closed; exclusive ∩ compare; n&lt;7 no fake percentile. Full `pha_fact_card_selfcheck` green.

---

## 10. PRD draft

**FR-6.15** Assessment rolling-window compile (see Chinese §10). **M1-P22** TODO.

---

## 11. Rollback

Flag off or revert attach/manifest/TASK; HTML unchanged.

---

**Maintainer intent:** last-N must pass only after Manifest compile — not via audit looseness; visible progressive baseline stays.

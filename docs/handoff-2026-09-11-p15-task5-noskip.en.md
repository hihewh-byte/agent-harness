# Handoff · 2026-09-11 · P15 next knife: land v1.19 (no-skip) + Qwen3 gold ×20

> **Language / 语言**：[中文](handoff-2026-09-11-p15-task5-noskip.md) · English (this file)

> For the next coding / acceptance agent · 2026-09-11.  
> **Authoritative detail is in the Chinese twin** — keep both in sync if you edit.  
> Prior chat: [P15 eval & TASK judgment](c87f5b03-8377-4253-ac9f-69c95b66631b)  
> Canvas: `canvases/pha-p15-gold-meds-eval.canvas.tsx`  
> Runs: `reports/p15_eval/runs.jsonl`

**Status: P15 = DONE (2026-09-11 maintainer stamp).** Evidence `runs_v244_commons_gold10.jsonl`: `slot_named_ge2` 5/10 accepted. Deferred items in Chinese twin §8.3 / change-log. No git in this chat.

First implementation reply must include:

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

Stack `CONSENSUS_ACK: stability-plan-v2026-06-10 read` if touching restart.

Source of truth: Chinese twin + PRD **v1.22**.

---

## One-liner

Brief already contains fixture-med/fixture-supp. Gold-sentence mention rate ≈ 0 because **runtime TASK still says `skip it when unrelated`**, while **approved PRD v1.19 forbids whole-slot skip**. Next knife = land v1.19 (TASK §5 + lead copy). **Reject** Gemini’s “MUST synthesize a 注意事项 section”. Then run **qwen3:14b × gold sentence × 20** only.

---

## Disk vs docs (verified 2026-09-11)

Still present on disk:

- `pha/harness_plan.py` (both TASK copies): `skip it when unrelated…`
- `pha/fact_card_copy.py` `bg_brief_lead` EN/ZH: ignore / 「无关则忽略」

Change-log claimed this was fixed; **code did not land or was reverted**. Fix disk first.

v1.20 lineage stub filter stays.

---

## Maintainer ruling on Gemini

| Claim | Ruling |
|---|---|
| Don’t re-run 20 under skip | Agree |
| Root cause = skip clause | Agree |
| Qwen3 only for next acceptance | Agree |
| MUST open a Precautions **section** | **Reject** (v1.19: fold into advice; no numbered precautions list) |
| MUST cross-reference every brief item to today’s metrics | Too strong — risks causal overclaim |
| Clean slot-only wording (no drug/training names) | Agree |

Target TASK shape (English; fold into advice, no separate list; optional causal forbid):

```text
5. When USER_BACKGROUND_BRIEF is present and non-empty, fold its self-reported
   items into the advice wording as cautions. Do not skip the slot. Never cite
   it as data; never restate or infer doses. Do not open a separate numbered
   precautions list. Use cautious correlational language only; forbid definitive
   causal claims (causes / leads to).
```

---

## 40-run snapshot (do not re-run under old TASK)

Gold: both models 10/10 audit + training advice; **fixture-med 0/20**; Qwen ~50s vs R1 ~162s.  
Meds-HRV prompt: Qwen better named coverage; R1 causal/Markdown/one `96.0` reject.  
Default for this track: **qwen3:14b**.

---

## DONE gate (stamped 2026-09-11)

Zero invent · no hard Markdown (post-strip) · **gold**: advice names **≥2 concrete brief items**; fixture-med∧fixture-supp is **not** the training-gold bar · **meds-HRV** (if run): fixture-med∧fixture-supp still applies · prefs unchanged · personal-data audit not weakened. Training commons ints pass via Manifest `population_commons` (int ∧ no card label in clause). **5/10 `slot_named_ge2` accepted** (former ≥8/10 suggestion is deferred / non-blocking).

**P15 DONE.** Deferred: audit decimals/some ints, naming rate, prefs checkbox drift, think perf.

Frozen gold prefs (do not write disk for alternate prompts):

- Prompt: overall readiness + RHR/HRV/sleep + training advice / strength?
- Metrics: `sleep_deep`, `sleep_time_asleep`, `hrv_sdnn_ms`, `resting_heart_rate_bpm`, `active_energy`, `spo2_percent`

---

## Hard no

must-cover / missing-row retry / prefs∩ / flip Data>Context / brief digits→Manifest / add `fact_card_interpret` to `USER_CONTEXT_BRIEF_PROFILES` / drug-name tables / “training named ⇒ supplements related” / gold-sentence Python if / re-run 20 while skip remains / Gemini must-section / DeepSeek on next acceptance slot.

Full checklist, paths, and run commands: see Chinese twin §§2–11.

# Handoff · 2026-09-11 · P15 next knife: land v1.19 (no-skip) + Qwen3 gold ×20

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-11-p15-task5-noskip.md)

> For the next coding / acceptance agent · 2026-09-11  
> Maintainer intent: **continue in a new chat**; this file is the sole start-of-work summary.  
> Prior chat transcript: [P15 eval & TASK judgment](c87f5b03-8377-4253-ac9f-69c95b66631b)  
> Eval canvas: [pha-p15-gold-meds-eval](canvases/pha-p15-gold-meds-eval.canvas.tsx)  
> Raw JSONL: `reports/p15_eval/runs.jsonl` (full 40-run set)

**Status: P15 = DONE (2026-09-11 maintainer stamp).** Evidence `runs_v244_commons_gold10.jsonl`: `slot_named_ge2` 5/10 accepted. Deferred items in §8.3 / change-log — open later. No git in this chat.

First implementation reply must include:

```text
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
```

Stack `CONSENSUS_ACK: stability-plan-v2026-06-10 read` if touching start/restart.

Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.22** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) **§19–§20** · change-log “P15 → DONE” entry.

---

## 0. One-liner

Pipeline works (brief contains fixture-med/fixture-supp). Gold ×20 with fixture-med=0 happened because **runtime TASK still said `skip it when unrelated`**, while **approved PRD v1.19 forbids whole-slot skip**. Next knife = land v1.19 (TASK item 5 + lead copy). **Do not** adopt Gemini’s “MUST open a separate precautions section”. After the fix, run gold ×20 with **qwen3:14b** only.

---

## 1. Read order (save tokens)

1. This document  
2. PRD FR-6.8 / FR-6.12 (v1.19–v1.20) + §8 M1-P15  
3. 3F RFC §19 (slot contract) + §20 (lineage stubs)  
4. Disk check (§4) — **disk wins; do not trust “already landed” in change-log**

You need not read all 40 run bodies; canvas or `runs.jsonl` summary is enough.

---

## 2. Hard red lines (always on)

- TurnEvidencePlan before LLM; user-visible numbers ⊆ Numerics Manifest.
- **No** new Python phrase / metric / label / **drug-name** hardcode tables.
- Fail-closed; no day/metric swap; **do not** flip Data > Context.
- **Do not** scan the whole card against P9.5b; **do not** add a Python `if` for one gold sentence.
- **No** must-cover / missing-row retry / prefs∩ / runtime LLM self-heal / weaken Numerics.
- Brief digits must not enter Manifest; **do not** add `fact_card_interpret` to `USER_CONTEXT_BRIEF_PROFILES`.
- **No** “training named ⇒ supplements related” TASK patch.
- Do not change TASK before PRD/RFC — but v1.19 **already approved** no-skip; this knife lands it, invents nothing new.
- Alternate assessment prompts only via in-memory `assessment_prompt=`; **never write prefs**.
- After tests, prefs must still be the frozen gold sentence + six checked metrics.

---

## 3. Status board

| Card | Status |
|---|---|
| M1-P6 / P7 / P12 | DONE (population share refs off; **personal percentiles still on card JSON/Manifest**) |
| M1-P15 | **DONE** (2026-09-11) |
| M1-P20 | **DONE** (2026-09-11 iPhone same-network exclusive resting-HR screenshot) |
| M2 | Not opened |

Remote: `https://github.com/hihewh-byte/agent-harness.git`. Agents commit locally only; maintainer pushes. Do not commit unless the user asks.

Runtime: launchd `gui/<uid>/com.personal-health-agent.pha-8788`; env `~/Library/Application Support/pha/env-8788.sh` (ingest token **must not be echoed**); long interpret `export LLM_TIMEOUT_SECONDS=300` (`.env` defaults 120; dotenv does not override an already-exported value). Restart: `bash scripts/pha_restart_accept.sh`. Default model target: **qwen3:14b**. `OLLAMA_THINK=false`. On 16 GB do not run two models in parallel.

**Note**: `pha/build_marker.py` on disk may still show an old build (e.g. `pha-v2.3.34-…`); change-log once wrote `pha-v2.3.38/39`. Bump after real edits; UI old build needs restart accept.

---

## 4. Docs vs disk gap (direct target of the next knife)

### 4.1 Approved (v1.19 / 3F §19)

| Do | Do not |
|---|---|
| Brief present → in-scope; **forbid whole-slot skip** | “Training named ⇒ supplements related” |
| Lead-in drops “ignore if unrelated” | Drug-name table; add `USER_CONTEXT_BRIEF` on interpret turns |
| **Fold into advice sentences; no separate numbered precautions list** | Weaken Numerics; brief digits → Manifest |
| Zero invent (no derived 100−percentile, etc.) | |

### 4.2 Disk as of 2026-09-11 check

`pha/harness_plan.py` item 5 (`_FACT_CARD_INTERPRET_TASK` and `_FACT_CARD_INTERPRET_TASK_SHARED_TAIL` **both**) still:

```text
… skip it when unrelated to the rows the assessment named.
```

`pha/fact_card_copy.py` lead still:

- EN: `ignore anything unrelated to today's card`
- ZH: `与今日卡片无关则忽略`

→ Change-log “P15 TASK slot contract” **claimed** a fix; code **did not land or was reverted**. Fix these two first, then re-run acceptance.

### 4.3 v1.20 already landed (keep)

Lineage drops metric-field stubs (`_is_lineage_field_stub` + `bg_lineage_stub_marks`); empty → omit the section. Selfcheck: `scripts/pha_chb_compiler_selfcheck.py`. Do not roll back.

---

## 5. 40-run eval (done — do not re-run under the old contract)

Script: `reports/p15_eval/run_p15_batch.py` (resumable). Conditions: gold prefs, in-memory second prompt, `LLM_TIMEOUT=300`, `OLLAMA_THINK=false`. Wall clock ~80 min.

### 5.1 Gold sentence (10 each)

| | qwen3:14b | deepseek-r1:14b |
|---|---|---|
| Audit pass | 10/10 | 10/10 |
| Training / strength advice | 10/10 | 10/10 |
| Names fixture-med | **0/10** | **0/10** |
| Names fixture-supp | 0/10 | 3/10 (often generic “supplement”; not a precautions pass) |
| Hard Markdown / invent 85 / timeout / think leak | 0 | 0 |
| Mean latency | ~50 s | ~162 s |

### 5.2 Meds-HRV prompt (in-memory, 10 each)

Prompt (zh): recent HRV and resting HR not at best — any effect from usual meds/supplements on HRV and resting HR?

- qwen3: dual-name hedge 6; fixture-supp only 3; slot skip 1; audit 10/10.
- DeepSeek: more scattered; causal overclaim 5/10; hard Markdown 2; one `unauthorized_value:96.0` (card has 96.1).

### 5.3 Model ruling (maintainer-approved direction)

- **This track default / next acceptance: qwen3:14b only.**
- DeepSeek does not take the next slot (invent risk + causal overclaim + latency). Need not become a permanent product-wide ban.

---

## 6. Maintainer ruling on Gemini (final — execute this)

| Gemini claim | Ruling |
|---|---|
| Do not re-run 20 while skip remains | **Agree** |
| Root cause = `skip it when unrelated` | **Agree** |
| Next acceptance: Qwen3 only | **Agree** |
| Keep lineage-stub knife | **Agree** |
| Clean wording (no drug/training names in TASK) | **Agree on direction** |
| **MUST synthesize a `注意事项` section** | **Reject** — conflicts with v1.19 “fold into advice; no numbered precautions list”; invites list/Markdown body |
| MUST cross-reference with today’s metrics | **Too strong — do not use verbatim** — amplifies causal overclaim; Context tugging Data |
| “DeepSeek uniquely unusable” | **Soften** — deprecate as interpret default is enough |

### 6.1 Landing shape (write English TASK this way; sync one sentence in ZH/EN PRD/RFC)

**Do:**

1. Delete `skip it when unrelated` / 「无关则忽略」 from TASK and lead.  
2. Non-empty brief → must enter advice wording as caution (no whole-slot drop).  
3. Fold **into advice sentences**; no separate numbered “precautions” section / list.  
4. Keep: not data; no restated/inferred doses.  
5. **Optional add** (E5 evidence): forbid definitive causal (`causes` / `leads to`); correlational / monitor wording only.  
6. Keep zero invent and no hard Markdown (`* # \``).

**Do not:**

- Example fixture-med / fixture-supp / strength training / supplements/medications inside TASK (avoid even category words; cite the slot name).  
- “Training named ⇒ supplements related”.  
- Forced standalone `注意事项` heading block.

Reference (not a locked draft; agent may tighten tone before landing, but must not re-introduce a must-section):

```text
5. When USER_BACKGROUND_BRIEF is present and non-empty, fold its self-reported
   items into the advice wording as cautions. Do not skip the slot. Never cite
   it as data; never restate or infer doses. Do not open a separate numbered
   precautions list. Use cautious correlational language only; forbid definitive
   causal claims (causes / leads to).
```

Sync `bg_brief_lead` EN/ZH to drop “ignore unrelated”; if CHB re-renders from current copy, editing copy is enough.

---

## 7. Coding checklist (next knife)

1. `pha/harness_plan.py`: both item-5 copies (base + SHARED_TAIL).  
2. `pha/fact_card_copy.py`: `bg_brief_lead` EN/ZH.  
3. If selfcheck asserts old skip copy → update fixtures.  
4. ZH/EN PRD / 3F §19: bump a minor version only if adding the weak-causality forbid sentence; if only landing already-written “no skip”, a major bump is optional, but change-log **must** record “disk landed v1.19 + causal guard”.  
5. Bump `pha/build_marker.py` (e.g. `pha-v2.3.40-p15-noskip`).  
6. ZH/EN `pha-ios-proactive-change-log` + `harness-change-log`.  
7. **Do not** touch prefs; **do not** open M2; **do not** weaken audit.

---

## 8. Acceptance: gold ×20 (run only after the fix)

### 8.1 Frozen prefs (check before and after)

Assessment prompt:

```text
评估今天整体身体状况，重点看今天的静息心率与HRV，睡眠的各项指标，用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议，是否可以进行力量训练？
```

Checked six: `sleep_deep`, `sleep_time_asleep`, `hrv_sdnn_ms`, `resting_heart_rate_bpm`, `active_energy`, `spo2_percent`.

### 8.2 How to run

```bash
set -a; source "$HOME/Library/Application Support/pha/env-8788.sh"; set +a
export LLM_TIMEOUT_SECONDS=300 PHA_AGENT_TIMEOUT_SECONDS=300
export OLLAMA_KEEP_ALIVE=10m OLLAMA_THINK=false
export PYTHONPATH="."
# qwen3:14b × gold ×20 only; adapt batch script or loop run_interpretation
```

Path: `pha.fact_card_interpret.run_interpretation` (fact-card slot), not `/api/chat`.  
Reuse/adapt `reports/p15_eval/run_p15_batch.py` (PER_CELL=20, gold + qwen3 only; **do not write prefs**).

Injection check: brief contains fixture-med and fixture-supp; `notes_used` / `brief_source` (chb or live_notes OK — slot non-empty with category self-report matters). This batch once saw `live_notes` notes_used=1 while body still named both items — trust injected content.

### 8.3 P15 DONE gate (already stamped)

Maintainer restated and stamped 2026-09-11:

1. Zero invent (no unauthorized; no derived 85/21.5). Training commons ints via Manifest `population_commons` (int ∧ no card metric label in the same clause) pass and are not invent.  
2. No hard Markdown (post-strip).  
3. **Gold**: advice surfaces **≥2 concrete brief items**. fixture-med∧fixture-supp is **not** the training-gold bar. **5/10 acceptable** (former ≥8/10 suggestion becomes non-blocking deferred).  
4. **Meds-HRV prompt** (if run): fixture-med ∧ fixture-supp dual-name bar still applies.  
5. Prefs unchanged after the run.  
6. Do not weaken personal-data audit.

**DONE.** Deferred (open later): audit decimals/some ints, `slot_named_ge2` rate, prefs checkbox drift, think perf.

---

## 9. Explicit non-goals

- Re-run 20/40 “just to confirm” while skip remains.  
- Gemini verbatim “MUST synthesize 注意事项 section”.  
- DeepSeek taking another acceptance slot.  
- must-cover / missing-row retry / prefs∩ / flip Data>Context / brief→Manifest / interpret `USER_CONTEXT_BRIEF` / drug-name tables / strip card percentiles to pass a test / weaken Numerics.  
- Unauthorized commit/push.

---

## 10. Start checklist (copy for a new agent)

- [ ] Emit CONSENSUS_ACK lines  
- [ ] `rg "skip it when unrelated" pha/harness_plan.py` still present → fix per §6  
- [ ] Sync `bg_brief_lead` EN/ZH  
- [ ] Related selfchecks PASS  
- [ ] Bump build + change-log  
- [ ] Prefs still gold  
- [ ] qwen3:14b × gold ×20; write results under `reports/p15_eval/`  
- [x] Decide P15 DONE per §8.3 — **DONE (5/10 accepted)**  
- [ ] Reply to maintainer: pass rate + failure samples + prefs unchanged  

---

## 11. Path cheat sheet

| Path | Role |
|---|---|
| `pha/harness_plan.py` | TASK item 5 |
| `pha/fact_card_copy.py` | `bg_brief_lead` |
| `pha/fact_card_interpret.py` | `run_interpretation` |
| `pha/fact_card_background_brief.py` | brief build / lead |
| `pha/chb_compiler.py` | lineage stub filter (landed) |
| `data/fact_card_prefs.json` | gold prefs (do not edit) |
| `reports/p15_eval/runs.jsonl` | prior 40-run evidence |
| `docs/prd-pha-ios-proactive-agent-v1.md` | v1.20+ |
| `docs/stage3f-intent-resolution-completeness-rfc.md` | §19–§20 |

---

**Maintainer passphrase summary**: P15 DONE (fixture-med not training gold; 5/10 slot≥2 acceptable). Deferred open later. No git in this chat.

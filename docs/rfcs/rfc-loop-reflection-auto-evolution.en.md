# PHA / harness-core: Loop Engineering + Reflection auto-iteration plan

> **Language / 语言**：English (this document) · [中文](rfc-loop-reflection-auto-evolution.md)

> Companion: Stage 4 RFC `docs/rfcs/rfc-stage4-offline-loop-engineering.md`  
> Trigger: after the 2026-07-11 all-English 50×≥8 stress run and clone-to-run

## 1. Goal

Freeze “stress / real sessions → failure modes → reviewable PR → CI veto → runtime gets smarter” into a **repeatable, non-runaway** evolution loop. The evolution target is **recognition coverage and the user ledger**, not control-flow topology.

## 2. Dual loops + Reflection (recommended landing shape)

```text
                 ┌─────────────────────────────────────┐
                 │  Reflection Critic (offline, read-only) │
                 │  In: JSONL stress / telemetry / error book │
                 │  Out: failure taxonomy + patch proposal draft │
                 └──────────────┬──────────────────────┘
                                │
        ┌───────────────────────▼───────────────────────┐
        │  Loop A · global recognition (catalog / aliases) │
        │  Harvest → Cluster → Distiller → 1E → human-review PR │
        └───────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────▼───────────────────────┐
        │  Loop B · user-value (CHB Facts / Interpretation) │
        │  session evidence → cold user-ledger update → personalized answers (no global routing edits) │
        └───────────────────────┬───────────────────────┘
                                │
                        Layer 2 immune gates
                 L1 selfcheck · Bank · Nightly 148/164
```

### Reflection mechanism (suggested new “Loop R”)

| Step | Do | Don’t |
|------|----|-------|
| **Observe** | Aggregate `en_stress_50x_*.jsonl`, harness JSONL, slow_round_candidates | Do not change weights online |
| **Critique** | Classify by taxonomy: RLP leak, metric mis-ledger, weak follow-up re-table, locale template not bilingual | Do not let Critic directly edit the Python state machine |
| **Propose** | Emit `pha.loop_proposal/v2`: catalog alias / English composer copy / fixture | Forbidden to change `harness_profile_registry` topology |
| **Verify** | Subset English stress (e.g. EN07/EN15/EN50) + selfcheck | Fail → veto, no merge |
| **Adopt** | Human-review PR → Nightly full suite | Forbidden auto-merge to main |

Implementation suggestion: reuse existing `scripts/pha_telemetry_harvest.py` + `scripts/pha_loop_alias_distiller.py`, add `scripts/pha_reflection_critic.py`:

- Input: one stress JSONL + optional harness report  
- Output: `reports/loop/reflection_{ts}.md` + `reports/loop/proposals/{id}.json`  
- Critic prompt may only cite a Layer 1 asset-path allowlist

## 3. Hook to this English stress run

The English 50×8 run is **high-quality seed corpus for Loop A** and an **RLP regression suite**:

1. **Harvest**: any `non_english_cjk_ratio` / `api_error` / `metric_*` failure → `slow_round_candidates`  
2. **Distill**: English colloquial aliases (“How's HRV?”, “SpO2?”) into `health_intent_catalog` / schema triggers  
3. **RLP special zone**: deterministic templates (warehouse focus, CompareTable opener, follow-ups) must go through `response_locale` (this run already fixed the warehouse-focus English path)  
4. **Nightly**: `PHA_E2E_EN_STRESS=1` can run a slim 10-set; full 50-set Weekly

## 4. How other harness-core products share the same loops

| Product | Loop A evolution target | Loop B | Reflection signals |
|---------|-------------------------|--------|--------------------|
| **PHA** | intent catalog / metric aliases / EN templates | CHB | E2E JSONL + wearable OCR mis-ledger |
| **tax_agent (local)** | form field aliases /口径 keywords | user annual fact ledger | tax-calc diff /口径 veto |
| **HIO-A (docs stage)** | device alert aliases / runbook trigger | campus asset-topology facts | alert retro JSONL → runbook PR |
| **Future ToB agent** | domain catalog JSON | tenant-level Facts | tenant stress battery |

Principle: **harness-core provides the loop skeleton (Harvest/Distill/Proposal/CI veto); products only fill Layer 1 assets and domain Critic rubrics.** The control plane (routing state machine, forbidden tools) is always human-reviewed and never auto-merged.

## 5. 90-day landing cadence

| Week | Deliverable |
|------|-------------|
| W1 | English stress JSONL → Harvest wired; RLP template bilingual inventory |
| W2 | Reflection Critic script + proposal schema selfcheck |
| W3 | Human-review merge of 1–2 EN alias PRs; Nightly hangs 10 EN sets |
| W4+ | Loop B CHB shares proposal format with tax/HIO; Weekly full 50 |

## 6. Hard constraints (re-emphasized)

- Loop **must not** auto-merge `main`  
- Loop **must not** change the Python routing state machine / global harness registry contract  
- Offline cold updates only; no online realtime weight fine-tuning  
- Stress failures go into the error book first, then Proposal — do not “fake data to pass tests”

# RFC · Stage 4 — Offline Loop Engineering (dual-loop self-evolution)

> **Language / 语言**：English (this document) · [中文](rfc-stage4-offline-loop-engineering.md)

> **Filename**: `docs/rfcs/rfc-stage4-offline-loop-engineering.md`  
> **Version**: v0.1 (2026-06-27)  
> **Status**: 📋 **Ratified (4-α.1 ✅ · 4-β-1 skeleton ✅ · 4-β-2 pending code)**  
> **Governing docs**: [`pha-pm-constitution.md`](../pha-pm-constitution.md) · [`harness-consensus-opus48-2026-06-08.md`](../harness-consensus-opus48-2026-06-08.md) · [`pha-architecture-evolution-v2.3.md`](../pha-architecture-evolution-v2.3.md) §8.2  
> **Related**: [`rfc-stage4b-personalization-flywheel.md`](rfc-stage4b-personalization-flywheel.md) · [`anti-regression-constraints.md`](anti-regression-constraints.md)

---

## 0. Execution order

Any agent coding under this RFC must, before starting:

1. Read this document + [`rfc-stage4b-personalization-flywheel.md`](rfc-stage4b-personalization-flywheel.md)  
2. First implementation reply: `CONSENSUS_ACK: rfc-stage4-offline-loop-engineering read`

**Forbidden**:

- Let Loop auto-merge into `main` (Proposal must go through a human-review PR)  
- Let Loop modify the Python routing state machine or the `harness_profile_registry.json` global contract  
- Online realtime weight fine-tuning (constitution Article 2: offline cold updates only)

---

## 1. Problem statement

PHA already has the **164/164 Bank** and **148/148 mixed-stress** immune system, but “smarter with use” still depends on humans expanding `health_intent_catalog.json` / schema `trigger_keywords`. Stage 4 goal: freeze **Telemetry → Eval → Patch → CI → Runtime** into a repeatable Loop, and **evolve recognition coverage, not control-flow topology**.

---

## 2. State-of-the-art benchmarking

| Industry pattern | Mechanism | PHA absorbs | Refuses to copy |
|------------------|-----------|-------------|-----------------|
| **OpenAI Evals + CI gate** | Dataset regression blocks release | 148/164 fixed-seed stress as Veto | Do not hand the wheel to an Eval LLM |
| **Vercel AI SDK config-as-code** | Declarative asset versioning | catalog/schema JSON Patch | Do not hot-load unreviewed Patches at runtime |
| **Anthropic Constitutional AI** | Rule-layer constrained generation | Layer 2 immune system + error book | Do not let the model change Harness Plan |
| **Netflix Chaos / Regression Tiers** | Fast + slow check layers | L1 PR · Full Nightly | Do not stuff a 70min stress into PR |

---

## 3. Three-layer constitutional gates (evolution boundary)

```text
┌─────────────────────────────────────────────────────────────┐
│  Layer 0 · Forbidden zone (never auto-Patch)                 │
│  Python state machine · TurnEvidencePlan contract · forbidden/tools │
│  numerics_audit policy · Shadow adopt · 3H structural routing rails │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 · Evolution special zone (Loop may propose)         │
│  health_intent_catalog.json · *.schema.json trigger_keywords  │
│  wearable_metric_registry intent_hints · TASK wording (via polish) │
│  【Loop B】user CHB §Facts/§Interpretation (see 4B RFC)        │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 2 · Immune system (auto Veto)                         │
│  L1 probes 18/18 · selfcheck manifest · Bank 164 · 3H 148    │
│  Stage 1E keyword-conflict detect · anti-regression-constraints.md │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Dual-loop definition

### 4.1 Loop A — global recognition loop (Stage 4-α)

**Goal**: expand all-user colloquial alias / trigger coverage.

```text
Slow-round Telemetry (JSONL)
  → Harvest: slow_round_candidates.jsonl
  → Cluster: by metric_id / intent_family
  → Distiller: proposal diff (catalog + schema ONLY)
  → 1E conflict detect
  → PR human review → merge → harness-change-log
  → Nightly 148+164 verify
```

**Evolution targets**: `metric_aliases` · `episodic_delta_followup` · `trigger_keywords`  
**Invariant targets**: Profile topology · Python `resolve_*` main paths

### 4.2 Loop B — user-value loop (Stage 4-β)

**Goal**: the better we know the user, the more targeted the answer.

See [`rfc-stage4b-personalization-flywheel.md`](rfc-stage4b-personalization-flywheel.md).

**Principle**: evolve the **user fact ledger (T0) + CHB interpretation summary (L1.5)**; **forbidden** to per-user modify `harness_profile_registry.json`.

---

## 5. CI layered gates (Phase 0 already landed)

| Layer | Trigger | Content | Duration |
|-------|---------|---------|----------|
| **PR** | `ci.yml` + `selfcheck_manifest` | Full offline selfcheck + **L1 probes** (`universal_attachment_lane_l1`) | <5 min |
| **Nightly** | `nightly-harness.yml` | 148 mixed stress + Bank 164; failures write `anti-regression-constraints.md` | ~1 h |
| **Weekly** | Human / real device | D-3d-2 E1–E8 red/green table | as needed |
| **Release** | Public Gate | 4a CI + 3d golden + Nightly 7-day all-green | — |

**Scripts**:

- PR L1: `scripts/pha_universal_attachment_lane_l1_selfcheck.py`  
- Nightly: `scripts/nightly_harness_regression.sh`  
- Error book: `scripts/pha_universal_attachment_stress_battery.py` → `docs/rfcs/anti-regression-constraints.md`
- **4-α Harvest**: `scripts/pha_telemetry_harvest.py` → `reports/loop/slow_round_candidates.jsonl`  
- **4-α Distiller**: `scripts/pha_loop_alias_distiller.py` → `reports/loop/proposals/` (`pha.loop_proposal/v2` columns)
- **1E gate**: `pha/loop_keyword_conflicts.py` · `scripts/pha_loop_keyword_conflict_selfcheck.py`
- **Tier-C containment**: `rules/loop_slot_candidates.jsonl` (forbidden to enter catalog)
- **4-β CHB**: `pha/chb_compiler.py` · [`wave4b-chronic-health-brief-spec.md`](../wave4b-chronic-health-brief-spec.md)

---

## 6. Stage 4 phases

| Phase | Deliverable | Depends |
|-------|-------------|---------|
| **4-0** | CI layers + red/green table + this RFC | ✅ 2026-06-27 |
| **4-α** | Telemetry harvest · 1E · distiller · **4-α.1** Tier columns | ✅ 2026-07-04 |
| **4-β-1** | CHB compiler skeleton + Spec v0.1 | ✅ 2026-07-04 |
| **4-β-2** | Harness slot + T0 Ingest Loop | Wave 4b · 4-β-1 |

---

## 7.1 Proposal struct (v2 · 4-α.1)

```json
{
  "schema": "pha.loop_proposal/v2",
  "accepted_catalog": [],
  "accepted_schema": [],
  "slot_candidates": [],
  "rejected": [],
  "patch_ops": []
}
```

Tier-C is **strictly forbidden** from entering `health_intent_catalog.json`; promote to `rules/loop_slot_candidates.jsonl`.

---

## 7. Acceptance criteria (4-α)

- [x] Distiller emits **only** JSON diff, no Python routing changes  
- [x] Any proposal that fails 1E → auto-discard  
- [ ] Any 148+164 failure → proposal must not promote (Nightly runs before human review)  
- [x] Error-book captures are traceable to manifest seed + trigger phrase

---

## 8. Revision history

| Date | Notes |
|------|-------|
| 2026-07-04 | 4-α.1 Tier columns · Tier-A Promote · 4-β-1 CHB skeleton |
| 2026-07-03 | Stage 4-α coding: 1E · harvest · distiller · selfcheck |
| 2026-06-27 | v0.1 first draft: dual-loop jurisprudence (Phase 0.4) |

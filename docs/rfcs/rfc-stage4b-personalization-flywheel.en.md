# RFC · Stage 4B — Personalization Flywheel

> **Language / 语言**：English (this document) · [中文](rfc-stage4b-personalization-flywheel.md)

> **Filename**: `docs/rfcs/rfc-stage4b-personalization-flywheel.md`  
> **Version**: v0.1 (2026-06-27)  
> **Status**: 📋 **Ratified (jurisprudence locked · pending Wave 4b + Stage 4-β coding)**  
> **Governing docs**: [`pha-pm-constitution.md`](../pha-pm-constitution.md) Article 3 · [`rfc-stage4-offline-loop-engineering.md`](rfc-stage4-offline-loop-engineering.md)  
> **Downstream spec (to write)**: `docs/wave4b-chronic-health-brief-spec.md` (D-4b-1)

---

## 0. Core ask

> **The better we know the user, the more valuable the answer** — but every “we get you” sentence must **trace an evidence chain**. Forbidden: an LLM slapping labels from offline guesswork.

---

## 1. Explicitly vetoed paths

| Path | Why vetoed |
|------|------------|
| Per-user rewrite of `harness_profile_registry.json` | Destroys global Profile determinism; 148/164 baseline goes out of control |
| Per-user rewrite of global `intent_hints` weights | Hidden routing fork |
| Offline LLM writing “fatty-liver trend” / “caffeine allergy” straight into the ledger | Violates constitution Article 3: inference pollutes T0 |

---

## 2. Approved path: T0 facts + L1.5 CHB columns

### 2.1 L0 · Fact sedimentation (strict T0 writes)

Ingestable facts must carry **provenance**:

| prov_type | Example | Storage |
|-----------|---------|---------|
| `lab_report` | ALT over limit two years running (ref: `lab_09`) | `medical_events` / lab rows |
| `wearable_import` | 90d HRV mean 33ms | wearable daily aggregates |
| `attachment_ingest` | 3H parse `metrics[]` high-confidence ingest proposal | proposal → human review / auto gate, then write |
| `user_statement` | User explicitly says “allergic to X” | session fact table (low confidence must be marked) |

**Forbidden**: LLM inference sentences with no ref_id entering T0.

### 2.2 L1.5 · CHB compile (Wave 4b)

An async Compiler (BYOK optional) produces a **Chronic Health Brief**. Harness **Tier1 read-only** slot `USER_CONTEXT_BRIEF`:

```markdown
## §Facts (hard facts · citable)
- LDL 2025-12-07: 2.45 mmol/L [ref: lab_2025-12-07]
- Last 90d sleep mean: 8.1h [ref: wearable_90d]

## §Interpretation (reading · not a numeric source)
- Lipids improved vs 2023; watch the long-term trend [derived_from: §Facts]

## §Open Questions
- No caffeine-sensitivity lab on file yet
```

- **§Facts** → may trigger numerics traceback  
- **§Interpretation** → must not be treated as a Manifest numeric source  
- **Physical column isolation** → prevents “blind labeling”

### 2.3 L2 · Value delivery (Harness topology unchanged)

User asks “Can I drink coffee today?”:

```text
GoalClassifier → lifestyle_advisory
existence_probe → medication/sleep facts present
Tier1 injects CHB §Facts + §Interpretation snippets
Arbiter may upgrade cabin (does not change Profile contract, only evidence assembly)
LLM, under TASK constraints, gives targeted advice with [ref:…]
numerics_audit: any concrete threshold must be traceable
```

---

## 3. Three inner cycles (inside Loop B)

| Layer | Name | Loop action |
|-------|------|-------------|
| **L0** | Ingest Loop | Harvest high-value not-yet-ingested attachment facts → proposal write |
| **L1** | Compile Loop | T0 change → trigger CHB recompile (stale hash) |
| **L2** | Eval Loop | generic answers / slow rounds → mark CHB gaps → next Compiler prioritizes §Open Questions |

---

## 4. Relation to the 3H universal fallback lane

- Attachment rounds **still stay grounded to the image** (`attachment_grounded_review` forbids warehouse)  
- **Ingest is an async side lane**: does not break 3H physical isolation  
- Ingested facts enter non-attachment rounds **next turn** via T0/CHB — not a same-turn warehouse sneak

---

## 5. Acceptance scenarios (4-β)

| Scenario | Expectation |
|----------|-------------|
| New user’s 1st open question | Reasonable generalization + prompt to add data |
| Round 20 weak “so what should I do” | episodic + CHB, not repeated popular science |
| After 3 labs, “how are my lipids” | T0 trend + CHB, not empty lifestyle |
| “Can I drink coffee” | Cite user’s meds/sleep facts + ref |

---

## 6. Phases and dependencies

| Phase | Depends on |
|-------|------------|
| Wave 4b Spec full text | doc-roadmap D-4b-1 |
| `USER_CONTEXT_BRIEF` Harness slot | 4b Spec |
| 3H → T0 Ingest proposal pipeline | 4b-α |
| Loop Compile trigger | Telemetry + T0 change events |

---

## 7. Revision history

| Date | Notes |
|------|-------|
| 2026-06-27 | v0.1 first draft: personalization-flywheel jurisprudence, attached to Stage 4 dual loops |

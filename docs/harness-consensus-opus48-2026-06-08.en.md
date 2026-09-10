# PHA Harness consensus baseline (Opus 4.8 audit alignment)

> **Language / 语言**：English (this document) · [中文](harness-consensus-opus48-2026-06-08.md)

> Status: cross-agent consensus baseline (mandatory)  
> Source: Opus 4.8 architecture review (full text provided by the user)  
> Scope: `pha/chat_service.py`, `pha/harness_*`, `pha/intent_*`, `pha/schema_*`, `pha/numerics_manifest.py`, `pha/catalog_*`, `pha/shadow_routing.py`

---

## 1. Consensus (frozen)

PHA and Claude Code are optimal harnesses for **different problem domains**:

- PHA: Harness in control, LLM as synthesizer (goal: data honesty and auditability)
- Claude Code: LLM in control, Harness as tool boundary (goal: autonomous exploration and feedback loops)

This is not a maturity ranking. It is the constraint difference between a **verifiable domain** and an **unverifiable domain**.

---

## 2. Hard constraints that must be kept (no rollback)

1. **TurnEvidencePlan before LLM**: each turn locks the profile first, then slots / forbids / tool allowlist.  
2. **Tier0 budget protection**: critical evidence (TASK, core ledger blocks) must not be tail-truncated away.  
3. **C-layer numerics audit**: personal-data numbers must be traceable to injected evidence; T0/T1 are separate domains.  
4. **Harness Veto**: LLM fetch suggestions must pass L0/L2 domain checks.  
5. **Shadow does not seize control by default**: telemetry only; it does not take over the main path.

---

## 3. Current gaps (evolution allowed)

1. Orchestration is concentrated in a giant function (`stream_pha_chat_events`); maintainability and testability are weak.  
2. Multi-step controlled reasoning is insufficient (mostly one-shot evidence → one synthesis).  
3. Extension is still mostly manual config (registry / catalog / profile changes are expensive).  
4. Routing is brittle on long-tail phrasing (keywords / lookup tables).  
5. The self-correction loop is weaker than agents in code-verifiable domains.

---

## 4. Evolution priority (consensus)

| Priority | Direction | Constraint |
|---|---|---|
| P0 | Split `stream_pha_chat_events` into a testable state machine | Do not break existing profile contracts |
| P1 | Generalize two-stage Catalog into a controlled N-step pick loop | Must keep Harness veto |
| P1 | Shadow routing for low-confidence reinforcement | Default zero-adopt, rollback-able |
| P2 | Profile/Registry generation and validation tools | Keep deterministic primary routing |
| P2 | Standardize sub-agent protocol | Must not bypass C-layer audit |

---

## 5. Forbidden

1. Do not hand the steering wheel to the LLM (health domain is not verifiable).  
2. Do not replace Tier0 budget governance with “dump a huge context”.  
3. Do not delete or weaken Numerics audit to buy surface fluency.

---

## 6. Change process (mandatory)

Any PR that touches files in scope must:

1. Explicitly declare whether the change is P0 / P1 / P2;
2. Update `docs/harness-change-log.md`;
3. Provide a rollback path;
4. Provide at least one harness regression check (self-check / script / log evidence).

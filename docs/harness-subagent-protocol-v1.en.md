# Harness Sub-Agent Protocol v1

> **Language / 语言**：English (this document) · [中文](harness-subagent-protocol-v1.md)

> **CONSENSUS_ACK**: harness-opus48-v2026-06-08  
> **Priority**: P2 · standardize sub-agent protocol  
> **Status**: Draft v1 (telemetry + validation; main path still orchestrated by Harness)

---

## 1. Purpose

Define the **controlled boundary** between PHA internal “sub-agents / tool executors” and the main Harness, ensuring:

- Sub-agents **must not** bypass TurnEvidencePlan, C-layer numerics audit, or Harness Veto
- Sub-agents **must not** emit unaudited personal health numbers directly to the user
- Main-path orchestration stays in `orchestrate_chat_turn_events` (Harness in control)

---

## 2. Roles

| Role | Duty | Seize control |
|------|------|------|
| **Harness Orchestrator** | Lock profile, slots, tool allowlist, skip_llm, final audit | Main control |
| **Catalog Fetch Agent** | Run `fetch_evidence_by_id` (N-step loop + fallback constraints) | No |
| **Tool Loop Agent** | Run tools inside the plan allowlist | No |
| **LLM Composer** | Stream synthesis from already-injected Tier0 evidence | No (synthesizer) |
| **Shadow Router** | Async semantic-comparison telemetry | No (zero-adopt) |

---

## 3. Hard constraints (no rollback)

1. **Plan before execution**: a `TurnEvidencePlan` must exist before any sub-agent call; empty `tools_allowed` forbids tool calls.
2. **Tool Veto**: only tools in `plan.tools_allowed` may run; Catalog mode is `fetch_evidence_by_id` only.
3. **SSE boundary**: sub-agents must not emit `done` / final `delta`; only Harness emits those after POST_AUDIT.
4. **Numerics audit**: personal-data numbers must be traceable via `NumericsManifest` or `CompareTable`; LLM output goes through C-layer audit or compare fallback.
5. **Shadow zero-adopt**: Shadow results write `shadow_routing` telemetry only; they must not rewrite plan / profile / answer.

---

## 4. Allowed event surface (sub-agent → Harness)

| event | Sub-agent may produce | Harness may forward to user |
|-------|----------------|---------------------|
| `status` | ✅ (progress / pick) | ✅ |
| `audit` | ❌ | Harness only |
| `delta` | ❌ (except Composer) | Harness only |
| `done` | ❌ | Harness only |
| `meta` / `fact_card` / `follow_ups` | Composer path only | Harness only |

---

## 5. Catalog N-step pick loop

- Max rounds: `PHA_CATALOG_MAX_FETCH_ROUNDS` (default 3)
- Each round is `fetch_evidence_by_id` only
- If `all_required_ready` is incomplete → Harness `catalog_partial_fill` fallback
- If the model picked nothing → Harness `infer_auto_tool_fallback` or `DEFAULT_COMBINED_FETCH_IDS`

---

## 6. Rollback

- Disable sub-agent boundary checks: `PHA_HARNESS_SUBAGENT_PROTOCOL=0`
- Restore single-round Catalog: `PHA_CATALOG_MAX_FETCH_ROUNDS=1`

---

## 7. Acceptance

- `scripts/pha_harness_subagent_protocol_selfcheck.py`
- `pha/harness_profile_registry.py` plan-contract checks
- E2E: `combined_review` + `wearable_only` routing probes

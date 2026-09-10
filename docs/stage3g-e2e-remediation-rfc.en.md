# Stage 3G — E2E spoken-storm remediation RFC

> **Language / 语言**：English (this document) · [中文](stage3g-e2e-remediation-rfc.md)

> **Version**: v0.3 (2026-06-26)  
> **Status**: Implemented (P0/P1/P1b/P2 coded and accepted)  
> **Upstream**: [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.en.md)  
> **Evidence**: Baseline fixed 20× **70/70** (`20260625T101854Z`) · Bank seed=20260626 **164/164** (`20260626T033611Z`) · pre-P2 **155/164** (`20260625T142957Z`)

---

## 1. Problem statement

| ID | Symptom | Root cause |
|----|------|------|
| **E2E-DELTA-01** | S04/QS04 “vs last week?” `delta_focus_missing` | `chat_skip_llm` weak-followup block ran **before** `build_episodic_delta_focus_answer` |
| **E2E-ALIAS-01** | Spoken metric variants `reintroduced_full_table_on_followup` | `infer_single_metric_focus_ids` empty set → LLM full table |
| **E2E-WARE-01** | Warehouse “is HRV normal?” slow path | schema/catalog did not cover spoken **心率变异** (without 性) |

## 2. Non-goals

- ❌ Add phrase if-else inside `infer_wearable_metrics` / orchestrator
- ❌ Let Reflection LLM freely rewrite user-visible numbers
- ❌ Raise the Tier0 cap to pass E2E

## 3. Fix spec

### 3.1 P0 — Skip control flow

In the screenshot-session branch of `evaluate_skip_llm_path`:

```text
correction → first_upload → episodic_delta → weak_followup → single_metric → …
```

### 3.2 P1 — Catalog coverage

`health_intent_catalog.json` v1.4:

- `episodic_delta_followup.tokens` — mutually exclusive with weak followup
- Expand `metric_aliases`: hrv / ldl / rhr / respiratory_rate / spo2

`wearable_bundle.schema.json` + `wearable_metric_registry.json` `intent_hints` sync spoken variants (declarative, not Python).

### 3.3 P1b — Weak-followup exclusion

`is_weak_episodic_followup` before close/advisory/anaphora:

```python
if is_episodic_delta_followup_message(msg):
    return False
```

## 4. Acceptance

| Check | Expect | Result |
|------|------|------|
| Baseline S04 T4 | PASS | **PASS** (0.2s delta skip) |
| Bank QS04 T4 | PASS | **PASS** (delta fix live) |
| `pha_chat_turn_fsm_selfcheck` delta-before-weak | PASS | **PASS** |
| `pha_health_intent_catalog_selfcheck` delta tokens | PASS | **PASS** |
| Baseline fixed 20× | 70/70 | **70/70** |
| Bank seed=20260626 | ≥162/164 | **164/164** (P2 wrap-up, `20260626T033611Z`) |

## 5. P2 wrap-up (2026-06-26)

| Cluster | Fix |
|------|------|
| alias miss (5) | Narrow hint first + paired workout focus + tighten `指标` regex + registry hint |
| Warehouse weak-sentence slow turns (3) | schema `trigger_keywords`: `睡得好`/`走路` → single-metric warehouse focus skip |
| Deep-sleep slow turn (1) | Paired deep-sleep focus exception (`sleep_deep`+`sleep_rem`) |

## 6. Reflection (docs layer)

See [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) §8.1 — R0/R1 already exist; R2 Shadow remains Backlog.

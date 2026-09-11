# Stage 3F — Intent-resolution completeness RFC

> **Language / 语言**：English (this document) · [中文](stage3f-intent-resolution-completeness-rfc.md)

> **Filename**: `stage3f-intent-resolution-completeness-rfc.md`  
> **Version**: v0.1 (2026-06-17)  
> **Status**: ✅ **Approved · architectural-completeness locked edition** · §15 is a v1.14 addendum (M1-P17 / P18 already coded)  
> **Positioning**: the **unified product-development wave** after Stage 3C (multi-turn coherence) — complete the “open intent → evidence assembly” path; **not** a single E2E / single-metric corner-case patch  
> **Upstream (read-only)**: [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) · [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · [`pha-pm-constitution.md`](pha-pm-constitution.md)  
> **Downstream coding**: `health_turn_resolver` · `intent_gates` · `harness_plan` · `health_intent_catalog` · `clarify_turns` · `harness_report`

---

## 0. Execution order and consensus bind

Any agent coding under this RFC must, before starting:

1. Read this document in full + [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) §2 constitution alignment  
2. Read [`docs/pha-pm-constitution.md`](pha-pm-constitution.md) Articles 1–3  
3. First implementation reply contains: `CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read`

**Forbidden**:

- Adding a phrase if-else in Python to pass a single real-device script (incl. “body age” class synthetic questions)  
- Letting a sub-agent / Shadow / LLM directly choose `TurnEvidencePlan` or bypass Numerics audit  
- Using “raise the Tier0 cap” as the only fix for open intent  

**Telemetry-driven statement** (constitution Article 2): this RFC’s project basis is the repeatedly appearing Harness-telemetry pattern **`profile=lifestyle` + `manifest_n=0` + user then unlocking one metric per turn** (see [`telemetry-review-playbook.md`](telemetry-review-playbook.md) §4 extension). It is a **routing-completeness gap**, not that some metric’s SQL cannot be read.

---

## 1. Problem statement (architectural completeness)

### 1.1 Already delivered (Stage 3C-α～ε)

| Capability | Status | Coverage |
|------------|--------|----------|
| `HealthTurnResolver` + `turnScope` | ✅ | Metric / year / window / anaphora continue-focus |
| All-profile episodic + `EPISODIC_BRIDGE` | ✅ | In-session **profile-lane** continue-focus |
| `health_intent_catalog` declarative inherit | ✅ | Weak questions, `session_anchor` |
| `clarify` short-circuit + chips | ✅ | **`lab_year`** and other lab ambiguity |
| `GroundedAnswerComposer` + fact_card | ✅ | Narrative layer isomorphic with Manifest |

### 1.2 Still-missing architecture blocks (completeness gap)

PHA’s current pipeline has a systematic blank when **“the user goal is expressed, the evidence domain is not named”**:

```text
User sentence (open synthetic goal, no concrete metric token)
  → SchemaIntentRouter: lab/wearable/supplement scores all 0
  → Default lifestyle (lightest lane)
  → Tier0 ≈ TASK only; Manifest / 90d / tools off
  → LLM under Soul contract outputs “lack baseline / please provide a report”
  → User is forced to name metrics one by one; each turn unlocks only a single-domain Manifest
  → episodic continues focus_profile (single lane), cannot rebuild a multi-domain joint view
```

This is not a bug in one feature; the **intent-resolution stack lacks three orthogonal dimensions**:

| Dimension | 3C already covers | 3F must complete |
|-----------|-------------------|------------------|
| **Scope** (which year / window / metric) | ✅ Resolver | Continue |
| **Profile** (which Harness lane) | ✅ SchemaRouter | Need **Arbiter** to upgrade cabin when under-specified |
| **Goal** (synthetic goal vs single-metric query) | ❌ | Need **GoalClassifier** + **focus_goal** |

### 1.3 What this RFC must answer

Without breaking the **A+ constitution** and the **Approved 3C RFC**, form a **Stage 3F unified product-development arrangement**, so PHA has a declarable, observable, regressable complete path for “infinite phrasings, finite assembly modes”.

### 1.4 Non-goals

- ❌ Separate Python branches for “body age”, “anti-aging”, etc.  
- ❌ LLM-mastered ReAct autonomously pulling data  
- ❌ Cross-session long-term user portrait (still a later Backlog)  
- ❌ Changing the Numerics audit algorithm body  
- ❌ Rewriting the full Soul Prompt inside this RFC (only declare **goal-aware narrative-contract** principles)

---

## 2. Relation to existing docs

```text
pha-pm-constitution.md          Governing law
harness-consensus-opus48          Hard constraints + P0/P1/P2
stage3c-multi-turn-episodic-focus-rfc   Multi-turn scope / episodic / clarify(lab_year)
stage3f-intent-resolution-completeness  ← this RFC: goal + arbiter + multi-domain assembly completeness
pha-architecture-evolution-v2.3   Stage 1～3C master blueprint; 3F writes into §8 roadmap
metadata-catalog-v2.3             existence_probe reuse, do not create a second probe
harness-subagent-protocol-v1      Intent Scout boundary
```

**3C is not repealed**: 3F **adds modules and catalog fields** on top of 3C; `HealthTurnResolver` still **does not choose the final profile** (continue §6.1 duties).

---

## 3. Non-negotiable constitution alignment

Same as [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) §2, plus:

| Constraint | 3F stance |
|------------|-----------|
| TurnEvidencePlan before LLM | Catalog / tools / LLM only after Arbiter emits the plan |
| Harness Veto | `forbidden` / Manifest domain checks unchanged |
| Shadow zero-adopt | Intent Scout only proposes + telemetry |
| Data > Context | Upgrade to `combined_review` still forbids silent full `SUPPLEMENT_BG` |
| P0 explicit > P2 episodic | User chip / explicit metric overrides `focus_goal` |
| Constitution Article 3 | 1.5B only produces **strategy enums** (`goal_class` / `suggested_domains`), does not write assertion body |

---

## 4. Full pipeline (Stage 3F target state)

```text
User sentence (+ clarify_choice_id if any)
  │
  ├─► HealthTurnResolver          # scope: metric / year / window / clarify trigger
  │       HealthTurnScope
  │
  ├─► GoalClassifier (C layer · new)    # goal_class: metric_specific | holistic | casual | clarify_pending
  │       In: user sentence + catalog.goal_markers + turn_scope
  │       Out: goal_class, goal_confidence (deterministic first)
  │
  ├─► SchemaIntentRouter          # asset-domain scores → router_profile candidate
  │
  ├─► Harness Arbiter (C layer · new)   # unique authoritative profile synthesis point
  │       In: goal_class + router_profile + turn_scope + existence_probe + episodic.focus_goal
  │       Out: authoritative_profile, arbiter_reason (enum)
  │
  ├─► TurnEvidencePlan            # slots / forbidden / tools_allowed
  ├─► Tier0 assembly + Catalog N-step order
  ├─► LLM Composer (narrative only)
  └─► numerics_manifest audit + Harness Veto
        │
        └── [async] Intent Scout → shadow_routing (zero-adopt)
```

**Key invariant**: Profile **locks only after Harness Arbiter**; Catalog render is still after Profile.

---

## 5. Core module design

### 5.1 GoalClassifier (C layer · declarative)

**Duty**: judge this turn’s **goal type**; does not choose profile, does not pull evidence.

**Output**:

```text
GoalClassification:
  goal_class: metric_specific | holistic_assessment | casual | clarify_pending
  confidence: float          # rule hit = 1.0; Shadow supplement < 1.0
  source: catalog | explicit_metric | shadow_suggest
```

**Rules (written into `health_intent_catalog.json`, forbid Python hardcoded tables)**:

```json
"goal_markers": {
  "holistic_assessment": {
    "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康"],
    "anti_tokens": [],
    "notes": "synthetic health goal; not a metric proper noun"
  },
  "metric_specific": {
    "inherit_from": "metric_aliases",
    "notes": "prefer when the user sentence contains a parseable metric token"
  }
}
```

**Priority**:

1. Explicit metric token → `metric_specific`  
2. `goal_markers.holistic_assessment` hit and no explicit metric → `holistic_assessment`  
3. Greeting / extremely short weak sentence → `casual` (reuse existing gates)  
4. Undecidable and probe multi-domain → `clarify_pending`

### 5.2 Harness Arbiter (C layer · deterministic)

**Duty**: synthesize **authoritative_profile**; analogous to tax-side “clarify vs execute” branch, but the **health domain stays deterministic**.

**Inputs**: `GoalClassification` + `SchemaIntentRouter` candidate + `HealthTurnScope` + `existence_probe(user_id)` + `session_turn_focus.focus_goal`

**Core strategy table**:

| goal_class | existence_probe | Arbiter behavior | authoritative_profile |
|------------|-----------------|------------------|------------------------|
| `holistic_assessment` | lab ✓ and wearable ✓ | Auto upgrade | `combined_review` |
| `holistic_assessment` | lab ✓ only | clarify `intent_scope` | `clarify` |
| `holistic_assessment` | wearable ✓ only | clarify `intent_scope` | `clarify` |
| `holistic_assessment` | both ✗ | clarify `data_gap` | `clarify` |
| `metric_specific` | — | Reuse SchemaRouter | router_profile |
| `casual` | — | Reuse SchemaRouter | router_profile |
| episodic `focus_goal=holistic` + weak question | lab ✓ and wearable ✓ | Continue goal, upgrade | `combined_review` |

**`arbiter_reason` enum** (written into harness report, for telemetry):

`schema_default` · `goal_holistic_upgrade` · `goal_clarify_scope` · `goal_clarify_data_gap` · `episodic_goal_continue` · `explicit_metric_override` · `session_anchor`

**With existence_probe**: reuse [`catalog_existence.py`](../pha/catalog_existence.py) / [`metadata-catalog-v2.3.md`](metadata-catalog-v2.3.md) existing probes; **do not create** a parallel probe API.

**holistic proxy metric set**: declared by catalog `holistic_proxy_metrics` (e.g. LDL, HRV, steps, vo2max), for Manifest and TASK template citation — **not** a “body age” hardcoded row.

### 5.3 Clarify contract extension (natural extension of 3C §6.4)

On the already-landed `PHA_CLARIFY_TURNS=1` base, extend `clarify_kind`:

| clarify_kind | Trigger | choices example | After user chooses |
|--------------|---------|-----------------|--------------------|
| `lab_year` (existing) | Multi-year lab weak question | 2023 / 2025 | explicit year scope |
| **`intent_scope` (new)** | holistic + single-domain probe | lab+wearable / lab only / wearable only | explicit domains → Arbiter upgrade |
| **`data_gap` (new)** | holistic + domain missing | Explain missing domain + guide upload (deterministic copy) | Do not enter LLM invention |

**Principles** (continue 3C §6.4):

- Clarify turns short-circuit LLM; `forbidden` bans Patient State full table  
- Chip choice = P0 explicit, overrides episodic  
- Clarify turns do not write `focus_goal=holistic` (write after user confirms)

### 5.4 Goal Session Anchor (Episodic second dimension)

Extend `session_turn_focus` (design fields, coded in 3F-β):

```text
focus_goal: holistic_assessment | metric_specific | null
focus_domains: ["lab", "wearable"]   # written after user chip or Arbiter upgrade
```

**Continue-focus rules**:

- Weak question (catalog `weak_followup`) + `focus_goal=holistic_assessment` → Arbiter **must** try `combined_review`, **must not** only continue `wearable_only` / `lab_cross_year` single lane  
- User explicit new metric (P0) → park or downgrade `focus_goal`  
- TTL / refresh rules same as 3C §6.2

### 5.5 Intent Scout (Shadow · P1)

**Duty**: async semantic proposal, **zero-adopt**.

**Output** (telemetry / optional status hint only):

```json
{
  "goal_class": "holistic_assessment",
  "suggested_domains": ["lab", "wearable"],
  "confidence": 0.88
}
```

**Adopt boundary**:

- Default: **does not** change Arbiter output  
- Only when authoritative=`lifestyle` and shadow=`holistic_assessment` and confidence≥`PHA_SHADOW_CONFIDENCE_THRESHOLD`, may emit a **non-blocking status**: “是否基于化验与穿戴综合评估？” → still requires chip or next-turn explicit  

Flag: `PHA_SHADOW_ROUTING=1` (reuse v2.3 Stage 2D, extend shadow fields)

### 5.6 Soul / Composer contract (principle layer)

When `authoritative_profile=combined_review` and Manifest already contains `holistic_proxy_metrics`:

- Allowed to do synthetic narrative based on **Manifest KV proxy metrics**  
- Must declare “non-standard clinical metric / proxy estimate”  
- **Forbidden** to output “please upload a report” instead of clarify when Manifest is empty (clarify should already have intercepted)

Concrete Prompt diffs are a separate PR; this RFC only locks the **behavior contract**.

---

## 6. Declarative Catalog extension (design draft · write JSON at coding time)

The following fragment is the **3F-γ target state**; coding PRs must update [`rules/health_intent_catalog.json`](../rules/health_intent_catalog.json) and have registry selfcheck validate.

```json
{
  "version": "1.2",
  "goal_markers": {
    "holistic_assessment": {
      "tokens": ["综合", "整体", "评估", "各项指标", "全面", "大健康", "身体年龄"],
      "priority": 10
    }
  },
  "holistic_proxy_metrics": ["ldl", "hdl", "hrv", "steps", "vo2max", "resting_hr"],
  "clarify_kinds": {
    "intent_scope": {
      "prompt_template": "您希望基于库内哪些数据做综合评估？",
      "choices": [
        {"id": "lab_wearable", "label": "化验 + 穿戴", "domains": ["lab", "wearable"]},
        {"id": "lab_only", "label": "仅化验档案", "domains": ["lab"]},
        {"id": "wearable_only", "label": "仅穿戴近90天", "domains": ["wearable"]}
      ]
    }
  }
}
```

**Maintenance rule**: new synthetic-goal phrasings → change `goal_markers` + golden cases + telemetry clustering; **forbid** changing Python phrase tables.

---

## 7. Harness observability extension

Extend [`harness_report`](../pha/harness_report.py) (suggest schema bump **v1.3**, keep old fields):

```json
{
  "goalClass": "holistic_assessment",
  "goalSource": "catalog",
  "arbiterDecision": {
    "authoritative_profile": "combined_review",
    "router_profile": "lifestyle",
    "reason": "goal_holistic_upgrade",
    "existence_probe": {"lab": true, "wearable": true}
  },
  "turnScope": { "...": "same as 3C" },
  "episodic": { "focusGoal": "holistic_assessment", "focusDomains": ["lab", "wearable"] }
}
```

**Ops use** ([`telemetry-review-playbook.md`](telemetry-review-playbook.md) §4 pending add):

- `router_profile=lifestyle` and `reason=goal_holistic_upgrade` → upgrade succeeded  
- `router_profile=lifestyle` and `goalClass=holistic` and profile still lifestyle → **architecture regression**  
- Shadow vs authoritative divergence rate → Stage 4 offline distill input

---

## 8. Golden cases (H5–H8)

Into `scripts/pha_health_turn_resolver_selfcheck.py` (from 3F-α) and register `selfcheck_manifest.json`.

| ID | Scenario | User sentence sequence | Assert |
|----|----------|------------------------|--------|
| **H5** | Open synthetic first turn | DB has lab+wearable; 「根据各项指标综合评估健康状态」 | `goal_class=holistic`; `profile=combined_review` or `clarify intent_scope`; **not** lifestyle |
| **H6** | Goal continue-focus | After H5, weak 「那结论呢」 | `focus_goal` continues; `profile=combined_review`; metric single-domain episodic does not override goal |
| **H7** | P0 explicit override | After H5, 「只看 LDL」 | `goal` downgrades; `profile=lab_cross_year`; `metric=ldl` |
| **H8** | Single-domain probe | Wearable DB only; holistic sentence | `clarify_kind=intent_scope`; choices include 「仅穿戴」 |

**E2E (human / real device, not CI-blocking)**: any under-specified synthetic question + subsequent single-metric unlock script — for telemetry contrast, **not** a single-phrase acceptance standard.

---

## 9. Phased implementation and Feature Flag

| Phase | Content | Flag | Depends |
|-------|---------|------|---------|
| **3F-α** | `GoalClassifier` + `Harness Arbiter` + harness `goalClass`/`arbiterDecision` + H5–H8 | `PHA_GOAL_CLASSIFIER=1` | 3C-γ catalog | ✅ coded |
| **3F-β** | `focus_goal` / `focus_domains` episodic + H6/H7 | `PHA_GOAL_SESSION_ANCHOR=1` | 3F-α | ✅ coded |
| **3F-γ** | catalog `goal_markers` + `holistic_proxy_metrics` + clarify `intent_scope`/`data_gap` + H8 | `PHA_CLARIFY_INTENT_SCOPE=1` | 3F-α, 3C-δ | ✅ coded |
| **3F-δ** | Intent Scout shadow fields + telemetry playbook §4 | `PHA_SHADOW_ROUTING=1` | 3F-α | ✅ coded |

**Rollback**: each flag independently defaults `0`; after off, revert to 3C-ε behavior.

**Map to consensus P0/P1/P2**:

| Consensus priority | 3F mapping |
|--------------------|------------|
| P0 | Arbiter + orchestrator join point; harness report fields |
| P1 | Intent Scout shadow; Catalog N-step order inside combined |
| P2 | catalog extension + registry validate + telemetry clustering |

---

## 10. § SOTA industry-pattern comparison

| Industry pattern | PHA 3F adopts | Deliberately does not adopt |
|------------------|---------------|-----------------------------|
| OpenAI Tool Use routing | C-layer Arbiter sets plan then allowlist tools | LLM self-chooses tool sequence |
| Claude Code autonomous explore | Intent Scout async proposal | LLM-mastered loop |
| ReAct multi-step reasoning | Catalog **controlled** N-step order (existing) | Unbounded ReAct |
| RAG wide retrieve | existence_probe **narrow-domain** upgrade | Full-DB embedding retrieve replacing plan |
| Tax `TaxTurnResolver` + clarify | HealthTurnScope + clarify chips | Cross-domain import |

---

## 11. Acceptance

### 11.1 Automatic

- [x] `bash scripts/run_selfchecks.sh` all green (incl. H5–H8, H-δ8/δ9, stage3f_delta)  
- [x] `generate --check` profile registry consistent with catalog  
- [x] `router_profile=lifestyle` + holistic sentence → authoritative ≠ lifestyle (when probe dual-domain)

### 11.2 Compliance

- [x] No LLM takeover; Shadow zero-adopt  
- [x] numerics no new `unauthorized_value` regression (body-age E2E P2 SSE hard assert)  
- [x] No single E2E phrase hardcoding (routing/goal via catalog + Arbiter)

### 11.3 Docs

- [x] This RFC status → **Implemented** (2026-06-24)  
- [x] `harness-change-log.md` + `startup-change-log.md` synced

---

## 12. Risks and mitigations

| Risk | Level | Mitigation |
|------|-------|------------|
| holistic over-trigger → combined volume swell | Medium | existence_probe gate + Tier0 Protected SLA |
| Too much clarify | Low | Only under-specified + multi-domain/missing-domain; single metric no clarify |
| Dual-source profile from Arbiter and Resolver | High | **Unique** authoritative exit = Arbiter |
| goal_markers maintenance entropy | Medium | telemetry clustering + offline distill (Stage 4) |

---

## 13. Docs and change register

| Document | Content |
|----------|---------|
| `docs/stage3c-multi-turn-episodic-focus-rfc.md` | §15 handoff pointer |
| `docs/pha-architecture-evolution-v2.3.md` | §8 Stage 3F roadmap |
| `docs/telemetry-review-playbook.md` | §4 goal/arbiter fields |
| `docs/harness-change-log.md` | 3F phase entries |
| `docs/startup-change-log.md` | flags and acceptance |
| `AGENTS.md` / `pha-mandatory-reads.mdc` | Index update |

---

## 14. Appendix: observability samples (not a requirements source)

The following conversation patterns are for **telemetry clustering labels**, **not** single-point requirements of this RFC:

1. Open synthetic question → lifestyle / manifest_n=0  
2. User names metrics one by one → single-domain profile rotation  
3. Explicit VO2 / wearable words → wearable manifest improves  
4. Same sentence multi-metric → `combined_review` gold path  

That sample proves an **assembly-completeness** gap; the fix path is **§5 all modules**, not adding a rule for one phrasing in the sample.

---

## 15. v1.14 addendum (Approved · docs locked · not coded)

> 2026-09-09 maintainer agreed audit: must not scan the whole card for “overall + focus on”; must not flip Data > Context with drug phrases; must not pull historical plans by note length. Must-read before coding [`handoff-2026-09-09-outline-and-context-lookup.md`](handoff-2026-09-09-outline-and-context-lookup.md). **Does not repeal** §5.1 existing priority (explicit metric → `metric_specific`) and H7 “只看 LDL”; the following are **additive** modules and strategy rows.

### 15.1 `outline_mode` (interpret / `daily_readiness` narrative contract)

Does not choose profile. Written into `health_intent_catalog.json` `assessment_outline`:

| mode | Markers (catalog tokens, freeze at coding) | Narrative |
|------|--------------------------------------------|-----------|
| `exclusive` | 只看 / 仅 / only look at | P9.5b: talk only about named rows |
| `emphasis` | 重点看 / 侧重 / especially | Named first; other checked valued rows may ride in the same paragraph, forbid a separate topic section. **v1.15**: English TASK sentence 1 = overall (no metric label); `exclusive` must not require an overall opening |
| `cover-card` | Neither of the above | Cover checked valued rows |

Priority **exclusive > emphasis > cover-card**. `daily_readiness` must not default exclusive. Python does not parse metric ids in the assessment request. Must not turn emphasis into cover-card (valued rows must be hit); must not miss a row then run another LLM round.

### 15.2 `goal_class=context_lookup`

Add to GoalClassifier output enum. Rules written into `goal_markers.context_lookup` (forbid Python drug-name/question tables). existence = notes probe, not wearable.

**Arbiter strategy rows (additive, do not change Data > Context):**

| goal_class | Other | Behavior | authoritative_profile | arbiter_reason |
|------------|-------|----------|------------------------|----------------|
| `context_lookup` and no explicit metric | notes ✓/✗ neither upgrades combined | Existing lifestyle / context_only | `lifestyle` | `goal_context_lookup` |
| `context_lookup` and explicit metric | — | **No** warehouse skip-LLM; numbers go named metric; background only brief slice | router_profile (usually `wearable_only`) | `explicit_metric_with_context_lookup` |
| Pure metric_specific (e.g. 90d HRV trend) | — | Unchanged | router_profile | `schema_default` |

Upgrade `combined_review` still forbids silent full `SUPPLEMENT_BG`. `fact_card` ⊆ `turn_scope.metric_keys`; empty → no card. **v1.15**: `wearable_daily_review`, when FACT_CARD_CONTEXT already present, SSE ⊆ that card’s metric rows (incl. legal cluster expand); training words do not stuff `workout_*` into scope.

### 15.3 Capture

`supplement_bg` schema: interrogative/imperative in `background_capture_keywords` are negative. Independent of lane (continue 3F capture ≠ route).

### 15.4 Non-goals (this addendum)

- Python equals for a single golden sentence  
- Opening CHB / P15 early  
- A new profile only to serve “did I take my meds”  
- Flipping the *Data beats Context* scoring order  

Coding map: consensus P1 (catalog + Arbiter rows + plan card-issue filter); flags see handoff §3.

---

## 16. v1.15 addendum (Approved · eval-audit landing)

> 2026-09-10 maintainer authorized: start after rewriting 40+40 three plans per consensus. Source of truth [`handoff-2026-09-10-eval-audit-solution.md`](handoff-2026-09-10-eval-audit-solution.md). **Does not repeal** §15.

| Item | Do | Don’t |
|---|---|---|
| Tier0 | Existing on-card row KV / Manifest must not tail-truncate; over limit, compress FACT_CARD_CONTEXT advice first | Raising global 4500 as the only fix; `_cap_system_content` chopping T0 |
| TASK | emphasis Sentence 1 = overall | exclusive overall opening; golden-one-sentence Python if |
| Card issue | SSE ⊆ FACT_CARD_CONTEXT metric rows | prefs ∩ cutting cluster expand; must-cover; miss-row retry |

Coding map: consensus P1; card **M1-P19**.

---

## 17. v1.16 addendum (Approved · exclusive inject + rule layer as source of truth + P15)

> 2026-09-10 maintainer order: start in 1–5 sequence; item 4 (change model) not done. Source of truth PRD v1.16. **Does not repeal** §15 / §16.

| Item | Do | Don’t |
|---|---|---|
| exclusive inject | exclusive interpret turns only: `FACT_CARD_CONTEXT` + Manifest ⊆ catalog `infer_wearable_metric_ids`; visible HTML card still whole card; empty → fail-closed | Scan whole card; new Python assessment-request parser; emphasis/cover cut card; must-cover |
| Opening / training | Rule-layer summary/advice as source of truth; P19 Sentence 1 add no words; gold via telemetry | Python if for a golden sentence; generate “can strength-train” by band |
| brief read side | Same `background_capture_negative_keywords` as capture before quota | Prefer long notes; runtime LLM self-heal |
| P15 CHB | §Background + lineage; combo hash; GET fact-card background once same day; interpret projection no §Facts | Add `fact_card_interpret` to `USER_CONTEXT_BRIEF_PROFILES`; brief numbers into Manifest |

Coding map: consensus P1; cards **M1-P20** / **M1-P15**. Flags: `PHA_EXCLUSIVE_INJECT_NAMED`, `PHA_CHB_AUTOCOMPILE` (both default 1).

---

## 18. v1.18 addendum (Approved · CHB self-statement rows + USER_CONTEXT_BRIEF project §Background)

> 2026-09-10 maintainer chose cut 2. Source of truth PRD v1.18. **Does not repeal** §15–§17.

| Item | Do | Don’t |
|---|---|---|
| Compile | notes → `background_rows[]`: `category` + de-numbered short sentence + relative time + `prov_type=user_statement`; time-of-day split rows reuse copy vocab | Drug/supplement-name Python tables; self-statement into §Facts / Manifest |
| Chat project | `USER_CONTEXT_BRIEF` (lifestyle / combined) must carry §Background | Interpret turns add `USER_CONTEXT_BRIEF`; add `fact_card_interpret` to `USER_CONTEXT_BRIEF_PROFILES` |
| Interpret | Same row set via existing `USER_BACKGROUND_BRIEF` | Change TASK item 5; “named training then supplement-related” |

---

## 19. v1.19 addendum (Approved · TASK slot contract: no invented numbers + present brief must not skip)

> 2026-09-10 gold-sentence audit fused 21.5/85/95. Maintainer adopted a generic slot contract. **Does not repeal** §15–§18. Numeric truth remains Manifest / FACT_CARD_CONTEXT, not CHB §Facts.

| Item | Do | Don’t |
|---|---|---|
| No invented numbers | TASK forbids inventing or deriving extra numbers/percents (including 100 minus a percentile); without a Manifest token use qualitative wording only; drop population examples that bait `95%` | Weaken Numerics; brief digits into Manifest |
| Background slot | Present brief is in-scope; do not skip the slot; drop “ignore if unrelated”; fold into advice sentences; no numbered precautions list; weak causal: forbid causes / leads to | “Named training ⇒ supplement-related”; drug-name table; add interpret to `USER_CONTEXT_BRIEF`; mandatory 注意事项 section |

Coding map: consensus P1; card **M1-P15** → DONE (PRD v1.22; deferred items open later).

---

## 20. v1.20 addendum (Approved · lineage drops metric-field stubs)

> 2026-09-10. Source of truth PRD v1.20. **Does not repeal** §15–§19.

| Item | Do | Don’t |
|---|---|---|
| Lineage | Keep only recurring caution sentences; drop de-numbered today-value / percentile / window-mean stub rows; if empty do not inject | Weaken audit; drug-name table; strip card percentiles from injection (rule layer still bands on percentiles) |

---

**Stage 3F · v0.1 Approved (2026-06-17)** — **status: Implemented (2026-06-24)** — **3F-α ✅ · 3F-β ✅ · 3F-γ ✅ · 3F-δ ✅** coded; P2 combined_review SSE hard assert wired into E2E.

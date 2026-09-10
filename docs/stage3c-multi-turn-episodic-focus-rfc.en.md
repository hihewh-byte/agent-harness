# Stage 3C — Multi-turn conversation coherence RFC

> **Language / 语言**：English (this document) · [中文](stage3c-multi-turn-episodic-focus-rfc.md)

> **Filename**: `stage3c-multi-turn-episodic-focus-rfc.md`  
> **Version**: v0.1 (2026-06-10)  
> **Status**: ✅ **Approved · architect-locked edition (2026-06-10)**  
> **Claimed task**: Stage 3C multi-turn coherence (after `stability-remediation-plan` P1, does not block P0 import/keepalive)  
> **Upstream refs (read-only borrow, bidirectional import forbidden)**: `tax_agent` v1.6–v1.9 multi-turn architecture, `tax-chat-experience-v2.md` (GroundedAnswerComposer / SSE fact-card)  
> **PHA depends**: [`stage3a2-episodic-focus-and-grounded-rationale.md`](stage3a2-episodic-focus-and-grounded-rationale.md) · [`stage3c-episodic-evidence-bridge.md`](stage3c-episodic-evidence-bridge.md) · [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.md) · [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) · [`manifest-tier-v1.md`](manifest-tier-v1.md)

---

## 0. Execution order and consensus bind

Any agent coding under this RFC must, before starting:

1. Read this document in full + `docs/stability-remediation-plan-2026-06-10.md` §6 behavior red lines  
2. First implementation reply contains: `CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read`  
3. Same PR updates `docs/startup-change-log.md` (if touching `chat_service` / `harness_plan` / startup path)

**Forbidden**: import any module from the `tax_agent` package; forbidden to hardcode tax-domain entities (`tax_year`, `FxRate`, etc.) into PHA routing.

---

## 1. Problem statement

### 1.1 User-visible symptoms

| Symptom | Typical repro |
|---------|---------------|
| Round 2 becomes a “plan laundry list” | Attachment round R1 good → R2 “why does it help” drops to `lifestyle` + full `SUPPLEMENT_BG` |
| Metric follow-up drops | R1 “我 HRV 怎么样” → R2 “那上个月呢” treated as a new topic, window reset |
| Cross-year reconcile drift | R1 “2024 年 LDL” → R2 “前年呢” does not inherit lab-year scope |
| Silent wrong guess | Multi-year labs in DB + user only asks “血脂怎么样” → model self-picks year, no clarify |
| Changed it, don’t know if it’s fixed | No production-grade **multi-turn golden cases**; single-turn selfcheck green but real-device three turns still crash |

### 1.2 Root cause (architecture layer)

PHA Stage 3A.2 already introduced **Layer 2.5 session episodic focus**, but the implementation scope is too narrow:

| Dimension | PHA current (3A.2) | tax_agent proven (v1.6–1.9) | Gap |
|-----------|--------------------|-----------------------------|-----|
| Episodic coverage | Only `attachment_asset_qa` profile; TTL=3 | **All profiles** write episodic (incl. fast lane); TTL=8; same-topic follow-up refresh | **High** |
| Entity/scope resolve | Scattered in `intent_gates` / `temporal_router` / `chat_service` conditions | `TaxTurnResolver` unified `turnScope` (year + source + revived) | **High** |
| Intent routing | A+ `SchemaIntentRouter` exists, but episodic **does not participate** in profile inherit | `tax_intent_catalog.yaml`: `episodic_continue` + scorer | **High** |
| Ambiguity handling | No `clarify` contract | `action=clarify` + chips | **Medium** |
| Observability | Harness has no `turnScope` | `harnessReport.turnScope.{taxYears,yearSource,episodicRevived}` | **Medium** |
| Multi-turn regression | Mostly single-turn | M1–M4 golden multi-turn in production selfcheck | **High** |
| Response UX | LLM emits Markdown directly | v2: `FactBundle` → `GroundedAnswerComposer` + `followUps` + SSE `fact_card` first | **Medium** (isomorphic with numerics) |

**Conclusion**: PHA “round 2 becomes a laundry list” is primarily because **episodic only covers attachment turns**; wearable/lab/combined-review fast lanes consume focus then never write back, so the next turn loses focus. Secondary: **no unified TurnResolver**, so anaphora continue-focus logic cannot be reused across profiles.

### 1.3 What this RFC must answer

Without breaking PHA **A+ constitution** and **P0–P4 conflict priority**, **conceptually re-infuse** tax_agent multi-turn experience as PHA-native design, forming a Stage 3C roadmap that can be coded in phases.

---

## 2. Non-negotiable constitution alignment

### 2.1 A+ three lanes and Harness final review

```text
User sentence
  → HealthTurnResolver (this-turn scope: metric/time/entity)
  → SchemaIntentRouter (Profile · 0ms deterministic)
  → TurnEvidencePlan (Tier0/Tier1/forbidden/tools)
  → Tier0 assembly (C layer · Data > Context)
  → LLM (narrative only, must not expand scope)
  → numerics_manifest audit + Harness Veto
```

- **Lane intercept order is not reversible**: Catalog / Patient State full table must not mount before Profile is chosen.  
- **Harness Veto**: `TurnEvidencePlan.forbidden` violations, numbers outside Manifest, `unauthorized_value` — same as today; this RFC **does not weaken**.  
- **LLM has no routing sovereignty**: `HealthTurnResolver` and `SchemaIntentRouter` are both C layer; optional 1.5B shadow only produces telemetry, does not block first token (continue v2.3 shadow-routing stance).

### 2.2 Manifest Tier and Causal Anchor

| Mechanism | This RFC stance |
|-----------|-----------------|
| **T0 measured values** | Multi-turn continue-focus must not “upgrade” T1 guideline values to T0; `numerics_manifest` still strict |
| **T1 disclosure block** | `GroundedAnswerComposer` narrative layer may cite T1, but must audit after `PHA_NUMERICS_AUDIT_SCOPE=t0_plus_disclosure` .mask |
| **Causal Anchor** | Episodic summary may contain “last turn discussed metric X”, but **forbid** auto-binding the focused supplement causal chain to LDL/HRV improvement (continue 3A.2 / 3C bridge TASK) |
| **Data > Context** | On continue-focus, `wearable_*` / `lab_*` profiles still forbid silent inject of full `SUPPLEMENT_BG` |

### 2.3 Memory conflict priority (P0–P4 · must keep)

| Priority | Type | Behavior under multi-turn expansion |
|----------|------|-------------------------------------|
| **P0** | This-turn user explicit statement | Overrides episodic-inferred scope/profile; may capture background, **does not** silently rewrite lab tables |
| **P1** | Structured labs / Manifest | Numeric iron evidence; `HealthTurnResolver` must not invent not-ingested years from episodic |
| **P2** | Session-focus assets | Attachment ledger, current metric family, current time window — **beats** full regimen |
| **P3** | background notes | Focused slice only + ≤3 preselected grounds (`build_preselected_grounded_hits`) |
| **P4** | Chat history / RECALL | Maintain anaphora; **attachment profiles still close cross-session RECALL** (see §5.2) |

Episodic generalization **strengthens P2**; it does not use P4 history snippets to replace the P1 ledger.

---

## 3. Goals and non-goals

### 3.1 Goals (Stage 3C)

| ID | Goal | Acceptance anchor |
|----|------|-------------------|
| **G1** | **Universal Episodic Focus**: every Harness profile (incl. fast lane) writes back `session_turn_focus` extended fields each turn | TTL decrement + same-topic refresh; non-attachment turns also have entries |
| **G2** | **HealthTurnResolver**: unified parse of `metric_scope` / `time_scope` / `lab_years` / `year_source` / `episodic_revived` | Forbid new scattered year ifs in `chat_service` |
| **G3** | **Declarative intent continue-focus**: `health_intent_catalog.yaml` (or extend existing schema registry) declares `episodic_continue`, anaphora, topic markers | Change intent only by YAML + golden cases |
| **G4** | **Clarify beats wrong guess**: multi-year lab / multi-metric ambiguity → `action=clarify` + chips (metric or year) | No silent default year |
| **G5** | **Observable**: `harnessReport.turnScope` + `episodic` node | Drop-offs attributable |
| **G6** | **Multi-turn golden H1–H4** into `selfcheck_manifest.json` | CI one command can block regression |
| **G7** | **UX v2 align** (phased): `FactBundle` → `GroundedAnswerComposer` + `followUps` + SSE `fact_card` first | Numerics audit isomorphic with tax v2 |

### 3.2 Non-goals

- ❌ Copy-paste modules from `tax_agent` or share a Python package  
- ❌ LLM full-power routing replacing `SchemaIntentRouter`  
- ❌ Restore incremental sync / new startup entry (R8)  
- ❌ Change Harness / TurnEvidencePlan **C-layer audit algorithm** body (only extend report fields and plan inputs)  
- ❌ Cross-session long-term user portrait (like tax C6) — separate backlog; this RFC is **in-session** episodic only  
- ❌ Rewrite 3B Vision ledger quality inside this RFC  

---

## 4. Target architecture

```text
POST /api/chat (SSE)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ HealthTurnResolver (new · C layer)                         │
│  In: user_message, session_id, episodic, data_quality     │
│  Out: HealthTurnScope                                      │
│    · primary_metric / metric_family                         │
│    · time_window (wearable) / lab_years[]                   │
│    · year_source: explicit | focus | default | clarify      │
│    · episodic_revived: bool                                   │
│    · needs_clarification + clarify_kind + choices[]         │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ revive + consume HealthSessionFocus (extend session_turn_focus)│
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ SchemaIntentRouter + health_intent_catalog (declarative continue) │
│  profile inherit: episodic.focus_profile weighted when no strong trigger │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ TurnEvidencePlan + Tier0 assembly (existing harness_plan extended input) │
│  + EPISODIC_BRIDGE slot (all profiles optional; attachment turns also have RECALL_FOCUS)│
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Fast lane / tools → FactBundle (new · isomorphic with tax v2) │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ GroundedAnswerComposer (new · optional LLM narrative layer) │
│  numerics strict + degrade template + followUps            │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ SSE: meta(turnScope) → fact_card → delta → follow_ups → done│
│ record_turn_focus + assistant digest write-back            │
└──────────────────────────────────────────────────────────┘
```

**Key change**: `attachment_asset_qa` / `episodic_bridge` / `temporal` branch judgments inside `chat_service` gradually **sink** into a single `HealthTurnResolver` + catalog output, consumed by `build_turn_evidence_plan(..., turn_scope=...)`.

---

## 5. Health-domain-specific constraints (must not be washed out)

### 5.1 Attachment-turn RECALL ban (continue 3A.2 P4)

| Rule | Notes |
|------|-------|
| **RECALL slot** | Under `attachment_asset_qa` / `attachment_episodic_bridge` profiles **forbidden**: inject cross-session `user_health_background_notes` snippets |
| **RECALL_FOCUS** | Replay only **this-session** already-audited `LabelLedgerV1` / Patient State slices (see active-recall spec) |
| **Episodic generalization does not relax RECALL** | Wearable/lab profiles may get `CHAT_RECALL` + `EPISODIC_BRIDGE`; attachment profiles **must not** open RECALL because of generalization |

### 5.2 Attachment vs non-attachment episodic fields on separate tracks

When extending `chat_session_turn_focus`, use **split-track storage**, avoid hard-fitting a “year” field onto supplement assets:

| Field | Attachment track | Universal track |
|-------|------------------|-----------------|
| `focus_profile` | `attachment_asset_qa` / `attachment_episodic_bridge` | `wearable_only` / `lab_cross_year` / `combined_review` / … |
| `focus_summary` | `label_ledger` truncated | C-layer generated summary such as “HRV · last 90d” |
| `focus_tokens_json` | Ingredient/OCR tokens | Metric aliases + time tokens |
| `focus_metric` | — | e.g. `hrv` / `ldl` / `sleep` |
| `focus_lab_years_json` | — | `[2023, 2024]` |
| `focus_wearable_window` | — | `{start, end}` ISO |
| `last_user_message` / `last_assistant_digest` | Two-turn bridge | Written by all profiles |
| `turns_remaining` | Default **3** (attachment deep focus) | Default **8** (wearable/lab shallow focus) |

**TTL split-track reason**: attachment ledger is high density and easy to pollute — keep shorter TTL; wearable/lab follow-ups depend more on anaphora — lengthen TTL and allow `revive`.

### 5.3 Clinical safety red lines

- Episodic must not generate or rewrite **dose/prescription**; drug interactions still go K-layer Lookup + Active Recall assertion replay  
- When `needs_clarification`, **forbid** calling `GET_HEALTH_DATA` wide-window tools to guess user intent  
- Fast lanes (e.g. temporal dossier) must also `record_turn_focus`, or next-turn `EPISODIC_BRIDGE` is empty

---

## 6. Core module design (PHA-native)

### 6.1 HealthTurnResolver

**Duty**: unique parse of “this turn’s effective health scope”, analogous to tax `TaxTurnResolver`; does **not** parse Harness profile (profile still belongs to `SchemaIntentRouter`).

**Output `HealthTurnScope` (suggested fields)**:

```text
HealthTurnScope:
  metric_keys: list[str]          # e.g. ["hrv", "resting_hr"]
  metric_source: str              # explicit | focus | inferred_default
  lab_years: list[int]
  year_source: str                # explicit | focus | uploaded | default | clarify
  wearable_window: {start, end} | null
  time_source: str
  profile_hint: str | null        # for catalog weighting, not final profile
  episodic_revived: bool
  needs_clarification: bool
  clarify_kind: str | null        # lab_year | metric | time_window
  clarify_prompt: str | null
  clarify_choices: list[dict]     # {id, label, payload}
```

**Parse order (deterministic)**:

1. **Explicit entity first**: metric tokens, four-digit years, `date_range_parser` windows in the user sentence → `*_source=explicit`  
2. **Anaphora continue-focus**: `health_intent_catalog.anaphora` hit + episodic valid → inherit `focus_metric` / `focus_lab_years` / `focus_wearable_window`  
3. **Topic continue**: isomorphic with tax `_topic_continues` — profile_hint matches `focus_profile`, or `last_assistant_digest` keyword intersection  
4. **Data-driven default**: `list_distinct_report_dates` / wearable coverage → default single year or last 90 days  
5. **Clarify branch**: multi-year labs all have LDL and user only says “血脂” → `needs_clarification=true`, **forbid** silently picking the latest year  

**Relation to `temporal_router`**: `temporal_router` degrades to a **HealthTurnResolver sub-strategy** (`resolve_lab_years` / `build_dossier`), no longer forked directly by `chat_service`.

**Anaphora examples (must be covered by golden cases)**:

| Turn | User sentence | Expected scope |
|------|---------------|----------------|
| R1 | 「我 HRV 正常吗」 | `metric=hrv`, `window=90d`, `source=default` |
| R2 | 「那上个月呢」 | `metric=hrv`, `window=上月`, `metric_source=focus`, `episodic_revived=false` |
| R1 | 「2024 年 LDL」 | `lab_years=[2024]`, `source=explicit` |
| R2 | 「前年呢」 | `lab_years=[2023]`, `year_source=focus` (relative anchor, not LLM) |

### 6.2 Universal Episodic Focus (extend `session_turn_focus`)

**Write timing**: end of every chat turn (incl. fast lane, deterministic attachment reply, `maybe_deterministic_attachment_reply`), call `record_health_turn_focus(...)`:

- `consume` decrements TTL  
- Refresh `focus_*` fields and `last_user_message` / `last_assistant_digest` (digest rule same as tax: ≤320-char summary)  
- `focus_profile` = this turn’s Harness `profile`

**Read timing**: every `chat` entry `revive_health_session_focus(session_id, message)` → inject `EPISODIC_BRIDGE` Tier0 block (lightweight for non-attachment profiles; attachment profiles still use existing `ATTACHMENT_LABEL` + bridge TASK).

**`EPISODIC_BRIDGE` block contract (universal track)**:

```text
【上轮对话摘要 · EPISODIC_BRIDGE】
- 关注指标: HRV
- 时间窗: 近 90 天（至 2026-06-09）
- 主题 profile: wearable_only
- 用户：我 HRV 正常吗
- 助手：<digest>
- 续焦剩余: 6 轮
```

**Division with Active Recall** (continue 3C active-recall spec):

| Mechanism | What it solves |
|-----------|----------------|
| Episodic Focus | **Lane** + scope inherit + profile weighting |
| EPISODIC_BRIDGE | Natural-language anaphora (“那” / “继续” / “同上”) |
| RECALL_FOCUS | **Assertion bite** on attachment/interaction turns (C-layer replay) |

### 6.3 Declarative `health_intent_catalog.yaml`

Analogous to `tax_intent_catalog.yaml`, **coexist and fuse** with existing `SchemaIntentRouter`:

```yaml
version: "1.0"
anaphora:
  tokens: [那, 这个, 上述, 继续, 同上, 刚才, 上个月, 去年, ...]
metric_aliases:
  hrv: [hrv, 心率变异性, rmssd, ...]
  ldl: [ldl, 低密度, 坏胆固醇, ...]
topic_markers:
  wearable_only: [睡眠, 步数, hrv, ...]
  lab_cross_year: [历年, 对比, 跨年, ...]
profiles:
  wearable_only:
    episodic_continue: true
    focus_metric_default: hrv
  attachment_asset_qa:
    episodic_continue: true
    recall_forbidden: true      # bind Harness forbidden RECALL
```

**Routing rules**:

- Explicit trigger score > episodic inherit score > default profile  
- When `episodic_continue: true`, weak questions (≤N chars, no new metric) inherit `focus_profile`  
- All tokens live in YAML; **forbid** new drug-name/metric regex tables in `chat_service` (align active-recall L-1)

**Relation to Universal Catalog / MC**: `health_intent_catalog` owns **profile-level lanes**; MC `trigger_keywords` own **asset mount** — they chain via `profile_hint`, do not merge files lest A+ asset scoring break.

### 6.4 Clarify contract

When `HealthTurnScope.needs_clarification`, **short-circuit the LLM main path**:

**SSE event**:

```json
{"event": "clarify", "kind": "lab_year", "prompt": "您有多年的血脂记录，想查看哪一年？", "choices": [{"id": "2024", "label": "2024年"}, {"id": "2023", "label": "2023年"}]}
```

**Principles**:

- Clarify turns **do not** write episodic consume (or write `mode=clarify` and do not decrement TTL)  
- User chip click is `explicit` scope, overrides episodic  
- Harness `forbidden` on clarify turns bans Patient State full-table inject

### 6.5 Observability: `harnessReport.turnScope`

Extend `pha.harness_report` (suggest schema `pha.harness_report/v2`, keep old fields):

```json
{
  "turnScope": {
    "metricKeys": ["hrv"],
    "metricSource": "focus",
    "labYears": [],
    "yearSource": "focus",
    "wearableWindow": {"start": "2026-03-11", "end": "2026-06-09"},
    "timeSource": "explicit",
    "episodicRevived": false,
    "focusProfile": "wearable_only",
    "turnsRemaining": 6
  },
  "episodic": {
    "bridgeInjected": true,
    "recallFocusInjected": false
  }
}
```

**Ops use**: real-device three-turn crash → check whether `metricSource` wrongly `default`, whether `episodicRevived` should be true, whether `profile` forked from `focusProfile`.

### 6.6 GroundedAnswerComposer and SSE UX v2 (phased G7)

**Isomorphic** with `tax-chat-experience-v2.md`, adapted to PHA numerics:

| Layer | PHA mapping |
|-------|-------------|
| **FactBundle** | Patient State slice + Manifest KV + `DATA_AVAILABILITY` + wearable summary |
| **Composer L1** | LLM narrates FactBundle as clinical Chinese |
| **Composer L2** | `audit_response_numerics` strict + Manifest Tier |
| **Composer L3** | Audit fail → deterministic template (existing fast-lane copy) |
| **Composer L4** | `followUps` 3 (must come from catalog-allowed next steps, not LLM freely inventing new metrics) |

**SSE sequence** (align tax v2):

```text
meta (turnScope + profile)
  → fact_card (T0 number-card JSON)
  → delta (narrative tokens)
  → follow_ups
  → done (harnessReport v2)
```

**Red line**: numbers in `fact_card` must ⊆ this turn’s `numerics_manifest`; sending fact_card first does not change the Harness forbidden set.

---

## 7. TurnEvidencePlan integration points

`build_turn_evidence_plan` adds optional param `turn_scope: HealthTurnScope | None`, used for:

| Input | Effect |
|-------|--------|
| `turn_scope.metric_keys` | Choose `WEARABLE_90D_SUMMARY` vs `LDL_AUTHORITY` vs evidence-slice columns |
| `turn_scope.lab_years` | `temporal_router` dossier year list |
| `turn_scope.needs_clarification` | Return `profile=clarify` plan, slots only `MASTER_ANCHOR` + `TASK` |
| `focus_profile` inherit | Weak question + `episodic_continue` → keep last-turn profile, avoid falling `lifestyle` |

**Attachment-specific path kept**:

- `attachment_asset_qa` + `attachment_episodic_bridge` logic **not deleted**, triggered by `HealthTurnResolver.profile_hint` + catalog instead of inline string judgments in `chat_service`  
- `evidence_scope` (`focus_plus_availability` etc.) still from the attachment submodule, as `TurnEvidencePlan.evidence_scope` into harness report

---

## 8. Multi-turn golden cases (H1–H4)

Into `scripts/pha_health_turn_resolver_selfcheck.py`, registered in `selfcheck_manifest.json`.

| ID | Scenario | Initial state | User sentence sequence | Assert |
|----|----------|---------------|------------------------|--------|
| **H1** | Wearable anaphora continue window | Empty focus | 「HRV 怎么样」→「那上个月呢」 | R2 `metric=hrv`, `metric_source=focus`, `time_source=explicit`, window is last month |
| **H2** | Lab multi-year scope | DB has 2023–2024 LDL | 「每年的 LDL」 | `lab_years=[2023,2024]`, `year_source=uploaded`, no years without data |
| **H3** | Fast-lane then continue-focus | R1 took `wearable_only` fast lane | 「继续」 | R2 `profile=wearable_only`, `metric_source=focus`, `turns_remaining` refreshed |
| **H4** | Ambiguity clarify | DB has 2023–2024 lipids | 「血脂怎么样」(no year) | `needs_clarification=true`, `clarify_kind=lab_year`, choices include 2023/2024 |

**Attachment specials (H-A series, alongside H1–H4)**:

| ID | Scenario | Assert |
|----|----------|--------|
| **H-A1** | Attachment R1→R2 follow-up | R2 `profile=attachment_asset_qa` or `attachment_episodic_bridge`; `RECALL` forbidden |
| **H-A2** | R2 asks HRV | `attachment_episodic_bridge` + `DATA_AVAILABILITY`; no full DOSSIER inject |
| **H-A3** | R3 interaction question | `RECALL_FOCUS` contains PS ledger; fixture-med not dropped |

**E2E golden (human/real device, not CI-blocking)**: reuse `stage3a-regression-checklist-v1.md` three-turn attachment script + new wearable two-turn script.

---

## 9. Phased implementation and Feature Flag

| Phase | Content | Flag | Depends |
|-------|---------|------|---------|
| **3C-α** | `HealthTurnResolver` + `turnScope` report + H1–H4 selfcheck | `PHA_HEALTH_TURN_RESOLVER=1` | P1 selfcheck green |
| **3C-β** | Universal `record_turn_focus` + `EPISODIC_BRIDGE` all profiles | `PHA_EPISODIC_ALL_PROFILES=1` | 3C-α |
| **3C-γ** | `health_intent_catalog.yaml` + episodic profile inherit | `PHA_HEALTH_INTENT_CATALOG=1` | 3C-β |
| **3C-δ** | `action=clarify` SSE + frontend chips | `PHA_CLARIFY_TURNS=1` | 3C-γ |
| **3C-ε** | `GroundedAnswerComposer` + SSE fact_card | `PHA_GROUNDED_COMPOSER=1` | Manifest audit green |

**Rollback**: each flag independently defaults `0`; after off, revert to Stage 3A.2 behavior; must not break single-turn chat.

---

## 10. Acceptance (definition of coding done)

### 10.1 Automatic

- [ ] `bash scripts/run_selfchecks.sh` all green (incl. `health_turn_resolver` H1–H4 + H-A series)  
- [ ] `create_app()` + `POST /api/chat` single-turn no regression  
- [ ] Harness snapshot tests: `turnScope` fields non-empty on wearable / lab / attachment three lanes  

### 10.2 Human/E2E

- [ ] Attachment three-turn script (3A regression checklist) behavior equal or better than 3A.2 baseline  
- [ ] Wearable two turns: “HRV” → “上个月” does not drop `lifestyle`  
- [ ] Multi-year LDL: ambiguity sentence triggers clarify or after explicit choice numbers match Manifest  
- [ ] `harnessReport` can explain any turn’s profile-choice reason  

### 10.3 Compliance

- [ ] `attachment_asset_qa` turns still have `RECALL` in `forbidden`  
- [ ] numerics audit no new `unauthorized_value` regression  
- [ ] No `tax_agent` import; `rg tax_agent` in `pha/` is zero  

---

## 11. Risks and mitigations

| Risk | Level | Mitigation |
|------|-------|------------|
| Generalized episodic pollutes wearable turns with supplement plans | High | TTL split-track + Data>Context forbidden unchanged |
| Dual-source years from `HealthTurnResolver` and `temporal_router` | Medium | Single entry; temporal only a submodule |
| catalog vs MC config conflict | Medium | profile_hint one direction; shadow routing observes divergence rate |
| Composer narrative layer introduces numbers outside Manifest | High | strict audit + fact_card first + degrade chain |
| Too much clarify interrupts UX | Low | Only `lab_years` multi-year and weak questions; wearable default window no clarify |

---

## 12. Docs and change register

Coding PRs must sync-update:

| Document | Content |
|----------|---------|
| `docs/startup-change-log.md` | Stage 3C phases and flags |
| `docs/stage3a-regression-checklist-v1.md` | New wearable multi-turn scripts |
| `CHANGELOG.md` | User-visible: multi-turn follow-up, clarify chips |
| `.cursor/rules/startup-consensus.mdc` | If new env flags |

---

## 13. Reference mapping (concept re-infusion, not code copy)

| tax_agent concept | PHA counterpart (to build) |
|-------------------|----------------------------|
| `TaxTurnScope` | `HealthTurnScope` |
| `tax_turn_resolver.py` | `health_turn_resolver.py` |
| `tax_intent_catalog.yaml` | `health_intent_catalog.yaml` |
| `record_turn_focus` | `record_health_turn_focus` |
| `episodic_bridge_block` | `health_episodic_bridge_block` |
| `harnessReport.turnScope` | Same field name, health semantics |
| M1–M4 | H1–H4 + H-A series |
| `GroundedAnswerComposer` | `grounded_answer_composer.py` (PHA clinical narrative style) |

---

## 14. Open questions (pending review)

1. **Unified TTL vs split-track**: this RFC suggests attachment 3 / universal 8; override with a single env?  
2. **Clarify frontend**: does PHA Console reuse tax chip UI pattern, or plain-text reply?  
3. **1.5B shadow**: emit `shadow_profile` into harness at 3C-γ, or 3C-α observe-only first?  
4. **Composer scope**: first version only `wearable_only` + `attachment_asset_qa` fast lanes, other profiles later?

---

**3C-α ✅ coded** · **3C-β ✅ coded** (branch `stage3c-alpha-health-turn-resolver`): Resolver + episodic write-back + harness `turnScope`; production default flag=0, enable `PHA_EPISODIC_ALL_PROFILES=1`.

---

## 15. Stage 3F handoff (intent-resolution completeness)

After 3C delivers **scope / episodic / clarify(lab_year) / Composer**, **Goal (synthetic goal)** and **multi-domain evidence auto-upgrade** are still missing. That gap is planned by a separate RFC, **not** a 3C-scope rollback or a single E2E patch:

- **Doc**: [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) (Approved 2026-06-17)
- **New modules**: `GoalClassifier` · `Harness Arbiter` · `focus_goal` episodic · clarify `intent_scope` / `data_gap`
- **Duties unchanged**: `HealthTurnResolver` still does not choose the final profile; authoritative profile locks only **after Harness Arbiter**
- **Coding phases**: 3F-α (Arbiter + H5) → 3F-β (goal anchor + H6/H7) → 3F-γ (catalog + intent clarify + H8) → 3F-δ (Shadow telemetry)

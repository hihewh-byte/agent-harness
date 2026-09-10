# PHA architecture evolution blueprint v2.3

> **Language / 语言**：English (this document) · [中文](pha-architecture-evolution-v2.3.md)

> **Status**: Design RFC — planning only, no implementation code in this document  
> **Baseline build**: `pha-v2.2.11-a-plus` (A+ SchemaIntentRouter already landed)  
> **Author stance**: Cursor architecture review — independent judgment after the Gemini / Grok debate  
> **Revision date**: 2026-06-01 (Wave 3d-δ/ε fact pipeline · Interpretation Policy · Soul alignment)

---

## 0. Purpose of this document

This document answers three questions:

1. In the Gemini vs Grok architecture debate, which items are **consensus that must be locked**, and which are **tensions that can evolve**?
2. On top of PHA’s current code baseline, what is **my own evolution blueprint**?
3. **What to do next** — design-first, then encode: priority and acceptance criteria.

**Non-goals**: this document does not introduce LLM-sovereign routing; does not change the `chat_service` two-round Catalog state machine; does not expand into concrete PR implementation details.

---

## 1. Debate recap: my independent analysis

### 1.1 The two sides have already converged

The surface conflict between Gemini and Grok is really a **mismatch of time scales**:

| Dimension | Gemini (more conservative) | Grok (more evolutionary) | Actual relationship |
|-----------|----------------------------|--------------------------|---------------------|
| Routing sovereignty | C-layer Schema scoring is the industrial endgame | Long-term LLM assist + Harness veto | **Progression, not replacement** |
| Latency | Opposes two-round ReAct | Single-round structured / shadow routing can compress TTFT | **Engineering shape is designable** |
| Tokens | DCH pruning is the core moat | A static Catalog still cheaper than full Schema | **Aligned** |
| Determinism | 0.5% crash in a medical scene = disaster | Harness always keeps veto | **Aligned** |
| Maintenance cost | Did not go deep on 150+ metrics | Keyword hell needs offline distillation | **A+’s real soft spot** |

**My conclusion**: this is not a binary “rule of law vs rule of people”. It is a layered constitution of **“rule of law first, semantics as assist, Harness as final review”**. Gemini correctly stressed the **determinism floor** of health scenes. Grok correctly pointed out A+’s **configuration-entropy ceiling** as scale grows. Only the merge of the two is the path PHA should take.

### 1.2 Gemini’s three strongest points, which must be kept

1. **Lane intercept happens before Catalog render**  
   The root cause of a supplement turn misclassified as wearable already proved: if Profile is wrong, even beautiful DCH copy is just “a landscape painted on a cliff”. Any future Hybrid scheme must not break this order:

   ```text
   user sentence → IntentRouter (Profile) → Catalog conditional mount → Tier0 assembly → LLM
   ```

2. **Data absolutely precedes Context**  
   Class separation of `lab_*` / `wearable_*` vs `supplement_bg` is not business if-else; it is an asset contract. Pure SpO2 / sleep-analysis sentences must keep Context assets silent at L0.

3. **C-layer numerics audit is independent of model IQ**  
   The stronger the model, the more likely it is to “confidently” cite clinical reference values outside the Manifest (e.g. the `3.4 mmol/L` ideal LDL that appeared in combined E2E). **Reasoning ability ≠ compliance ability**; `audit_response_numerics` must be kept long-term.

### 1.3 Grok’s three strongest points, which A+ must face

1. **Non-linear explosion of rule maintenance**  
   Three Schema assets can still be maintained by hand; if P2 expands to 50–150 lab/wearable metrics, pairwise conflicts among `trigger_keywords` / `negative_keywords` will not be sustainable.  
   **The solution is not to fall back to pure LLM routing**, but: **offline distillation + online deterministic execution** (a large model writes config; a small engine runs config).

2. **Shadow Routing is the best Hybrid shape**  
   The main path keeps A+’s 0ms determinism; LLM semantic guesses run async in parallel and produce only **advice and telemetry**, never blocking the first token. This is far more practical than “round 1 must wait for the LLM to emit JSON”.

3. **Progressive evolution must have Feature Flags and rollback**  
   Each Stage should be able to fall back to the previous Stage under `PHA_HARNESS_*` switches and be observed via `HarnessBuildReport`, rather than changing production chat behavior in place.

### 1.4 Two points both sides underweighted, which I recommend adding

**(A) Observation layer before intelligence layer**

Before introducing any LLM-assisted routing, first stand up **Route Telemetry**:

- Each turn records: `asset_scores`, `profile`, `include_supplement_catalog`, `catalog_line_count`
- If Shadow is later enabled: record disagreement rate of `shadow_proposal` vs `authoritative_profile`
- Persist 2–4 weeks of real traffic in JSONL (existing `HarnessBuildReport`), then decide whether Stage 2 is worth it

**(B) Manifest Tier v1 — disclosure-protocol edition (approved; see dedicated doc)**

The combined E2E yellow light (`unauthorized_value:3.4`) was caused by the C layer not distinguishing T0 user-measured values from T1 guideline references. **Do not adopt** Schema T1 injection / offline distillation (maintenance and legal-liability concerns).

Official design: **[`manifest-tier-v1.md`](manifest-tier-v1.md)** (v1.1, audited by Grok/Gemini):

| tier | Meaning | Audit policy |
|------|---------|--------------|
| **T0** | In-warehouse user-measured values (Manifest KV) | Strict allowlist, block |
| **T1** | LLM-internalized guidelines / ideal lines | **Not injected**; pass after masking the disclosure block; format-check only, no truth check |
| **T2** | Model inference | Prompt requires “estimate / possibly”; v1 warning only |

Stage 1 close-out = implement `PHA_NUMERICS_AUDIT_SCOPE=t0_plus_disclosure` + combined E2E all-green; **production default already switched to `t0_plus_disclosure`** (rollback: `PHA_NUMERICS_AUDIT_SCOPE=t0_strict`).

#### Stage 1 close-out summary (2026-05-24)

Manifest Tier v1 landed successfully; bilingual sandbox complete. Domain-split audit + disclosure protocol fully solved the combined E2E `3.4` yellow-light false kill. **Production default switched to `t0_plus_disclosure`**, `PHA_NUMERICS_T1_M4_MODE=warn`.

| Milestone | Status |
|-----------|--------|
| A+ SchemaIntentRouter + three lanes | ✅ `pha-v2.2.11-a-plus` |
| Manifest Tier v1 disclosure protocol | ✅ `pha-v2.2.12-manifest-tier-v1` |
| combined E2E numerics | ✅ exit 0 under `t0_plus_disclosure` |
| Route Telemetry systematized | ⏳ fields partially landed; **operations** see [`telemetry-review-playbook.md`](telemetry-review-playbook.md) |
| Hybrid registry + Metadata Catalog | ✅ 2A–2D encoded; **production deepening = P1** (does not block 3B) |
| **Stage 3B Perception Worker** | 🚧 **3B-α implementation** → [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) v1.0 |
| 3A attachment-QA golden closed loop | ⏳ [`stage3a-regression-checklist-v1.md`](stage3a-regression-checklist-v1.md) |
| **Stage 3C multi-turn coherence** | ✅ 3C-α～ε encoded → [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) |
| **Stage 3F intent-resolution completeness** | ✅ 3F-α～δ encoded → [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) |
| **Stage 3G E2E spoken-language storm + Bank regression** | ✅ Baseline 70/70 · Bank seed=20260626 **164/164** → [`stage3g-e2e-remediation-rfc.md`](stage3g-e2e-remediation-rfc.md) |
| **Stage 3H universal attachment fallback lane** | ✅ 3H-α/β/γ + structural fallback + 148/148 stress → [`rfcs/rfc-stage3h-universal-attachment-lane.md`](rfcs/rfc-stage3h-universal-attachment-lane.md) |

---

## 2. PHA layered constitution (my core architecture view)

Regardless of whether the base is Qwen 7B, Claude 3.5, or a future 70B, PHA should keep **four-layer decoupling**:

```text
┌─────────────────────────────────────────────────────────────┐
│ L3 · Reasoning layer (LLM)                                   │
│   Duty: synthesize evidence, generate NL, (optional) propose fetch │
│   Forbid: sole routing power; citing Manifest-out numbers without a tier │
└───────────────────────────▲─────────────────────────────────┘
                            │ receives only pruned context
┌───────────────────────────┴─────────────────────────────────┐
│ L2 · Evidence layer (Fetch + Manifest + Reduce)              │
│   Duty: pull by asset_id, Numerics allowlist, UniversalReduce│
└───────────────────────────▲─────────────────────────────────┘
                            │ Profile already locked
┌───────────────────────────┴─────────────────────────────────┐
│ L1 · Catalog layer (Catalog + DCH)                           │
│   Duty: ≤5 L0 entries, conditional Context mount, dynamic when_zh bait │
└───────────────────────────▲─────────────────────────────────┘
                            │ lane already locked
┌───────────────────────────┴─────────────────────────────────┐
│ L0 · Intent layer (SchemaIntentRouter + TurnEvidencePlan)    │
│   Duty: Profile selection, Data>Context, forbidden/tools/slots │
│   Traits: 0ms local, pure config, golden-regressable         │
└─────────────────────────────────────────────────────────────┘
```

**Harness Veto** is distributed across L0–L2: any LLM fetch proposal must pass L0 Profile allow-domain + L2 Manifest domain checks; a Shadow LLM never touches the L0 steering wheel.

### 2.1 End-to-end data flow (including Perception Worker · 2026-05-26)

On-device recap (DeepSeek / Qwen 7B) proved: **L3 cannot own OCR / ledger settlement**; if Tier0 eats the ledger, the model will hallucinate. Insert a **deterministic Perception Worker** (3B-α/β) between L0 and L2.

**Perception-layer constitution (2026-05-27 · Spec v0.3)**: **ignorant routing** — upload does not assume a business family; **L0.0 media split** → **L0.2 all-type `layout_region` slices** → **L0.4 multi-engine IR** → **L0.5 `document_family`** → Schema ledger. EN/ZH key names in Spec §0.1. Details: [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) §0.1 · §1.4 · §7.0–§7.10.

```text
user + N attachments (unknown business family)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ L0 · chat intent (SchemaIntentRouter + attachment_qa_mode)   │
│   session focus · episodic_bridge default lane · Harness Veto│
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ L0.0–L0.6 · Perception Worker (3B-α live / 3B-β target)      │
│   L0.0 media_route (pdf_* | raster_photo)                    │
│   L0.4 adapter IR (OCR / Layout / PDF / optional VLM)        │
│   L0.5 document_family (supplement|lab|medication|…)         │
│   L0.6 LabelLedgerV1 + merge_trace + P-gates G1–G6           │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Evidence      │  │ Metadata      │  │ Shadow        │
│ Worker        │  │ Catalog       │  │ default off   │
└───────┬───────┘  └───────┬───────┘  └───────────────┘
        └─────────┬─────────┘
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ L2 · Tier0 (ATTACHMENT_LABEL + DATA_AVAILABILITY + TASK …)   │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ L3 · main LLM — NL synthesis only; forbid inventing doses    │
│     outside the ledger                                       │
└─────────────────────────────────────────────────────────────┘
```

**Sub-agent two stages (no skipping)**:

| Stage | Shape | Notes |
|-------|-------|-------|
| **3B-α** | Deterministic Perception Worker | Current P0; no LLM on the main path |
| **3B-β** | Lightweight LLM Worker (Lab / guidelines, etc.) | Open Flag only after golden green + 2 weeks Telemetry |

---

### 2.2 Hardware Tier and Progressive Enhancement (M4 floor)

Wenhui ruled: **the same PHA must be fluent on M4 Air (7B); high-spec machines must have a visible dividend**. Detection and capability come from `runtime_capabilities()` + `PHA_HARDWARE_TIER` mapping (implementation in Stage 3B RFC §7).

| Tier | Detection (examples) | Perception | MC / Catalog | Shadow | Main model |
|------|----------------------|------------|--------------|--------|------------|
| **T1 · Survive** | VRAM ≤16G or only 7B available; `PHA_HARDWARE_TIER=1` | Serial OCR; no default dual Vision | MC Tier1; ≤400 token | **Off** | 7B single round |
| **T2 · Advanced** | 14B available or VRAM>16G | Multi-page OCR; optional Vision **verify** Flag | MC slightly expanded | Sample ≤5% | 7B/14B |
| **T3 · High-spec** | Multiple models coexist / cloud API | Concurrent OCR pages | MC Tier0 A/B | Sample ≤10% | 14B/32B/cloud |

**Principle**: T1 behavior = default production behavior; T2/T3 only add capability, never break the T1 contract.

---

## 3. Evolution blueprint (five stages, my version)

Relative to Grok/Gemini’s three stages, I split **Stage 1 into “close-out” vs “harden”** and give **Manifest tier** its own workstream, to avoid a false Green of “A+ is done”.

### Stage 0 — A+ constitution landed ✅ (mostly complete)

| Item | Status | Notes |
|------|--------|-------|
| `supplement_bg.schema.json` | ✅ | Context asset + conditional catalog |
| `SchemaIntentRouter` | ✅ | Substring scoring + Data>Context |
| Delete `user_message_is_supplement_manifest` | ✅ | p1.6.1 tech-debt retired |
| DCH conditional mount | ✅ | Pure SpO2 sentence Catalog 2 lines |
| Offline golden / schema selfcheck | ✅ | T1 supplement + T2 combined dry-run pass |
| spo2 / supplement E2E | ✅ | Wearable lane, supplement lane exit 0 |
| combined E2E numerics | ✅ | Manifest Tier v1 solved the 3.4 yellow light |
| Route Telemetry JSONL | ⏳ | Stage 2 folds in `numerics_audit` + shadow |

**Stage 0 verdict**: routing constitution is in force; **Stage 1 is closed** (`pha-v2.2.12-manifest-tier-v1`).

---

### Stage 1 — A+ harden + Manifest Tier ✅ (v2.2.12 · closed)

**Goal**: turn A+ from “it runs” into “operable, extensible, auditable”.

| Work package | Status |
|--------------|--------|
| **1A · Route Telemetry** | ⏳ Stage 2 RFC |
| **1B · Schema governance** | Partial |
| **1C · Manifest tier** | ✅ [`manifest-tier-v1.md`](manifest-tier-v1.md) |
| **1D · E2E matrix** | ✅ Three lanes + combined numerics |
| **1E · Keyword-conflict detection** | ✅ Stage 4-α · `pha/loop_keyword_conflicts.py` |

---

### Stage 2 — Hybrid dynamic registry + MC + Shadow (v2.3 ~ v2.4) 📋 v2.3.3 final-review merge

**External review (2026-05-24)**:

| Source | Score | Status |
|--------|-------|--------|
| Grok · Stage 1 | 9.4/10 | Close-out acknowledged (note: its “production default t0_strict” is outdated; see RFC appendix F) |
| Grok · Stage 2 RFC | 9.0/10 | Approved with refinements; suggested admission Checklist → already in RFC §5.6 |
| Gemini | Final-review pass | **Retracted same-turn registration**; firmly supports Discover→Promote + CI preset templates |

**Encode status**: **2A ✅** · **2B ✅** · **2C ✅** · **2D ✅** · **3A ✅** OCR/vision on-net · **3A.1–3A.2.2 ✅** code merged · **3A golden E2E ⏳ not green** · **3B 🔴 P0 RFC v0.9**

**3A RFCs**: [`stage3a1`](stage3a1-attachment-qa-governance.md) · [`stage3a2`](stage3a2-episodic-focus-and-grounded-rationale.md) · [`stage3a2.1`](stage3a2.1-response-ux-and-causal-anchor.md) · [`stage3a2.2`](stage3a2.2-answer-quality-and-vision-guard.md) · [`stage3a-regression-checklist-v1`](stage3a-regression-checklist-v1.md) · [`stage3a2.3`](stage3a2.3-chat-attachment-inline-preview.md) 📋 P2 UX

**3B RFC**: [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) · v1 blocking goldens: **IMG_6800 + IMG_6801**

**Goals**:

1. **Universal Dynamic Slots**: supplements / meds / genes / allergies are all Slots; preset `universal_health_assets.json` + user-side **Discover→Promote** (**not** same-turn into the menu).
2. **≤400 token** MC (Tier1 default) + code-name menu; when Layer B truncates, **degrade Context first, keep Data**.
3. **Existence Veto** + **2A telemetry first**; Shadow **smart sampling, default off** (2D).

**Official RFC**: [`metadata-catalog-v2.3.md`](metadata-catalog-v2.3.md) (**v2.3.3**)

**Merged implementation order (encode after sign-off)**:

```text
2A  HarnessReport v1.1 (intent_route / numerics_audit / catalog_existence / dynamic_slots)
2B  universal_health_assets.json + dynamic_slot_registry + Existence Veto + Discover→Promote
2C  MC domain Rollup + rank_score truncation + Tier1 inject (FORCE_TIER0 A/B only)
2D  Shadow smart sampling (combined 10% / lab 15% / casual 0%) — default off
```

**Key rulings (Cursor on Grok/Gemini disagreements)**:

| Disagreement | Merged conclusion |
|--------------|-------------------|
| Runtime dual-JSON sources of truth | ❌ schema is truth; preset JSON is template + CI only |
| LLM same-turn register into menu | ❌ allow async Discover; **next-turn** Promote |
| MC English-only | ❌ keep Stage 1 bilingual; dynamic slots keep `title_zh` |
| Shadow 100% | ❌ Profile-layered sampling + confidence≥0.7 high-priority telemetry |

**Acceptance**: see RFC §11; all Flags off ≡ v2.2.12.  
**P1 deepening**: weekly MC pick-rate report, Dynamic Slot zero-core-change drill (**does not block 3B goldens**).

---

### Stage 3B — Perception Worker (v2.3.3+ · **current P0**)

**Goal**: user uploads 1–N supplement images → **ledger accurate, auditable, low-confidence may refuse** → L3 only “speaks human”.

| Work package | Status | Notes |
|--------------|--------|-------|
| **3B-α · ledger contract** | 🚧 Week1 | P-layer G1–G6 · `perception_merge.py` · [`stage3b-week1-implementation.md`](stage3b-week1-implementation.md) |
| **3B-α · golden E2E** | ✅ CI | `scripts/pha_perception_golden_6800_6801.py` |
| **3B-α · multi-image Merge** | 📋 | Facts first; isolate e-commerce noise |
| **3B-α · confidence / refuse** | 📋 | Combined with `layout_hints`; do not false-kill legal single-ingredient cases |
| **3B-α · Fixture E2E** | ⏳ | NOW·PS/Choline/Inositol **CI only** (see Spec appendix A) |
| **3B-α · L3 forbid inventing doses** | 📋 | TASK constitution + numerics alignment |
| **3B-β · Vision Worker** | 📋 Spec v0.2 | [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) · media split + post `document_family` |
| **3C · attachment async + evidence bridge** | 📋 Spec | see table below |
| **3C · vision capability matrix** | 📋 v0.2 | [`stage3c-vision-capability-matrix.md`](stage3c-vision-capability-matrix.md) |
| **3B · real-image E2E** | 📋 | [`stage3b-e2e-real-label-fixture.md`](stage3b-e2e-real-label-fixture.md) |

**3C Specs**: [`stage3c-async-attachment-orchestrator.md`](stage3c-async-attachment-orchestrator.md) · [`stage3c-episodic-evidence-bridge.md`](stage3c-episodic-evidence-bridge.md) · [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.md) (🔒 v0.2) · [`stage3c-k-interaction-lookup-backlog.md`](stage3c-k-interaction-lookup-backlog.md) · analysis [`stage3c-attachment-evidence-bridge-analysis.md`](stage3c-attachment-evidence-bridge-analysis.md)

**Official RFC**: [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) · **β Spec**: [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md)

**Relation to 3A**: 3A routing / focus / causality **is not re-encoded**; gaps fold into 3B (see regression checklist).

---

### Stage 3 — Hybrid controlled pick (v3.0+)

**Goal**: LLM emits a **structured fetch proposal** via Guided Decoding / JSON Mode; Harness executes veto + Manifest audit.

| Mechanism | Notes |
|-----------|-------|
| Input | Stage 2 Metadata Catalog + Tier0 Task |
| Output | `{ "requested_ids": [...], "confidence": 0.xx }` |
| Veto rules | Assets Profile does not allow → drop; Context assets need `include_supplement_catalog`; over ≤5 → truncate and warn |
| Fallback | Parse fail / timeout → fall back to Stage 1 `default_combined_fetch_ids(user_message)` |
| Backend | Must evaluate local FSM (Outlines/SGLang) pre-generation cost; **forbid** compiling a hundred-asset FSM on every request |

**Acceptance**: accuracy lift on complex open instructions is measurable; **illegal fetch rate = 0** (Harness intercepts).

---

### Stage 4 — Scale solution (P2 / 150+ metrics)

**Goal**: solve keyword hell, without giving up L0 determinism.

```text
Offline (CI/weekly)                    Online (0ms)
─────────────────                      ─────────────
Claude/large model batch-reads Schema  →  distill trigger/negative/embeddings
Human Review of the diff               →  write *.schema.json
Conflict-detection script              →  SchemaIntentRouter read-only execute
```

Optional: **embedding-assisted scoring** as a secondary signal to `score_asset`, but **the final Profile verdict is still a Harness table lookup**; embeddings never decide the lane alone.

---

## 4. Stage 2 detailed design: hybrid registry and Metadata Catalog

> **Full spec** in [`metadata-catalog-v2.3.md`](metadata-catalog-v2.3.md) **v2.3.2**. This section is a blueprint summary.

### 4.0 Hybrid registry (response to “supplement hardcoding”)

- Live `supplement_bg` is a **legacy asset-ID name**; underlying `user_health_background_notes.category` already supports `medication` / `supplement` / `symptom`, etc.  
- Stage 2 **does not** adopt Grok-style “hundred SQLite tables + dual JSON sources of truth”; it adopts **Schema as truth + domain ontology + Existence Veto + optional user override**.  
- **Veto** 7B **same-turn** dynamic register into the menu; **adopt** Discover→Capture→Promote (next turn) + Existence Veto.
- **Adopt** Grok: `rank_score` truncation, degrade Context first, Shadow smart sampling, `FORCE_TIER0` A/B only.

### 4.1 Definition

**Metadata Catalog (MC)** is a **compressed asset directory** generated deterministically by Harness from the **Tier B Schema registry**, independent of DCH bait sentences, serving:

- Let the LLM “know which evidence types the system has” (a prerequisite for mid-term Hybrid)
- Cut repeated-explanation tokens in `combined_catalog_task_text`
- **Does not replace** SchemaIntentRouter Profile selection

Relation to existing `EVIDENCE_CATALOG` (DCH dynamic when_zh):

| Block | Role | Typical length | Generated when |
|-------|------|----------------|----------------|
| `EVIDENCE_CATALOG` | This-turn **orderable** ≤5 items + DCH bait | 300–600 chars | After Profile is locked |
| `METADATA_CATALOG` | Global **read-only** asset index (id / class / one-liner) | 200–400 token | Cached at Schema hot-load |

### 4.2 Generation logic (pseudo-code-level design)

```text
Input: UniversalCatalogManager._assets (all active schemas)
Output: METADATA_CATALOG text block

FOR each asset IN assets SORT BY intent.priority DESC:
  IF asset.catalog.enabled == false: SKIP
  EMIT one line:
    "{asset_id} | {asset_class} | {display.title_zh} | lanes={catalog.profiles}"

Budget:
  - hard cap PHA_METADATA_CATALOG_MAX_TOKENS (default 400)
  - rank_score = intent.priority + mention_score + recency; when over, **cut Context first, keep Data**
  - MC default Tier1; only PHA_METADATA_CATALOG_FORCE_TIER0=1 enters Tier0 (A/B)
  - includes promoted dynamic slots; Layer B allows title_zh | title_en
```

**Existence Veto (menu layer)**:

```text
EVIDENCE_CATALOG row = Schema candidates ∩ existence_probe(user_id) pass
MC global index may list system capability; menu only lists this-turn orderable items
```

**Integration points**:

- **Does not enter** `wearable_only` / `supplement_manifest` / `casual` Tier0 (avoid wasting tokens)
- **May enter** `combined_review` Tier1 or Tier0 tail (Feature Flag)
- **Never** includes fetch full text, Manifest KV, Patient State

### 4.3 Integration with TurnEvidencePlan

```text
build_turn_evidence_plan(msg)
  → route = SchemaIntentRouter (unchanged)
  → IF profile == combined_review AND PHA_METADATA_CATALOG=1:
       slots_tier0 += ["METADATA_CATALOG"]  // or tier1, A/B
  → EVIDENCE_CATALOG still from build_catalog_block(profile, msg) (unchanged)
```

**Invariants**:

- `forbidden` / `tools_allowed` still decided by Profile
- Presence of MC **does not change** the default fetch ID set
- MC is a **read-only index**, not a second router

### 4.4 Shadow Routing optional scheme

**Motive**: collect “did A+ miss semantics?” data with zero TTFT regression risk.

```text
user sentence ──► SchemaIntentRouter ──► authoritative_profile (main path, sync)
                 │
                 └──► [async] shadow_worker
                        Input: METADATA_CATALOG (compressed) + user sentence
                        Output: shadow_proposal { ids[], profile_hint }
                        Action: write HarnessBuildReport.shadow_* only, do not block SSE
```

**Disagreement handling (telemetry only; Stage 2 does not auto-merge)**:

| Case | Action |
|------|--------|
| shadow_profile == authoritative | record `shadow_agree` |
| shadow extra-proposed Context assets | record `shadow_ctx_extra` (watch closely) |
| shadow suggested Data assets that A+ did not put in combined | record `shadow_data_miss` → human Review Schema |
| shadow vs A+ profile conflict | record `shadow_profile_conflict` → **still A+ wins** |

Stage 3 then uses 2–4 weeks of JSONL to decide which disagreement types can **conditionally** upgrade into Harness adopt rules.

### 4.5 Stage 2 Feature Flags

| Variable | Default | Notes |
|----------|---------|-------|
| `PHA_METADATA_CATALOG` | `0` | MC |
| `PHA_METADATA_CATALOG_TIER` | `1` | Default Tier1 |
| `PHA_METADATA_CATALOG_FORCE_TIER0` | `0` | Set 1 only for A/B |
| `PHA_CATALOG_EXISTENCE_VETO` | `1` | Menu veto |
| `PHA_DYNAMIC_SLOT_DISCOVERY` | `0` | 2B Discover Hook |
| `PHA_SHADOW_ROUTING` | `0` | Default off until 2D |
| `PHA_SHADOW_PROFILE_COMBINED_RATE` | `0.10` | Smart sampling |
| `PHA_SHADOW_CONFIDENCE_THRESHOLD` | `0.7` | High-priority telemetry |

---

## 5. Risk control and rollback

| Risk | Mitigation |
|------|------------|
| MC grows Tier0 volume | Default Tier1; hard token cap; enable only on combined profile |
| Shadow slows the machine | Async + timeout discard; on M4, shadow uses the smallest model |
| After Hybrid, LLM wild-picks | Profile veto + Manifest domain check + default fallback |
| Keyword-maintenance hell | Stage 4 offline distill; Stage 1E conflict detection |
| Guideline-constant false kill | Manifest tier (Stage 1C) |

**Rollback path**:

```text
Stage 3 → off PHA_HYBRID_FETCH → Stage 2
Stage 2 → off PHA_METADATA_CATALOG / PHA_SHADOW_ROUTING → Stage 1
Stage 1 → PHA_HARNESS_CATALOG_MODE=legacy → v2.2.6 full pre-inject (extreme)
```

---

## 6. Current baseline and Stage 1 close-out checklist

Based on measured `pha-v2.2.11-a-plus`:

| Test | Result |
|------|--------|
| `pha_schema_intent_selfcheck` | ✅ |
| `pha_harness_golden_run` T1/T2 | ✅ |
| `pha_e2e_qwen_spo2_sleep` | ✅ wearable_only, cites 90d/96.4%/8.0h |
| `pha_e2e_qwen_supplement` | ✅ structured supplement review |
| `pha_e2e_qwen_combined` Turn2 | ⚠️ `numerics_audit`: `unauthorized_value:3.4` |

**Stage 1 primary closure**: not a new feature, but **Manifest tier + combined numerics E2E all-green**.

---

## 7. Next-action plan (Week 0–4 · approved 2026-05-26)

> **Week 0 constraint**: docs + golden design + 3A regression scan; **core implementation starts after `stage3b-perception-worker-rfc` v1.0 sign-off**.

### 7.0 Track zero — freeze the baseline (0.5 day)

| # | Action | Output |
|---|--------|--------|
| 0.1 | Reconcile `build_marker` / `/health` / this document’s encode-status table | Baseline contrast table (see 3A regression checklist §0) |
| 0.2 | Archive DeepSeek/Qwen failed-turn summaries | `tests/fixtures/e2e-failures-2026-05/README.md` (de-identified) |

### 7.1 Track one — 3A regression acceptance (not re-encode)

| # | Action | Output |
|---|--------|--------|
| 1.1–1.7 | Scan per [`stage3a-regression-checklist-v1.md`](stage3a-regression-checklist-v1.md) | Red/green filed; red items → 3B deps |

### 7.2 Track two — Stage 3B RFC + implementation (P0)

| # | Action | Output |
|---|--------|--------|
| 2.1 | RFC v0.9 review | [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) |
| 2.2 | After RFC v1.0 sign-off, implement 3B-α | `LabelLedgerV1` + golden scripts + refuse UI |
| 2.3 | Blocking goldens | IMG_6800+6801 → NOW, PS/Choline/Inositol 50mg |

### 7.3 Track three — Telemetry operations (P0, parallel with 2.1)

| # | Action | Output |
|---|--------|--------|
| 3.1 | Attachment fields + **L0_L3_Alignment_Rate** KGI | [`telemetry-review-playbook.md`](telemetry-review-playbook.md) |
| 3.2 | Weekly Review template + JSONL export design | Same doc §4 |

### 7.4 Track four — Hardware Tier (P0 docs · P1 implementation)

| # | Action | Output |
|---|--------|--------|
| 4.1 | Matrix written into this document §2.2 | ✅ |
| 4.2 | `runtime_capabilities()` + Flag mapping | 3B RFC §7 implementation |

### 7.5 Track five — Stage 2 MC deepening (P1, does not block 3B)

| # | Action | Output |
|---|--------|--------|
| 5.1 | MC pick-rate sample | Telemetry weekly |
| 5.2 | Dynamic Slot zero-core-change drill | Drill record |

### 7.6 Explicitly not doing (this phase)

- ❌ Re-encode 3A.2.1 / brand-allowlist regex table
- ❌ 3B-β parallel multi-LLM sub-agents
- ❌ Replace Harness main chain with LangChain
- ❌ Hybrid Guided Decoding in production
- ❌ Full pha-core split-out
- ❌ 150+ metrics full L0 Catalog
- ❌ Let 7B or 1.5B **write** Active Recall assertion prose (C layer + optional `recall_plan` enum only)

### 7.7 Implementation-wave master table (updated 2026-05-30)

> **Gemini final review** (unanimous): forbid phrase trigger words · forbid small models writing assertions · `anchored_asset` forced every turn inside focus · `RECALL_FOCUS` Bottom-Anchor.  
> **Detail table**: [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.md) §11 · [`doc-roadmap-v2.3.md`](doc-roadmap-v2.3.md) (doc registry + TODO)

| Wave | Track | Delivery | Gate / status |
|------|-------|----------|---------------|
| **Wave 0** | Legal | Active Recall v0.2 + media-split Spec v0.2 | ✅ locked |
| **Wave 1 · P0** | L0 perception | Media routing + episodic default lane | ✅ encoded |
| **Wave 2 · AR** | L2.6 memory | `ActiveRecallLedger` + `RECALL_FOCUS` | ✅ encoded |
| **Wave 3 · L0** | Perception generalize | `layout_region` + OCR arbitration + G6 decouple | 🚧 heuristic L0.2 encoded; Florence/BYOK wait 3d-β |
| **Wave 3c** | Wearable fork | `WearableSnapshotLedgerV1` · `wearable_screenshot_review` | ✅ encoded · ⏳ **on-device 6-image E2E awaiting green** |
| **Wave 3d** | Wearable merge | `unknown+wearable` coerce · no-data refuse · follow-up reuse | ✅ encoded · L0 ledger 9 KPIs |
| **Wave 3d-γ** | Compare contract | `CompareTableV1` · Audit strong-decouple · forced Fallback | ✅ **3d-γ-a/b** · Soul/UX **v2.3.18** |
| **Wave 3d-ε** | Interpretation compliance | Interpretation Policy · NO_BASELINE subjective-word audit · respiratory rate into table | ✅ **v2.3.19** (C-13/C-14) |
| **Wave 3d-δ** | Fact pipeline | Metric Registry · stage / Workout day-agg | ✅ **δ-a/b/c** v2.3.20–23 · Registry JSON drives Compare · **pre-device G3 workout increment** |
| **Wave 3d-β** | Perception precision | Split-screen KPI · 6-image async UX · F-layer fixture | 📋 parallel with γ · depends on γ architecture green |
| **Wave 4a** | OSS gate | doctor · CI mock · PII audit · English README | 📋 **Spec first** (see doc-roadmap) |
| **Wave 4b** | L1.5 CHB | Chronic Health Brief async Compiler · `[ref:*]` Schema | 📋 Spec TBD (**after 3d green**) |
| **Wave 4c** | Cross-platform | Capability Matrix · Linux OCR-only degrade | 📋 backlog |
| **Wave 4 · AR-3** | K layer | `lookup_interactions` + Medication intent | 📋 see stage3c-k-interaction-lookup-backlog |
| **Wave 5** | Public release | `personal-health-agent` @ `v0.1.0-alpha` · Demo GIF | 🔒 4a all-green + **3d-γ Compare** golden |

**Scientific launch order (must not reverse)**:

```text
Read correctly  →  L0.2 slices + WearableSnapshot ledger high (Wave 3c/3d)
Compute clearly →  CompareTable SSO (Wave 3d-γ)
Do not invent   →  Compare Audit + Fallback (3d-γ) + Interpretation Policy (3d-ε)
Expand facts    →  Metric Registry + L1 day-agg (3d-δ)              ← new
Remember        →  AR-1/2 RECALL_FOCUS every-turn anchored_asset (Wave 2)
Interpret       →  LLM type-A judgment only (Policy v1) · CHB (4b)
Open source     →  4a gate + Public (Wave 5)
```

**Current build**: `pha-v2.3.21-wave3d-delta-b-workout-import`  
**Higher law**: [`pha-pm-constitution.md`](pha-pm-constitution.md)  
**Wearable dedicated docs**: [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md) · [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md) · [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md) · [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md)

### 7.9 Document registry (should write / should change)

> Full list, priority, owner fields: **[`doc-roadmap-v2.3.md`](doc-roadmap-v2.3.md)**.

| Priority | Document | Status | Notes |
|----------|----------|--------|-------|
| **P0** | [`stage3d-wearable-merge-and-gates-spec.md`](stage3d-wearable-merge-and-gates-spec.md) | 📝 first draft | 3d coerce/refuse/reuse legal |
| **P0** | [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md) | ✅ **v1.2** | CompareTable SSO · γ-1 fixtures |
| **P0** | [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md) | ✅ **v1.0 signed** | Two judgment types · no-baseline subjective words · 3d-ε |
| **P0** | [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md) | ✅ **v1.0 signed** | Metric Registry · stage/Workout · 3d-δ |
| **P0** | [`stage3d-wearable-e2e-checklist.md`](stage3d-wearable-e2e-checklist.md) | 📝 TBD | 6 images + G-Compare red/green table |
| **P0** | [`wave4a-open-source-readiness-spec.md`](wave4a-open-source-readiness-spec.md) | 📝 TBD | OSS gate · Apache-2.0 · CI · PII |
| **P1** | [`stage3d-beta-vision-precision-spec.md`](stage3d-beta-vision-precision-spec.md) | 📝 TBD | Split-screen KPI · async attachment UX |
| **P1** | [`wave4b-chronic-health-brief-spec.md`](wave4b-chronic-health-brief-spec.md) | 📝 TBD | L1.5 CHB · Compiler · write-disk gate |
| **P1** | `README.md` (English) | 📝 TBD | Quick Start · architecture one-pager |
| **P2** | [`wave4c-cross-platform-capability-matrix.md`](wave4c-cross-platform-capability-matrix.md) | 📝 TBD | Tier A/B/C · OCR degrade |
| **Maint** | This document §7.7 | ✅ updated this pass | Wave master table |
| **Maint** | [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md) | 🔄 3d revision pending | build number · 3d status |

### 7.11 PHA / LLM responsibility boundary (2026-06-01 · architecture lock)

> Dedicated: [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md) · warehouse expansion: [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md)

| Question | Architecture answer |
|----------|---------------------|
| User wants 90d compare, warehouse does not have it? | **Allowed**; **deterministic aggregate** at L1/L2 then write CompareTable; forbid LLM computing Raw |
| PHA stays faithful, LLM sounds like a doctor? | **If personal baseline exists → LLM may interpret (type A)**; **NO_BASELINE → facts only (type B)** |
| “Fairly adequate”? | **Type B out of bounds**; 3d-ε intercepts with an audit rule family, not a prompt tweak |
| Why are deep sleep / REM NO_BASELINE? | **`warehouse_not_implemented`**; Apple Raw often has it; PHA day table not aggregated (3d-δ) |

**Moat**: evaluative language is allowed if and only if data is real and traceable; evaluation must trace to CompareTable `verdict` or a personal 90d baseline.

### 7.10 Current TODO summary (2026-06-01)

| # | Task | Type | Blocks |
|---|------|------|--------|
| T1 | New-session on-device: 6 images + 90-day compare + sleep | Acceptance | — |
| T2 | Follow-up no image: “what is in the picture” reuses parse | Acceptance | T1 |
| T3 | Draft `stage3d-wearable-merge-and-gates-spec.md` | Docs | — |
| T4 | Draft `wave4a-open-source-readiness-spec.md` | Docs | — |
| T5 | Implement `pha_e2e_wearable_screens_real.py` + F-layer fixture | Encode | T1 green |
| T6 | GitHub Actions mock CI | Encode | T4 Spec |
| T7 | Draft `wave4b-chronic-health-brief-spec.md` | Docs | T1–T2 green |
| T8 | **3d-ε** encode: `compare_no_baseline_subjective` audit | Encode | ✅ v2.3.19 |
| T9 | **3d-ε** encode: `respiratory_rate` into CompareTable | Encode | ✅ v2.3.19 |
| T10 | **3d-δ** Spec review → sleep stage import design review | Docs/encode | δ Spec ✅ |

### 7.8 Non-case-by-case statement (architecture delivery, not one-off patches)

| Type | Content |
|------|---------|
| **Platform capability** | L0.0 media split, L0.5 `document_family`, L2.6 Active Recall, episodic default lane |
| **F-layer only** | NOW/6800/6801, R3 fixture-med questions — Fixture/E2E only, **do not enter** P-layer gates or routing regex |
| **Forbid** | Drug-name trigger tables, small models writing assertions, OCR≥25 short-circuit, follow-up question allowlists |

---

## 7.5 Stage 3F — intent-resolution completeness (locked 2026-06-17)

> Detail: [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md)

After Stage 3C solved **multi-turn scope / episodic / clarify(lab_year)**, the pipeline still lacked **Goal (synthetic goal)** and **multi-domain evidence auto-upgrade**. 3F as a **unified product-development wave** fills that layer; it is **not** if-else for a single E2E wording.

```text
HealthTurnResolver (scope)
  → GoalClassifier (goal_class)
  → SchemaIntentRouter (router_profile)
  → Harness Arbiter (authoritative_profile + existence_probe)
  → TurnEvidencePlan → Tier0 → LLM
```

| Slice | Content | Flag | Status |
|-------|---------|------|--------|
| 3F-α | GoalClassifier + Harness Arbiter + H5 | `PHA_GOAL_CLASSIFIER=1` | ✅ |
| 3F-β | focus_goal episodic + H6/H7 | `PHA_GOAL_SESSION_ANCHOR=1` | ✅ |
| 3F-γ | catalog goal_markers + clarify intent_scope + H8 | `PHA_CLARIFY_INTENT_SCOPE=1` | ✅ |
| 3F-δ | Intent Scout shadow telemetry | `PHA_SHADOW_ROUTING=1` | ✅ |

**Convergence with Gemini/Grok/Cursor debate**: finite profile lanes + declarative goal + existence_probe upgrade + Shadow zero-adopt.

---

## 8. Open questions (need Wenhui ruling)

1. **METADATA_CATALOG default Tier0 or Tier1?**  
   Recommend Tier1; if 7B pick-rate is low, then A/B Tier0.

2. **Does Shadow use the same model or a smaller one?**  
   Recommend `qwen2.5:1.5b` or a dedicated routing small model, to avoid GPU contention with main inference.

3. **Who maintains T1_reference guideline constants?**  
   Recommend medical advisor + Schema PR Review; forbid the model inventing them at runtime.

4. **Admission bar for P2 metrics into the Registry?**  
   Recommend: L2 warehouse ready + Manifest domain + intent block + ≥3 golden sentences each.

---

## 8. Stage 3G controlled Reflection and Stage 4 offline adaptive-evolution blueprint

> **Status**: Approved (docs layer, 2026-06-25)  
> **Related**: [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) · [`stage3g-e2e-remediation-rfc.md`](stage3g-e2e-remediation-rfc.md)

### 8.1 Stage 3G: controlled Reflection and defensive spec

To address cognitive drift and answer compliance under complex context, the system introduces **Stage 3G (Guided Reflection)** as a controlled reflection layer — the last Harness line of defense **after LLM synthesis, before the user sees it** (aligned with existing `iter_post_compose_audit_phase`).

| Principle | Requirement |
|-----------|-------------|
| **Max 1 inner loop** | Forbid infinite Token nesting or multi-round debate; the Reflection operator has **exactly 1** inner check/replace chance; if it fails, **force degraded output**, cut long-tail latency. |
| **Plan is immovable** | Reflection **only** may correct Action params, tool inputs, format, and **T0 number alignment**; **strictly forbid** modifying, overturning, or regenerating `TurnEvidencePlan`. |
| **Stateless physical isolation** | Reflection input is a **read-only context snapshot**; intermediate reasoning **must not write back** the Session state machine, lest hallucination pollute the control backbone. |
| **Shadow zero-adopt** | Any LLM Shadow score is **telemetry only**; must not adopt onto the user-visible path. |

**Already landed (R0/R1, code exists)**:

- **R0**: `CompareTable` fallback + `numerics_audit` (`chat_turn_compose.iter_post_compose_audit_phase`)
- **R1**: audit fail → ledger template **replace/hybrid** (not LLM freely rewriting facts)

**Not landed (Backlog)**: R2 Shadow quality-score telemetry.

### 8.2 Stage 4: offline adaptive evolution and question_manifest ledger

Uphold constitution article 2 **data-driven**: online/test two-way reconciliation; **reject** online real-time weight fine-tuning.

| Mechanism | Notes |
|-----------|-------|
| **question_manifest ledger** | Each Baseline / Bank stress writes `question_manifest_<ts>.json` (seed, slot, style, actual question) |
| **Offline alias evolution** | Mine **spoken variants** from manifest + crash jsonl → update `health_intent_catalog.json` / schema `trigger_keywords` → cold-start full regression |
| **Static assets go live** | Only via JSON/Markdown asset replace + harness-change-log; forbid Python phrase routing for a single E2E |

### 8.3 2026-06-25 E2E spoken-storm fix wave (after 3F)

| Priority | Item | Entry |
|----------|------|-------|
| P0 | Delta focus **before** weak-follow-up skip | `chat_skip_llm.py` |
| P1 | `metric_aliases` + `episodic_delta_followup` expansion | `health_intent_catalog.json` + schema/registry |
| P1b | Weak follow-up mutually exclusive with delta tokens | `health_intent_catalog.is_weak_episodic_followup` |
| P2 | T1 slow-turn profiling (vision vs LLM) | Independent perf RFC, **not** mixed with ZIP-import causes |

### 8.4 Stage 3H — universal attachment fallback lane (approved 2026-06-26)

> Detail: [`rfcs/rfc-stage3h-universal-attachment-lane.md`](rfcs/rfc-stage3h-universal-attachment-lane.md) (Ratified)

**Pain**: user uploads a liver/kidney lab report + “analyze the lab results”; the system answers warehouse historical lipids/HRV/sleep (wrong hat). Root cause is a **routing-completeness gap** — facts already dug by the generalized parse layer (`results[]`/`narratives[]`) are discarded as garbage by the hardcoded last mile (`resolve_attachment_qa_mode` kicks lab/unknown out → lands `lifestyle` warehouse).

**Two-layer lane constitution**:

| Layer | Lane | Positioning |
|-------|------|-------------|
| Layer 1 | `attachment_grounded_review` (universal fallback) | Any actionable attachment + no dedicated-lane hit → talk-about-this-image + warehouse physically isolated; **build once, permanently cover ~90% of the long tail** |
| Layer 2 | wearable_screenshot_review / lab_cross_year (dedicated enhancement) | High-frequency high-value types only; miss/fail **degrades to the universal layer, never back to lifestyle** |

**Iron law**: if this turn has an actionable attachment → **never land lifestyle**; new types only add `*.schema.json` + registry hints, **strictly forbid changing Python routing**.

| Priority | Item | Flag | Status |
|----------|------|------|--------|
| 3H-α | Universal-lane routing land + plan + warehouse-isolation forbidden | `PHA_UNIVERSAL_ATTACHMENT_LANE=1` | ✅ |
| 3H-β | `focus_summary_from_parsed` serializes `metrics[]` fact table | same | ✅ |
| 3H-γ | Dedicated-lane fail falls back to universal + declarative expand-class SOP | reuse | ✅ |
| 3H-δ | corrupt/odd family **structure-signal hard take-over** (paths + metrics/vision_summary → grounded) | same | ✅ 2026-06-27 |
| 3H-ε | Mixed stress battery + wrong-answer book + tone polish / harness telemetry | `scripts/pha_universal_attachment_stress_battery.py` | ✅ **148/148** seed=20260626 |

**Current build**: `pha-v2.3.32-full-import-only` (8788 production instance)

### 8.5 Stage 4 — offline Loop Engineering (legal lock 2026-06-27)

> Detail: [`rfcs/rfc-stage4-offline-loop-engineering.md`](rfcs/rfc-stage4-offline-loop-engineering.md) · personalization: [`rfcs/rfc-stage4b-personalization-flywheel.md`](rfcs/rfc-stage4b-personalization-flywheel.md)

| Stage | Status |
|-------|--------|
| **4-0 wall-building** | ✅ CI layered L1 + Nightly draft + D-3d-2 red/green table + dual-ring RFC |
| **4-α ring A** | ✅ harvest · 1E · distiller |
| **4-α.1** | ✅ Tier-A/B/C split · 1E-a/b/c · schema fuzzy-trigger retired · Tier-A Promote |
| **4-β-1** | ✅ `wave4b` Spec v0.1 · `chb_compiler.py` skeleton |
| **4-β-2a/b** | ✅ Harness `USER_CONTEXT_BRIEF` · Mock LLM §Interpretation |
| **4-β-2c** | 📋 T0 Ingest async write (hung) |

**Iron law**: evolution identifies coverage, does not evolve control-flow topology; Patch is Proposal PR + human review only.

---

## 9. Summary: my final stance (updated 2026-06-27)

1. **Stage 3H is physically closed**: universal attachment fallback + dedicated-enhancement fallback + corrupt structural fallback; 148/148 elastic stress all green; wrong-answer book [`anti-regression-constraints.md`](rfcs/anti-regression-constraints.md) standing red line in force.
2. **Stage 3G E2E is closed**: Bank seed=20260626 **164/164**; R0/R1 CompareTable/numerics audit landed; R2 Shadow quality scoring still backlog.
3. **Next priority (P0)**: **on-device 6-image E2E golden** (C-1/C-2) + **Stage 4-β-2c** (T0 Ingest async write) + Wave 4a OSS gate.
4. **Observation**: Telemetry operations (`L0_L3_Alignment_Rate`) still ⏳; see [`telemetry-review-playbook.md`](telemetry-review-playbook.md).
5. **OSS Public Gate**: 4a CI all-green + 3d wearable golden + 3H stress regression into CI.
6. **CHB (Wave 4b)**: [`wave4b-chronic-health-brief-spec.md`](wave4b-chronic-health-brief-spec.md) v0.1 ✅; `pha/chb_compiler.py` 4-β-1 ✅; 4-β-2a/b Harness slot hang + Mock LLM ✅.

---

## Appendix A: mapping to existing documents

| Existing document | Relationship |
|-------------------|--------------|
| [`doc-roadmap-v2.3.md`](doc-roadmap-v2.3.md) | **Doc registry + TODO master list** (2026-05-30) |
| `harness-evidence-matrix.md` | Stage 1 needs Profile trigger-source update |
| `harness-catalog-v2.2.7.md` | Stage 2 MC is its “catalog compression” extension |
| `harness-dch-p1.6.md` | DCH coexists with MC; DCH still owns this-turn bait |
| `storage/schemas/README.md` | A+ intent-block governance entry |
| [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md) | Wave 3d-γ Compare SSO |
| [`wearable-interpretation-policy-v1.md`](wearable-interpretation-policy-v1.md) | 3d-ε interpretation boundary |
| [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md) | 3d-δ Metric Registry |
| [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md) | Wave 3c/3d wearable dedicated |
| [`stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) | Stage 3C multi-turn (Approved) |
| [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) | Stage 3F Goal + Arbiter (Approved 2026-06-17) |
| [`rfcs/rfc-stage4-offline-loop-engineering.md`](rfcs/rfc-stage4-offline-loop-engineering.md) | Stage 4 dual-ring Loop (Ratified 2026-06-27) |
| [`rfcs/rfc-stage4b-personalization-flywheel.md`](rfcs/rfc-stage4b-personalization-flywheel.md) | Personalization flywheel CHB+T0 (Ratified 2026-06-27) |
| [`rfcs/stage3d-wearable-e2e-checklist.md`](rfcs/stage3d-wearable-e2e-checklist.md) | 3d on-device red/green E1–E8 (v1.0) |
| [`pha-pm-constitution.md`](pha-pm-constitution.md) | Higher law |

## Appendix B: recommended review order

1. [`doc-roadmap-v2.3.md`](doc-roadmap-v2.3.md) — current TODO and doc priority  
2. [`stage3d-wearable-merge-and-gates-spec.md`](stage3d-wearable-merge-and-gates-spec.md) (TBD) — 3d acceptance legal  
3. [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md) — wearable Harness contract  
4. [`wave4a-open-source-readiness-spec.md`](wave4a-open-source-readiness-spec.md) (TBD) — OSS gate  
5. [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) — Perception Worker master RFC  
6. [`telemetry-review-playbook.md`](telemetry-review-playbook.md)

# Metadata Catalog v2.3 — design RFC (hybrid registry · Stage 2)

> **Language / 语言**：English (this document) · [中文](metadata-catalog-v2.3.md)

> **Status**: Design RFC — **awaiting Review; encoding forbidden**  
> **Baseline build**: `pha-v2.2.12-manifest-tier-v1` (Stage 1 closed)  
> **Related**: [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md), [`manifest-tier-v1.md`](manifest-tier-v1.md)  
> **Revision date**: 2026-05-24 · **v2.3.3 final-review merge edition**  
> **External review**: Grok Stage2 9.0/10 + Stage1 9.4/10; Gemini final review **fully accepts** Discover→Promote and CI preset templates  
> **Encode gate**: three-party architecture Review is closed; **2A code** starts only after chief designer Wenhui explicitly confirms in §12 of this document

---

## 0. Purpose of this document and Cursor’s independent stance

### 0.1 The core question Wenhui raised (must be answered head-on)

> Supplements are only one facet of a user’s health background; medications, herbs, lifestyle memos, and more will all grow. If the catalog hardcodes “supplements”, must we change code every time we add a class?

**Conclusion (actionable)**:

| Ask | Can we do it | How |
|-----|--------------|-----|
| Stop treating “supplements” as the only Context semantics | ✅ | Abstract the asset domain as **`user_context` (user background memo)**; supplements / meds / symptoms are all **category subclasses**, not independently hardcoded lanes |
| Add a Context-class asset without changing Python | ✅ (conditional) | Add `storage/schemas/*.schema.json`, reuse the generic fetch adapter (see §3) |
| Add a Data-class asset (new lab / wearable aggregate) | ⚠️ usually needs an adapter | Still Schema contract + optional offline-distilled keywords; **not** runtime LLM inventing tables |
| “Whatever the user says auto-grows” with zero ops | ⚠️ Stage 2 **merge** | See §5 **Discover → Capture → Promote**; **forbid same-turn** menu entry without ground truth |

### 0.2 v2.3.2 response to Grok / Gemini Review (merged rulings)

| Review comment | Ruling | Written in |
|----------------|--------|------------|
| When Layer B truncates, **degrade Context first**, keep Data | ✅ adopt | §7.2 |
| **Dynamic priority** = `intent.priority` + `mention_score` | ✅ adopt (mention computed deterministically, not LLM) | §7.2 |
| Shadow **smart sampling** (combined 10–20%, casual 0%) | ✅ adopt | §8 |
| `shadow_confidence_threshold` high-priority telemetry | ✅ adopt | §8 |
| MC default Tier1; only `FORCE_TIER0=1` enters Tier0 | ✅ adopt | §7.4 |
| Inaccurate MC descriptions → golden + Top-20 human Review | ✅ adopt | §9 |
| Roadmap: 2A telemetry → 2B dynamic+base → 2C MC → 2D Shadow | ✅ adopt (same as Cursor’s original 2A; **2B promoted**) | §10 |
| Hybrid dynamic catalog **in Stage 2 design** | ✅ adopt | §5, §6 |
| Grok: `universal_health_assets.json` as **runtime dual source of truth** | ❌ veto | §6 — change to **preset template + CI validate** |
| Gemini: **same-turn** LLM writes `dynamic_slots.json` into the menu | ❌ veto | §5 — **next-turn promote** + Existence Veto |
| Gemini: MC English-only one-liner | ❌ correct | §7.3 — **bilingual sandbox**; dynamic slots keep `title_zh` |
| Do not merge MC with EVIDENCE_CATALOG | ✅ three-party agreement | §7.1 |

**Merged definition of “dynamic” (greatest common divisor of Wenhui/Grok/Gemini)**:

```text
user mentions a new asset → Discover (proposal) → Capture (write DB) → Existence pass → Promote (next turn into Registry/MC/menu)
                              ↑ async 1.5B structured extract             ↑ physical lock          ↑ not same-turn hallucination register
```

### 0.3 Judge’s notes on Grok / Gemini original proposals (historical record)

**Adopt**:

1. **Two-layer (actually three-layer) registry**: static domain ontology + executable asset contract + user override layer.  
2. **Existence Veto (data-existence veto)**: no ground truth, not in this-turn Catalog menu.  
3. **Code-name menu ≤400 token**: round 1 sees only `asset_id` codes, not field details.  
4. **Lossless integration with TurnEvidencePlan / SchemaIntentRouter**: L0 stays deterministic; MC is read-only.

**Veto or demote**:

| Proposal | Problem | Stage 2 handling |
|----------|---------|------------------|
| `universal_health_assets.json` and `*.schema.json` as **dual sources of truth** | Dual slot lists will inevitably drift | **Single source of truth = `*.schema.json`**; domain-ontology JSON is rollup metadata or a CI artifact only |
| Each slot bound to its own SQLite table (`user_med_metabolic`…) | **Does not match** live `user_health_background_notes(category=…)` | Unify `data_source` contract as an **existence probe** expression; see §4 |
| Runtime LLM **same-turn register** into the menu | 7B hallucination flood | **Forbid**; allow **async Discover proposals**, **next-turn Promote** (§5) |
| Gemini one-shot “exhaust 150+ slots” JSON | Maintenance-entropy explosion; duplicates the A+ Schema path | Domain ontology lists **domain + templates** only; metric detail stays in each Schema `metrics` |

### 0.4 Live facts (design must align, not invent)

- Context data already lives in **`user_health_background_notes`**, field `category` includes: `supplement` / `medication` / `sleep_lifestyle` / `symptom` / `general`.  
- Asset `supplement_bg` display still says “supplements”, but `trigger_keywords` already include **medication, fixture-med, fixture-med-C**, etc.; the bottleneck is **asset ID and domain labels** still being supplement-narrative, not that the data model only supports supplements.  
- `UniversalCatalogManager` already **hot-loads** `storage/schemas/*.schema.json` — that is PHA’s “open platform” kernel; Stage 2’s job is **registry semantic upgrade + menu compression + existence veto**, not a second Catalog codebase from scratch.

---

## 1. Problem statement (revised)

| Pain | Status quo | Stage 2 goal |
|------|------------|--------------|
| Context misread as “supplements-only” | `supplement_bg` naming + `include_supplement_catalog` API | Domain model **`user_context.*`**; API semantics become **regimen/catalog_mount** |
| New med / new memo types | Changing schema JSON is enough, but no standard template | **Context asset template** + domain-ontology docs |
| Prompt bloat | combined Task + Catalog + Manifest | MC ≤400 token; **code-name menu** |
| Hallucinated empty menu | Context fetch can enter Catalog with no rows | **Existence Veto** |
| Routing unobservable | No JSONL `numerics_audit` | 2A telemetry first |

---

## 2. Three-tier registry constitution (hybrid dynamic catalog)

```text
┌─────────────────────────────────────────────────────────────────┐
│ Tier C · user override layer (per-user, optional)                 │
│   storage/users/{user_id}/dynamic_context_assets.json            │
│   only “promoted” custom slots; must carry data_source + existence │
└───────────────────────────▲─────────────────────────────────────┘
                            │ merge (startup / per-user cache)
┌───────────────────────────┴─────────────────────────────────────┐
│ Tier B · evidence asset contract (SOURCE OF TRUTH · executable)   │
│   storage/schemas/*.schema.json                                   │
│   UniversalCatalogManager hot-load → routing / Catalog / Fetch / MC│
└───────────────────────────▲─────────────────────────────────────┘
                            │ rollup / docs / CI validate
┌───────────────────────────┴─────────────────────────────────────┐
│ Tier A · domain ontology (read-only reference, not a second router)│
│   storage/registry/universal_health_domains.json (design path)    │
│   defines display, priority of lab / wearable / user_context / …  │
│   **does not** enumerate fish_oil, metformin, etc. detail slots   │
└─────────────────────────────────────────────────────────────────┘
```

**Merge rules (v2.3.2)**:

```text
effective_assets = Tier_B_schemas
  + Tier_C_promoted_dynamic (status=promoted, maps_to legal)
Router / L0 still read-only Tier_B (unchanged)
MC index may read effective_assets
EVIDENCE_CATALOG menu = candidates ∩ existence_probe (includes promoted dynamic)
```

**Forbid**: Tier A driving Catalog rows alone; a Tier A entry missing the matching Tier B schema → CI fail.

---

## 3. Generalizing the Context domain: from “supplement catalog” to “user background memo”

### 3.1 Domain definition

| Domain ID | Meaning | Typical category (DB) | asset_class |
|-----------|---------|-----------------------|-------------|
| `lab` | Lab Data | — | data |
| `wearable` | Wearable time-series Data | — | data |
| `user_context.regimen` | Supplements + Rx + OTC + herbal regimens | supplement, medication | context |
| `user_context.lifestyle` | Sleep / diet / exercise habits | sleep_lifestyle | context |
| `user_context.symptom` | Symptom / allergy memos | symptom, general | context |

**Live `supplement_bg` evolution path (encode period, not tonight)**:

- **Short term**: keep `asset_id=supplement_bg` (compat); change `display.title_zh` to “medication / supplement / regimen background”; `category` metadata `user_context.regimen`.  
- **Mid term**: optionally add `medication_regimen.schema.json`, **share fetch adapter** with `supplement_bg`, `catalog.filter_categories: ["medication"]`; mount by intent score in combined.  
- **Forbid**: adding `if supplement` / `if medication` lane branches in Python.

### 3.2 Generic Context-asset Schema template (new asset = copy JSON)

```json
{
  "asset_id": "medication_regimen",
  "category": "user_context",
  "context_domain": "user_context.regimen",
  "intent": { "asset_class": "context", "priority": 6, "trigger_keywords": [] },
  "catalog": {
    "enabled": true,
    "profiles": ["combined_review"],
    "conditional": true,
    "catalog_min_score": 2.0
  },
  "fetch": {
    "mode": "adapter",
    "adapter": {
      "module": "pha.chat_background",
      "callable": "build_user_background_block",
      "params": { "categories": ["medication", "supplement"], "max_chars": 1200 }
    }
  },
  "existence": {
    "probe": "sqlite_notes",
    "table": "user_health_background_notes",
    "where": { "category_in": ["medication", "supplement"] },
    "min_rows": 1
  }
}
```

**Zero-Python-extension condition**: fetch still goes through existing `build_user_background_block`; only the schema adds `params` / `existence` blocks (encode period implements a generic probe).

### 3.3 Relation to SchemaIntentRouter

- Router still scores **each asset_id**; Data > Context unchanged.  
- `include_supplement_catalog` evolves to **`include_context_regimen_catalog`** (semantics: whether to mount regimen-class Context entries).  
- **Profile selection does not read** Tier A domain JSON.

---

## 4. Existence Veto (data-existence veto) — adopt Gemini’s physical lock

### 4.1 Principle

> The model or registry may “know” a class of asset exists, but **this-turn Catalog menu** only shows entries for which **this user already has ground truth**.

### 4.2 `existence` contract (written on every schema)

| probe type | Meaning | Example |
|------------|---------|---------|
| `sqlite_notes` | `user_health_background_notes` has rows | Context regimen |
| `sqlite_metric` | A metric table has data | lab/wearable |
| `patient_state` | Patient State fragment non-empty | ledger field |
| `always` | Skip veto (use sparingly, Data default assets only) | lab_lipid_panel |

**Veto pseudo-code**:

```text
FOR each catalog_candidate IN ranked_assets:
  IF NOT existence_probe(user_id, asset.existence):
    SKIP from EVIDENCE_CATALOG lines  # not into menu
    LOG catalog_veto_reason in HarnessBuildReport
  ELSE:
    EMIT menu line
```

### 4.3 Boundary with Grok “dynamic discovery”

- User chat mentions “metformin” → **background capture** writes DB (already exists) → next-turn existence passes → menu shows a regimen-class entry.  
- **No need** for the LLM to register a new asset_id.  
- User mentions “hometown herb XYZ” with no DB record → **not into the menu**; LLM may say in the reply “not recorded yet; you can add it”.

---

## 5. Universal Dynamic Slots Registry (dynamic-slot register · Stage 2 merge core)

> **Module name (encode period)**: `pha.dynamic_slot_registry` (design path, corresponding to Gemini’s `dynamic_slot_registry.py`)  
> **Principle**: every health asset (supplements, meds, genes, allergies, lifestyle) is a **Slot** in the Registry; extension is **config + data**, not business `if supplement`.

### 5.1 Three-state lifecycle (Discover → Capture → Promote)

| Status | Meaning | When it enters menu / MC |
|--------|---------|--------------------------|
| `pending_discovery` | LLM/rules extracted a candidate; no DB ground truth yet | **No** |
| `captured` | `background capture` already wrote notes / metric | **No** (this turn) |
| `promoted` | Passed Existence Veto + mapping check | **Yes (from next turn)** |

**Same-turn invariant (physical lock, Gemini adopted)**:

```text
EVIDENCE_CATALOG rows ⊆ { promoted slots } ∩ existence_probe(user_id) == true
```

### 5.2 UserIntentDiscoveryHook (design hang point)

```text
After user message is persisted (may run parallel with capture; does not block SSE first token):
  IF PHA_DYNAMIC_SLOT_DISCOVERY=1:
    discovery_job(user_message)   # default 1.5B sidecar or rules, not main 7B path
      → emit discovery_proposal JSON
      → write storage/users/{uid}/dynamic_slots.json (status=pending_discovery)
  IF capture writes DB successfully:
    mark matching proposal as captured
  IF existence_probe passes AND maps_to is legal:
    mark promoted → merge into effective_assets (in-process cache; visible on next request)
```

**Forbid**:

- Discover results **directly** changing L0 `SchemaIntentRouter` Profile.  
- Discover results **same-turn** injecting Tier0 / triggering fetch.  
- Promoting a slot with no `maps_to_domain` / no adapter template (prevent `jiuzhuan_jindan`).

### 5.3 `discovery_proposal` and `promoted slot` JSON Spec

**Proposal (pending)**:

```json
{
  "slot_id": "herbal_tea_regimen",
  "domain": "user_context.regimen",
  "title_zh": "草药茶饮方案",
  "title_en": "Herbal tea regimen",
  "mention_tokens": ["草药", "茶饮"],
  "maps_to_asset": "supplement_bg",
  "maps_to_domain": "user_context.regimen",
  "status": "pending_discovery",
  "discovered_at": "2026-05-24T12:00:00Z",
  "confidence": 0.71,
  "source": "discovery_hook:1.5b"
}
```

**Promoted** — extra fields:

```json
{
  "status": "promoted",
  "promoted_at": "2026-05-24T12:05:00Z",
  "existence": { "probe": "sqlite_notes", "category": "general", "min_rows": 1 },
  "promotion_reason": "capture+existence"
}
```

**Mapping rules**:

| Case | Handling |
|------|----------|
| Hits an existing Tier A/B asset (e.g. metformin mention) | `maps_to_asset=supplement_bg` or `medication_regimen`; **do not create** a new slot_id |
| Long-tail Chinese memo (hometown herb) | New `slot_id`, but must `maps_to_domain` + reuse `chat_background` adapter |
| Proposes a brand-new Data table (e.g. CGM) | Stage 2 **does not promote**; log telemetry `discovery_unmapped`; Stage 4 offline adds schema |

### 5.4 Alignment with Grok’s “zero-code” claim

| Grok wording | PHA landing |
|--------------|-------------|
| New assets need no core-code change | **Context long tail**: yes (template + dynamic_slots + same adapter) |
| Need only data tables | **Yes** — live `user_health_background_notes`; not one table per drug |
| LLM auto-generates Slot config | **Half-true** — LLM generates a **proposal**; **promote** is completed deterministically by Existence + mapping |
| Dynamic Slots merge into MC | **Yes** — `effective_assets = schemas + promoted_dynamic` (§2) |

### 5.5 Feature Flags (dynamic discovery)

| Variable | Default | Notes |
|----------|---------|-------|
| `PHA_DYNAMIC_SLOT_DISCOVERY` | `0` | 1=enable Discover Hook |
| `PHA_DYNAMIC_SLOT_AUTO_PROMOTE` | `1` | Auto-promote after capture+existence (still not same-turn menu) |
| `PHA_USER_DYNAMIC_SLOTS` | `0` | Read per-user `dynamic_slots.json` |

### 5.6 Dynamic Slot admission Checklist (Grok suggestion · must pass before Promote)

> **Purpose**: keep low-quality / hallucinated slots out of `effective_assets` and MC; **all must pass** before `status=promoted`.

| # | Check | On fail |
|---|-------|---------|
| 1 | `maps_to_domain` belongs to a Tier A registered domain | Refuse Promote, log `discovery_unmapped` |
| 2 | `maps_to_asset` is empty **or** points at an existing schema asset | If unmapped, must bind the generic `chat_background` adapter template |
| 3 | `existence.probe` returns true for this `user_id` | Stay `captured`, not into menu |
| 4 | `title_zh` **non-empty** (hard requirement for Chinese UX; Gemini/Grok agree) | Refuse Promote |
| 5 | `title_en` recommended non-empty (MC bilingual row) | warning only |
| 6 | `slot_id` matches `^[a-z][a-z0-9_]{2,48}$` and does not collide with schema `asset_id` | Refuse |
| 7 | Same-turn invariant: Promote takes effect on the **next request** | Enforced in code/tests |
| 8 | Golden sentence (optional 2B+): 1 mention-sentence dry-run does not break Profile | CI warning |

**Flood control**: per-user `promoted` dynamic slots hard-capped at `PHA_DYNAMIC_SLOTS_MAX_PROMOTED` (default **8**); overflow evicts oldest by `promoted_at`.

---

## 6. Tier A preset base: `universal_health_assets.json` (merged Spec)

> **Path (design)**: `storage/registry/universal_health_assets.json`  
> **Role**: **preset domain templates + common slot prototypes** (Grok’s large base), **not** a second runtime routing table.

### 6.1 Relation to `*.schema.json` (eliminate dual sources of truth)

```text
universal_health_assets.json  ──CI validate/generate──►  *.schema.json (truth)
         │                                              │
         └──────── runtime: read-only template index / Discover map ──┘
```

- **Runtime**: `UniversalCatalogManager` still only hot-loads `storage/schemas/*.schema.json`.  
- **Preset JSON**: provides `domain → slot_template → suggested_asset_id`; Discover **prefers mapping** onto existing assets, reducing new-id flood.  
- **CI**: every `suggested_asset_id` in the preset must have a schema; every active schema must reverse-register in the preset or be marked `runtime_only`.

### 6.2 Structure (compact edition, not Grok’s hundred-row flatten)

```json
{
  "version": "2026.05",
  "role": "preset_templates_not_runtime_menu",
  "domains": {
    "lab": {
      "display": { "zh": "化验检查", "en": "Laboratory Tests" },
      "priority": 90,
      "templates": [
        { "template_id": "lipid_panel", "maps_to_asset": "lab_lipid_panel", "tags": ["data", "cardiovascular"] }
      ]
    },
    "wearable": {
      "display": { "zh": "穿戴设备", "en": "Wearable" },
      "priority": 85,
      "templates": [
        { "template_id": "wearable_ts", "maps_to_asset": "wearable_bundle", "tags": ["time_series"] }
      ]
    },
    "user_context.regimen": {
      "display": { "zh": "用药与营养方案", "en": "Regimen" },
      "priority": 70,
      "templates": [
        { "template_id": "regimen_memo", "maps_to_asset": "supplement_bg", "tags": ["context"] },
        { "template_id": "medication_memo", "maps_to_asset": "medication_regimen", "tags": ["context"], "status": "planned" }
      ]
    },
    "user_context.lifestyle": { "display": { "zh": "生活方式", "en": "Lifestyle" }, "priority": 65, "templates": [] },
    "genomics": { "display": { "zh": "基因检测", "en": "Genetics" }, "priority": 60, "templates": [], "status": "P2" },
    "allergy": { "display": { "zh": "过敏", "en": "Allergy" }, "priority": 55, "templates": [], "status": "P2" }
  }
}
```

**Note**: Grok-list details like `fish_oil` / `metformin` **do not enter this file**; they live as **DB free text** or Discover `mention_tokens`, not one runtime slot row each.

### 6.3 File-merge strategy

Encode period **pick one**: keep only `universal_health_assets.json` (with `domains` + `templates` + `asset_bindings`), to avoid dual-file drift with `universal_health_domains.json`.

**CI rule**: every `maps_to_asset` / `asset_bindings` must have a matching `*.schema.json`; every active schema must register `context_domain`.

---

## 7. Metadata Catalog (MC) and the code-name menu

### 7.1 Split of labor: MC vs EVIDENCE_CATALOG (three-party consensus)

| Block | Role | Tier | Contains user ground truth | Orderable |
|-------|------|------|----------------------------|-----------|
| `METADATA_CATALOG` | Global phone book (static schema + **promoted dynamic**) | **Default Tier1** | No | No |
| `EVIDENCE_CATALOG` | This-turn menu (DCH + when_zh) | Tier0 | Yes (after fetch) | Yes |

**Forbid merging**; MC inject **does not change** L0 Profile / default fetch set.

### 7.2 Dynamic priority and Layer B truncation (Grok feedback merge)

**Rank score (deterministic, no LLM)**:

```text
rank_score(asset, user_message, user_id) =
    intent.priority * 10
  + mention_score(asset, user_message) * 5   # substring/keyword hit, 0~3
  + recency_bonus(asset, user_id) * 2        # last-7-day fetch/mention, 0~2
  + (0 if asset_class == "data" else -3)     # Context easier to squeeze out on truncate
```

`mention_score`: reuse Schema `trigger_keywords` + user **promoted dynamic** `mention_tokens`; **forbid** LLM real-time scoring.

**Layer A / B / C**:

```text
Layer A · domain summary (~80 token, never truncated)
  lab:1 wearable:1 ctx.regimen:1(+dyn:1) ctx.lifestyle:0

Layer B · asset rows, fill to budget by rank_score DESC
  Truncate rule (when over PHA_METADATA_CATALOG_MAX_TOKENS):
    1) first drop lowest rank_score Context rows (regimen/lifestyle/symptom)
    2) then drop low-priority Data (keep lab_lipid_panel, wearable_bundle until last)
    3) promoted dynamic: if title_zh present, Layer B uses bilingual short title “id|CTX|zh|en”

Layer C · … +N truncated (~20 token)
```

**Input set**:

```text
mc_assets = Tier_B_schemas (catalog.enabled)
          ∪ Tier_C_promoted_dynamic (status=promoted)
```

### 7.3 Code-name menu Codec and bilingual strategy (Gemini correction)

**Menu (EVIDENCE_CATALOG)** — shorter; only those that **pass existence**:

```text
【Menu·codes·≤400tok】
lab:lab_lipid_panel|wear:wearable_bundle|ctx:supplement_bg|dyn:herbal_tea_regimen
```

**MC (METADATA_CATALOG)** — may include promoted dyn rows not yet ordered:

```text
lab_lipid_panel|DATA|血脂四项|Lipid panel|combined
herbal_tea_regimen|CTX|草药茶饮|Herbal tea|combined
```

- Layer A may use **ZH/EN domain codes** (`ctx.regimen/用药方案`).  
- **Dynamically grown Chinese assets must allow `title_zh`** (continuation of Stage 1 bilingual sandbox).  
- No field details, no T0/T1 numbers.

### 7.4 Integration with TurnEvidencePlan (Grok feedback)

| Profile | MC | Menu |
|---------|----|------|
| `casual` | ❌ | ❌ |
| `wearable_only` | ❌ default | Wearable Catalog |
| `supplement_manifest` | ❌ | Context lane |
| `lab_cross_year` | ⚠️ optional | lab |
| `combined_review` | ✅ Tier1 default | ≤5 + existence |

```text
slots_tier1 += ["METADATA_CATALOG"]   # when PHA_METADATA_CATALOG=1
slots_tier0 += ["EVIDENCE_CATALOG", "NUMERICS_MANIFEST", "TASK"]  # unchanged

# A/B experiment only:
IF PHA_METADATA_CATALOG_FORCE_TIER0=1:
  slots_tier0 += ["METADATA_CATALOG"]  # must watch Tier0 fuse
```

---

## 8. Shadow Routing (smart sampling · v2.3.2)

### 8.1 Principle

- Main path: `SchemaIntentRouter` (sync, 0ms steering wheel)  
- Shadow: async, **zero-adopt**, default **off** (`PHA_SHADOW_ROUTING=0`)

### 8.2 Smart sampling (Grok feedback)

| Profile | Base sample rate | Notes |
|---------|------------------|-------|
| `casual` | **0%** | Do not sample |
| `wearable_only` | 2% | Low |
| `lab_cross_year` | **15%** | Configurable cap 20% |
| `combined_review` | **10%** | Configurable cap 20% |
| Other | 5% | Global default `PHA_SHADOW_ROUTING_SAMPLE_RATE` |

```text
effective_rate = profile_rate OR global_default
IF random() < effective_rate: enqueue shadow_job
```

Timeout `PHA_SHADOW_ROUTING_TIMEOUT_MS=800` → `disagreement_class=shadow_timeout`.

### 8.3 Confidence-layered telemetry (Grok feedback)

| Condition | JSONL mark |
|-----------|------------|
| `shadow_confidence >= PHA_SHADOW_CONFIDENCE_THRESHOLD` (default **0.7**) | `telemetry_priority=high` |
| Otherwise | `telemetry_priority=low` (still recorded; Dashboard can filter) |

**Forbid**: high confidence **does not** trigger auto-adopt or dynamic Promote.

### 8.4 HarnessBuildReport fields (2A landing)

```json
{
  "intent_route": { "authoritative_profile": "combined_review", "asset_scores": {}, "catalog_ids": [] },
  "numerics_audit": { "audit_scope": "t0_plus_disclosure", "passed": true, "violations": [] },
  "catalog_existence": {
    "candidates": ["lab_lipid_panel", "supplement_bg"],
    "vetoed": ["supplement_bg"],
    "veto_reasons": { "supplement_bg": "sqlite_notes_min_rows" }
  },
  "dynamic_slots": {
    "discovered": 1,
    "promoted": 0,
    "pending": ["herbal_tea_regimen"]
  },
  "shadow_routing": {
    "sampled": true,
    "completed": true,
    "profile_match": true,
    "shadow_confidence": 0.82,
    "telemetry_priority": "high",
    "disagreement_class": null
  }
}
```

---

## 9. Risk control and Feature Flags

| Risk | Mitigation |
|------|------------|
| Inaccurate MC description causes mis-picks | Top-20 assets **quarterly human Review** + golden dry-run covering MC rows |
| Dynamic Discover hallucination | Mapping table + Existence Veto + **not-same-turn** Promote |
| Dual-JSON source drift | CI: `universal_health_assets` ↔ schemas |
| Tier0 bloat | MC default Tier1; `FORCE_TIER0` A/B only |
| Shadow GPU contention | Smart sampling + 1.5B sidecar + default off |

| Variable | Default | Notes |
|----------|---------|-------|
| `PHA_METADATA_CATALOG` | `0` | MC |
| `PHA_METADATA_CATALOG_TIER` | `1` | Tier1 |
| `PHA_METADATA_CATALOG_FORCE_TIER0` | `0` | Set 1 only for A/B |
| `PHA_METADATA_CATALOG_MAX_TOKENS` | `400` | Hard cap |
| `PHA_CATALOG_EXISTENCE_VETO` | `1` | Menu veto |
| `PHA_DYNAMIC_SLOT_DISCOVERY` | `0` | Discover Hook |
| `PHA_DYNAMIC_SLOT_AUTO_PROMOTE` | `1` | Auto-promote after capture |
| `PHA_USER_DYNAMIC_SLOTS` | `0` | per-user JSON |
| `PHA_SHADOW_ROUTING` | `0` | **Default off until 2D** |
| `PHA_SHADOW_ROUTING_SAMPLE_RATE` | `0.05` | Global fallback |
| `PHA_SHADOW_PROFILE_COMBINED_RATE` | `0.10` | combined sampling |
| `PHA_SHADOW_PROFILE_LAB_RATE` | `0.15` | lab_cross_year |
| `PHA_SHADOW_CONFIDENCE_THRESHOLD` | `0.7` | High-priority telemetry |

**Rollback**: all Flags → 0 + `PHA_CATALOG_EXISTENCE_VETO=0` ≡ v2.2.12.

---

## 10. Implementation roadmap (Grok/Gemini/Cursor merge · after Review pass)

| Stage | Name | Content | Default switch |
|-------|------|---------|----------------|
| **2A** | Telemetry foundation | HarnessReport v1.1: `intent_route`, `numerics_audit`, `catalog_existence`, `dynamic_slots` counts | Telemetry with Harness DEBUG |
| **2B** | Dynamic discovery and base | `universal_health_assets.json` + `dynamic_slot_registry` + Existence Veto + Discover→Promote | Discovery **off** |
| **2C** | Extreme compression and Tier1 | MC cache, rank_score truncate, code-name menu, `FORCE_TIER0` A/B hook, etc. | MC **off** |
| **2D** | Shadow routing | Smart-sample Shadow + confidence layering | Shadow **off** |

**Encode-order iron law**: 2A → 2B → 2C → 2D (**observation before intelligence**; Shadow last and default off).

**2A scope boundary (encode period only; not implementing tonight)**:

- Extend `build_harness_report` / `emit_harness_build_report`: write `intent_route`, `numerics_audit` (passed in from the chat completion path), `catalog_existence` (dry-run / stream both OK).  
- **Do not** implement MC text, **do not** implement Discover Hook, **do not** implement Shadow.  
- Schema version: `pha.harness_report/v1.1` (backward-compatible; v1 missing fields).

---

## 11. Acceptance criteria

- [ ] 2A: JSONL contains `numerics_audit` + `catalog_existence`  
- [ ] 2B: Discover proposal writes `dynamic_slots.json`; **this-turn** menu does not contain pending  
- [ ] 2B: after capture, next-turn promoted row enters MC (including `title_zh`)  
- [ ] 2C: MC ≤400 token; on truncate **Data kept over Context**  
- [ ] 2C: `FORCE_TIER0=1` A/B only; default Tier1  
- [ ] 2D: combined sample ~10%, casual 0%; confidence≥0.7 marked high  
- [ ] All Flags off ≡ v2.2.12  

---

## 12. Review Checklist (v2.3.3)

### 12.1 External Review (closed)

| Reviewer | Conclusion | Key ruling |
|----------|------------|------------|
| **Gemini** | ✅ approve v2.3.2/2.3.3 direction | Retracted “same-turn register”; supports Discover→Promote + CI preset templates |
| **Grok** | ✅ RFC 9.0/10 approve with refinements | Hybrid dynamic catalog already in Stage 2; suggested admission Checklist → §5.6 |
| **Cursor** | ✅ merge landed | See §0.2 |

### 12.2 Chief-designer sign-off (Wenhui · encode-start gate)

- [ ] Accept **Discover→Promote** (same-turn invariant: menu ⊆ {promoted} ∩ existence)  
- [ ] Accept `universal_health_assets.json` = **preset templates**, `*.schema.json` = **sole source of truth**  
- [ ] Accept §5.6 **Dynamic Slot admission Checklist**  
- [ ] Accept 2A→2B→2C→2D order; Shadow **default off until 2D**  
- [x] **Explicit command to start Phase 2A encoding** (Wenhui: “approve v2.3.3 + start 2A”)

> **2A ✅** · **2B ✅** · **2C ✅** · **2D ✅** · **3A ✅** · **3A.1 ✅** `pha-v2.3.3-stage3a1-attachment-qa-governance`  
> 3A.1 spec: [`stage3a1-attachment-qa-governance.md`](stage3a1-attachment-qa-governance.md)

---

## Appendix A: migration map for Grok example JSON

| Grok concept | PHA mapping |
|--------------|-------------|
| `domains.supplement.slots` | `user_context.regimen` + schema `supplement_bg` / future `medication_regimen` |
| `domains.medication.slots` | Same regimen domain; **not** a separate SQLite table |
| `data_source: sqlite:user_med_*` | `existence.probe: sqlite_notes` + `category` |
| Dynamic LLM register | `background capture` + next-turn existence + optional Tier C promote |

## Appendix B: MC example (generalized domain labels)

```text
【Metadata Catalog · read-only · Tier1】
domains: lab:1 wearable:1 ctx.regimen:1
lab_lipid_panel|DATA|Lipid panel|combined,lab
wearable_bundle|DATA|Wearable TS|combined,wearable
supplement_bg|CTX|Regimen/meds memo|combined(conditional)
```

## Appendix C: with Manifest Tier v1

- Menu and MC **contain neither** T0 measured values **nor** T1 guideline constants  
- Disclosure protocol still lives in Task + C-layer `t0_plus_disclosure`

## Appendix D: three-party ruling contrast (for Wenhui to decide)

| Topic | Grok | Gemini | Cursor merge |
|-------|------|--------|--------------|
| Dynamic catalog into Stage 2 | Include now | 2B full involvement | ✅ 2B Discover+Promote |
| `universal_health_assets.json` | Runtime Registry | Iceberg large base | ✅ Preset templates + CI, **not** dual source of truth |
| LLM register timing | Immediate | Same-turn write JSON | ❌ **Next-turn** Promote + physical lock |
| Shadow sampling | 5% plus smart | 5% sidecar | ✅ Profile-layered, default off |
| MC language | Lean English to save tokens | Insist bilingual | ✅ Bilingual; menu shorter |
| Implementation order | 2A→MC→Shadow | 2A→2B dynamic→2C MC→2D Shadow | ✅ Same as Gemini |

## Appendix E: Cursor’s final advice to the chief designer

1. **RFC v2.3.3** can serve as the implementation Spec; Grok/Gemini final review has merged.  
2. **After confirm, start 2A only**; 2B must accept against §5 same-turn invariant + §5.6 admission Checklist.  
3. Grok’s full hundred-slot JSON → **CI distill reference**, not a runtime dual source.  
4. “Open platform” = Schema hot-load + preset templates + Discover proposals + Existence Promote.

## Appendix F: reviewer fact correction (avoid doc drift)

| Statement | Correction |
|-----------|------------|
| Grok Review “production default `t0_strict`” | **Already inconsistent with Stage 1 close-out**; live/restart scripts default **`t0_plus_disclosure`** (rollback: `t0_strict`); see `pha-architecture-evolution-v2.3.md` §1.4 |
| Gemini “start all of 2A tonight” | Gated on **Wenhui explicit confirm**; architecture Review ≠ auto-start |

# Stage 3C — Active Recall Bridge (multi-turn focus memory wakeup)

> **Language / 语言**：English (this document) · [中文](stage3c-active-recall-bridge.md)

> **Version**: v0.2 (2026-05-26)  
> **Status**: 🔒 **Spec locked** (Gemini final review unanimous) · **code after Wenhui start-work confirm**  
> **Review**: Wenhui · Gemini joint review judges · Cursor architecture recheck (anti-hardcoding amendments merged)  
> **Depends on**: [`stage3c-episodic-evidence-bridge.md`](stage3c-episodic-evidence-bridge.en.md) · [`session_turn_focus`](../../pha/session_turn_focus.py) · Harness Tier0 assembly  
> **Related**: [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) §9 · [`telemetry-review-playbook.md`](telemetry-review-playbook.md)

---

## 0. Problem

| Symptom | Root-cause layer |
|------|--------|
| Turn 3 “take with a fixture-med” drops turn-1 PS 100mg ledger | **L3 attention decay** + Tier0 long-context noise, not a routing drop |
| Later turns negate earlier ones; invent interactions when aligning with a fixture-med | **K-layer Lookup not forced** + no “pinned fact anchor” |
| `session_focus_active` still true but the model “forgot what we were talking about” | Focus TTL only governs the **lane**, not **grip** |

**Already solved (not this Spec)**: R2 dropping to `lifestyle` → `attachment_episodic_bridge` default lane; OCR≥25 short-circuit retired.

**This Spec solves**: inside the focus lifetime, **force re-inject already-audited structured facts** every turn into the model’s attention hot zone (immediately above the user’s latest question).

---

## 1. Alignment and difference vs Claude Code Active Recall

| Dimension | Claude Code (concept) | PHA target |
|------|---------------------|------------|
| Memory source | assertions distilled from the task | **C layer only**: `LabelLedgerV1`, Patient State slices, DATA_AVAILABILITY rows |
| Who writes memory | background compress/tag | **forbid L3 write**; optional **1.5B routing** only decides “which cards to wake”, does not generate content |
| When to wake | on-demand recall | **minimum wakeup every focus turn** + **expanded wakeup** on intent hit |
| Inject position | near current turn | Harness **`RECALL_FOCUS`** protected slot, assembled **immediately above the USER question** (Bottom-Anchor) |
| Vs vector Recall | can coexist | existing `RECALL` slot (history snippets) still **forbidden** on attachment profiles; this mechanism is an **independent slot** |

---

## 2. Architecture necessity ruling

### 2.1 Is it necessary?

| Argument | Ruling |
|------|------|
| episodic_bridge already injects ATTACHMENT_LABEL | **insufficient**: when Tier0 compresses and Manifest/BG grow, 7B still misses ledger rows |
| Lengthen `focus_summary` | **insufficient**: fights the Tier0 budget; not an attention anchor |
| Fully depend on 1.2B/1.5B to remember the dialog | **reject**: small models **must not** generate medical-assertion content (hallucination + unauditable) |

**Conclusion**: under **M4 + 7B + multi-turn focus**, **L2.5 Active Recall is necessary**, but as **C-layer assertion replay**, not a second chat-memory system.

### 2.2 Compatible with current architecture?

| Existing component | Relation |
|----------|------|
| `session_turn_focus` | `ActiveRecallLedger` **mounts the same `session_id`**; TTL destroys together |
| `SchemaIntentRouter` / `qwen2.5:1.5b` shadow | optional **`recall_plan`** output: wakeup config ids, **does not** write assertion copy |
| `attachment_episodic_bridge` | every turn Tier0 **must** contain `RECALL_FOCUS` (new slot) |
| `build_preselected_grounded_hits` | one source of clinical-baseline assertions |
| P/F/K | assertions have **no brand whitelist**; F-layer E2E may assert the `anchored_asset` string |

### 2.3 Can it fix Gemini’s R3 crash?

| Can solve | Cannot solve alone |
|--------|----------------|
| 7B forgetting “current asset = PS 100mg” | L0 ledger itself is wrong (needs 3B-β) |
| Inconsistent asset description across turns | Invention when there is no K-layer `lookup_interactions` |
| Interaction questions not citing “on a fixture-med” | Claiming “you are taking” when the ledger has no fixture-med |

**Need the combo**: Active Recall (fact anchor) + **K-layer interaction Lookup** (§6) + G1–G6 low-confidence refuse.

---

## 3. Anti-corruption constitution (hard red lines · final-review law)

> **2026-05-26 Gemini final review**: the following three vs Cursor-dissent amendments are **unanimously locked**, priority above the rest of this Spec.

### 3.1 Three final-review locks (Anti-Hardcoding Locks)

| Lock | Law | Forbidden |
|------|------|------|
| **L-1 trigger** | Recall expand is decided **only** by `SchemaIntentRouter` intent family + `focus_tokens` + MC `trigger_keywords` | **any** drug-name/phrase table in production (`["药物项A","吃"]` etc.) |
| **L-2 body** | Assertion `text` is **100%** from `LabelLedgerV1` or a warehouse row **already injected into this-turn Tier0** | 7B / 1.5B **writing or rewriting** assertion bodies |
| **L-3 low-insurance** | Inside focus TTL **`anchored_asset` is forced into `RECALL_FOCUS` every turn** (when ledger is high) | “only recall the ledger when a trigger word hits” selective amnesia |

`recall_plan` (optional 1.5B) outputs **only** a strategy enum, e.g.:

```json
{ "recall_plan": ["anchored_asset", "clinical_baseline", "interaction_context"] }
```

Meaning is “**which existing cards to pull from the Ledger**”, **not** letting the model generate new sentences. `anchored_asset` is **always in the list by default** inside focus; Shadow must not omit it.

### 3.2 General red lines

1. **Assertions must be traceable**: `source_slot`, `source_turn`, `evidence_id` (if any).
2. **Forbid L3 / Assistant writing back the Ledger**.
3. **Forbid full history replay**: ≤ **8** assertions, each ≤ **120** chars.
4. **Division**: `RECALL` = history snippets; `RECALL_FOCUS` = **audited-fact Bottom-Anchor**.

### 3.3 Constitution-level refuse when ledger is low

- No `assert_anchored_asset` (`parse_confidence != high` or a G* hit) → **must not** use Recall to invent ingredients/brand.
- Take §8 refuse template + intent protection; R3 interaction questions **same**.

---

## 4. `ActiveRecallLedger` Schema (session-level · memory or SQLite)

```json
{
  "session_id": "…",
  "focus_session_id": "focus_20260527_001",
  "turns_remaining": 2,
  "assertions": [
    {
      "id": "assert_anchored_asset",
      "kind": "anchored_asset",
      "text": "当前焦点资产（定账）：Phosphatidyl Serine 100 mg；Choline 100 mg；Inositol 50 mg。品牌：NOW。",
      "source_turn": 1,
      "source_slot": "ATTACHMENT_LABEL",
      "parse_confidence": "high",
      "immutable": true
    },
    {
      "id": "assert_clinical_snippet",
      "kind": "clinical_baseline",
      "text": "档案摘录：LDL 偏高（见 Patient State 行 2025-xx-xx）；未注入全表。",
      "source_turn": 2,
      "source_slot": "PATIENT_STATE_LAB",
      "immutable": false
    }
  ],
  "recall_plan": ["anchored_asset", "clinical_baseline"]
}
```

> `recall_plan` is a **string array** (strategy ids), not natural language; `anchored_asset` is **required by default** in a focus session (see §3.1 L-3).

| `kind` | Write timing | Source |
|--------|----------|------|
| `anchored_asset` | after Turn1 `parse_confidence=high` | `label_ledger` render, **not** marketing OCR rows |
| `clinical_baseline` | `episodic_bridge` and Patient State/Manifest non-empty | **only rows already injected into Tier0** |
| `interaction_context` | K-layer lookup hit | `catalog.lookup_interactions` result summary |
| `user_stated_constraint` | user explicit self-report (optional P2) | must `source=USER_MESSAGE` + truncated original |

**Destroy**: `turns_remaining <= 0` or `merge_family_conflict` → clear Ledger.

---

## 5. Write pipeline (C layer · deterministic)

```text
Turn N finishes L0.6 ledger / Harness assembly
        │
        ▼
upsert_assertions_from_slots(slot_contents, parsed_payload)
        │
        ├─ high + ingredient_rows≥1 → assert_anchored_asset (overwrite same id)
        ├─ episodic_bridge + numerics/wearable rows → assert_clinical_snippet (merge dedupe)
        └─ lipid_bridge + LDL snapshot → assert_clinical_snippet (optional lipid-specific sub-kind)
```

**Forbidden**: write assertions back from assistant free text (anti-pollution).

---

## 6. Wakeup and inject (L2 / L2.6 Harness)

### 6.1 Golden low-insurance memory (L-3 · forced every turn)

| Condition | `RECALL_FOCUS` content |
|------|---------------------|
| `session_focus_active` and `assert_anchored_asset` exists | **must** inject (no trigger word, no Shadow approval) |
| ledger low / no assert | **do not inject** a forged asset row; refuse |
| `profile ∈ {attachment_episodic_bridge, attachment_asset_qa, …}` | enable `RECALL_FOCUS` slot |

### 6.2 Expanded cards (recall_plan · pull only ids already in Ledger)

| Strategy id | Rule trigger (deterministic · no drug-name table) | Injected assertion |
|---------|------------------------------|----------|
| `anchored_asset` | **always true** inside focus (after high ledger) | ledger render text |
| `clinical_baseline` | `profile=episodic_bridge` and this-turn Tier0 contains Patient State/Manifest/Availability rows | `assert_clinical_snippet` |
| `interaction_context` | `SchemaIntentRouter` → `medication_interaction` (or MC equivalent intent block) | K lookup summary; **omit if no lookup; forbid L3 invention** |

**1.5B Shadow (optional · AR-4)**: only suggest a **subset** of the `recall_plan` array (with `anchored_asset` already forced); default **rule engine** overrides Shadow; Telemetry compares disagreement rate.

### 6.3 Bottom-Anchor and Lost-in-the-Middle

7B attention is **U-shaped**: Prompt-**top** System Recall is washed out after long History inject. So **`RECALL_FOCUS` physical position = immediately above the current user question** (not the top of Tier0).

```text
==================== history decay zone ====================
[Turn1] upload ledger (already shifted up, starting to fade)
[Turn2] long reply / Manifest / SUPPLEMENT_BG noise
====================================================

┌──────────────────────────────────────────────────┐
│ RECALL_FOCUS (protected · last to sacrifice on trim) │
│ 【焦点记忆 · 勿与下文矛盾】                        │
│ 1. currently locked asset: {anchored_asset}        │  ◄── U-shape bottom hot zone
│ 2. clinical baseline excerpt: {clinical_baseline} (if any) │
│ 3. interaction lookup: {interaction_context} (if any)     │
└──────────────────────────────────────────────────┘

[Turn N] current user question: ……
```

Tier0 **upper** may still keep a compressed `ATTACHMENT_LABEL`; **legal force** is `RECALL_FOCUS` (KGI drift detection vs `anchored_asset`).

**RECALL_FOCUS template (C layer · no arrow symbols)**:

```text
【焦点记忆 · 本轮必须承认的事实 · 勿与下文矛盾】
1. {assert_anchored_asset.text}
2. {assert_clinical_snippet.text}   （若有）
3. {interaction_context.text}       （若有，来自档案 lookup）
```

### 6.4 Anti-patterns

| ❌ | ✅ |
|------|-----|
| Stuff the full Ledger into the top of Tier0 | Bottom-Anchor + ≤8 items |
| `recall_triggers: ["药物项A","吃"]` hardcoded table | Schema intent + focus_tokens |
| Every turn let 7B summarize “what we just talked about” | C-layer assertion replay |

---

## 7. Telemetry & KGI

| Field | Notes |
|------|------|
| `recall_assertion_ids` | assertion ids injected this turn |
| `recall_plan` | enum |
| `recall_focus_chars` | RECALL_FOCUS char count |
| `l0_l3_asset_drift` | assistant ingredients/brand disagree with `assert_anchored_asset` → violation |

**KGI**: `Focus_Recall_Hit_Rate` = share of focus turns that inject `anchored_asset` (target ≥0.95).

---

## 8. E2E acceptance (F layer · extend existing plan)

In the multi-turn script (planned) of [`stage3b-e2e-real-label-fixture.md`](stage3b-e2e-real-label-fixture.en.md):

| Turn | User sentence | Assert |
|------|--------|------|
| R1 | two images + what is it / help | `ledger.ingredient_rows >= 3` |
| R2 | which body metrics can it raise | `profile == attachment_episodic_bridge`; `RECALL_FOCUS` contains PS/Choline |
| R3 | side effects with a fixture-med | `recall_plan == interaction_risk`; assistant **contains** PS; **contains** fixture-med only if Patient State has a record; `l0_l3_asset_drift == false` |

**Before impl**: human-verify the `RECALL_FOCUS` block via Harness DEBUG excerpt.

---

## 9. Relation to 3B-β / media-route

- **L0.6 ledger** is the **only authority** producing `anchored_asset` assertions; ledger low → assertion empty; Recall does not invent.
- **Media-route** is **orthogonal** to Active Recall: the former is “read correctly”; the latter is “don’t forget across turns”.

---

## 10. Multi-agent boundary (L0 → L2.6 · no internal waste)

| Agent / module | Layer | Duty | Forbidden |
|--------------|-----|------|------|
| Perception Worker | L0.1–L0.4 | media-route → unified IR | business-family pre-route |
| Ledger + P gates | L0.6 | upsert `anchored_asset` on `high` | hard-answer on low confidence |
| Shadow Policy | L2.5 | read-only; output `recall_plan[]` | write assertion bodies |
| Harness Guard | L2.6 | `RECALL_FOCUS` Bottom-Anchor concat | let L3 pick its own memory |
| K Catalog | K | `lookup_interactions` → `interaction_context` | ingredient if-else |
| Master LLM | L3 | natural-language polish | change dose / change ledger |

---

## 11. Implementation waves and start-work gate (adjusted plan)

> **Scientific order**: **read correctly first (L0 high) → then remember (L2 Recall) → then don’t invent (K Lookup)**  
> **Gate**: **do not write AR-1/2 production code before Wave 1 green**; execute after Wenhui replies “confirm start”.

### Wave 0 — Spec close ✅

- This doc v0.2 + cross-refs to 6 related Specs
- Gemini three final-review locks written into §3.1

### Wave 1 — P0 perception-ledger green (blocks AR assertion quality)

| Item | Delivery | Done when |
|------|------|----------|
| **P0-E1** | media-route + post `document_family` coding | Spec §7.0–§7.8 |
| **P0-E2** | `pha_e2e_attachment_label_real.py` + desensitized 6800/6801 | R1: `parse_confidence=high` + F-layer golden; or documented WARN |
| **P0-E3** | Telemetry: `media_route`, `document_family` | observable in Harness / attach logs |

### Wave 2 — AR-1 / AR-2 Harness (pending start-work code)

| Item | Delivery | Depends on |
|------|------|------|
| **AR-1** | `ActiveRecallLedger` upsert + Focus TTL sync | Wave 1 R1 high |
| **AR-2** | `RECALL_FOCUS` slot + Bottom-Anchor assembly + `recall_*` Telemetry | AR-1 |
| **AR-2b** | `Focus_Recall_Hit_Rate` · `l0_l3_asset_drift` KGI | AR-2 |

### Wave 3 — AR-3 K layer (Spec-only first · code may lag)

| Item | Delivery | Notes |
|------|------|------|
| **AR-3-Spec** | Medication interaction intent block + `lookup_interactions` contract | 📋 [`stage3c-k-interaction-lookup-backlog.md`](stage3c-k-interaction-lookup-backlog.en.md) |
| **AR-3-Code** | `interaction_context` assertion backfill | after Wave 2 is stable |

### Wave 4 — AR-4 / AR-5 enhancements

| Item | Delivery |
|------|------|
| **AR-4** | 1.5B `recall_plan` Shadow (rules first) |
| **AR-5** | `pha_e2e_attachment_multiturn.py` R1–R3 |

### Start-work checklist (for Wenhui confirm)

- [ ] Accept §3.1 three final-review locks
- [ ] Accept Wave 1 before AR-1/2 coding
- [ ] Provide or approve desensitized 6800/6801 paths
- [ ] Reply “confirm start AR-1” or adjust waves

---

## 12. Revision log

| Date | Version | Notes |
|------|------|------|
| 2026-05-26 | v0.1 | First draft: Claude Code Active Recall alignment; C-layer assertions; Bottom-Anchor; small model only recall_plan |
| 2026-05-26 | v0.2 | Gemini final review: L-1/L-2/L-3 locked; `recall_plan` as array; low-insurance every turn; Wave 1–4 and start-work gate |

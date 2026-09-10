# PHA Harness Tier0 fuse policy — v2.2.6.1 design doc

> **Language / 语言**：English (this document) · [中文](harness-tier0-fuse-v2.2.6.1.md)

> **Status**: v2.2.6.1 coded — Tier0 budget assembly + Protected SLA  
> **Scope**: Tier0 budget assembly + tool-status copy correction + `tier0_integrity` observation  
> **Out of scope**: Metadata Catalog, dual-entry unification, merely raising `SYSTEM_CONTENT_MAX_CHARS`

---

## 1. Background and root cause (E2E evidence)

| Symptom | Root cause (reproduced) |
|------|----------------|
| Qwen prompts “model does not support tool calls” | `tools_allowed=[]` shared the `elif not use_tools` branch with “model does not support tools” |
| Combined question LLM asks for HRV | `assemble_tiered_supplemental` concatenates in plan order then **tail-cuts 4500 chars**; `SUPPLEMENT_BG` multi-note ~4600 chars squeezed out `WEARABLE_90D_SUMMARY` and `TASK` |
| `plan_vs_actual=[]` but LLM still amnesic | Only checked the `slot_contents` dict, not the **final tier0 string** |

Current anti-pattern (do not continue):

```python
tier0 = join(slots_in_plan_order)
if len(tier0) > PHA_HARNESS_TIER0_MAX_CHARS:
    tier0 = tier0[:4500] + "…截断"  # silently drop tail slots
```

---

## 2. Architecture principles (aligned with Grok implementation advice)

| # | Principle | Notes |
|---|------|------|
| P1 | **Priority is absolute** | Tier0 allocates char budget by a **profile-fixed priority**; high priority occupies first |
| P2 | **Survival is inalienable** | Protected slots may not be `missing`; over-budget only `full → summary → min`, never `dropped` |
| P3 | **Auditable** | Each slot’s final state writes `tier0_integrity`; `dropped`/`missing` on Protected → **ERROR** |
| P4 | **Supplement special-case** | `SUPPLEMENT_BG` default **summary into Tier0**; full text in Tier1 or Raw User cite |
| P5 | **Two fuse layers split** | Tier0 budget (~4500) vs system total cap (~10000): protect Tier0 first, then cut Tier1 |
| P6 | **Small-step delivery** | v2.2.6.1 is this module + copy only; no Catalog / agent consolidation |

---

## 3. Review of Grok rem suggestions

### 3.1 Fully adopted

- Protected Tier0 list and “at least a summary”
- Summarize supplements to avoid 16×1200 chars stacking Tier0
- `tier0_integrity` (full / summary / min / missing)
- E2E accept: long supplement + same-session combined question
- Design first then implement; no Catalog / dual-entry this week

### 3.2 Adopted with tweaks

| Grok suggestion | Adjustment |
|-----------|------|
| Assemble order TASK → LDL → WEARABLE → supplement | **Adopt as combined budget-allocation order**; decouple from plan.slots_tier0 declaration order (implementation assembles by priority table, not plan-list order) |
| Over budget: compress supplement first, then WEARABLE, LDL/TASK last | **Adopt as degradation order**; LDL/TASK only `full→summary`, never `dropped` |
| Refactor `_cap_system_tiered` | **Second layer**: after Tier0 assembly, system layer still cuts Tier1 first; if Soul+Tier0 already exceeds cap, emit `cap_system_tiered_overflow` ERROR, then second-compress by in-Tier0 degradation order |

### 3.3 Not adopted / clarified

- **Do not create a `WEARABLE_RAW_TS` slot**: existing `WEARABLE_90D_SUMMARY` is already a precomputed summary; the bug is it **did not enter the tier0 string**, not a raw-timeseries naming issue
- **Do not change large Soul blocks in v2.2.6.1**: only add one Task sentence “do not ask for metrics already in injected Evidence blocks”
- **Do not raise `PHA_HARNESS_TIER0_MAX_CHARS` as the only fix**

---

## 4. Slot state machine

After assembly, each Tier0 slot is in one of:

| State | Meaning | Allowed on Protected? |
|------|------|-------------------|
| `full` | Original text fully in tier0 | ✅ |
| `summary` | After a slot-level compressor | ✅ |
| `min` | Tiny placeholder (slot_id + one-line pointer “see Patient State / Raw User”) | ✅ (last resort) |
| `absent` | Source empty (no LDL in DB, etc.) | ⚠️ WARNING |
| `dropped` | Source exists but not in tier0 | ❌ Protected forbidden → **ERROR** |

---

## 5. Profile-level Protected list and priority

### 5.1 `combined_review` (E2E main battlefield)

**Budget allocation order (high → low)**:

1. `TASK` — Protected, never dropped
2. `LDL_AUTHORITY` — Protected
3. `WEARABLE_90D_SUMMARY` — Protected
4. `SUPPLEMENT_BG` — **degradable**; Tier0 default `summary` mode

**Degradation order (when over budget, apply low → high)**:

1. `SUPPLEMENT_BG`: full → summary(≤800) → min(≤120)
2. `WEARABLE_90D_SUMMARY`: full → summary(keep HRV mean / activity energy / one Pearson line) → min
3. `LDL_AUTHORITY`: full → summary(latest + compare key rows only) — **never dropped**
4. `TASK`: cannot compress below min (keep full text); if still over → `tier0_budget_exceeded` ERROR

**plan.slots_tier0 declaration** (docs/matrix sync; implementation concatenates by priority table, not this list order):

`MASTER_ANCHOR` (Soul layer), `TASK`, `LDL_AUTHORITY`, `WEARABLE_90D_SUMMARY`, `SUPPLEMENT_BG`

### 5.2 `supplement_manifest`

Priority: `TASK` → `SUPPLEMENT_BG`(summary/full)

- User **this message is the full supplement text** (Raw User Lane); Tier0 `SUPPLEMENT_BG` uses **DB summary ≤800**, avoiding double occupancy with Raw User
- Protected: `TASK`, `SUPPLEMENT_BG` (at least min)

### 5.3 `lab_cross_year`

Priority: `TASK` → `LDL_AUTHORITY`

### 5.4 `wearable_only`

Priority: `TASK` → `WEARABLE_90D_SUMMARY`

### 5.5 `casual` / `lifestyle`

Priority: `TASK` is the only Protected; rest per profile table

---

## 6. Assembly algorithm (budget, replacing concat+truncate)

**Function**: `assemble_tiered_supplemental_v2(plan, slot_contents) -> (tier0, tier1, missing, tier0_integrity)`

```
Input:
  - plan.profile
  - slot_contents: slot_id -> raw string
  - budget: PHA_HARNESS_TIER0_MAX_CHARS (default 4500)

Steps:
  1. Look up profile priority_list and protected_set
  2. Precompute candidates per slot:
       - SUPPLEMENT_BG -> summarize_supplement_bg(raw, mode=summary|full)
       - WEARABLE_90D_SUMMARY -> compress_wearable_summary(raw)
       - LDL_AUTHORITY -> compress_ldl_block(raw)
       - TASK -> no compress
  3. Round 1: in priority order, try append Protected slots at full, accumulate len
  4. If accumulated > budget:
       degrade degradable slots one step by degradation_order; repeat until <= budget or cannot continue
  5. If any Protected is dropped -> integrity[].severity=error
  6. If Protected is min and still > budget -> error tier0_budget_exceeded
  7. Non-Protected SUPPLEMENT_BG full body -> overflow to tier1 tail (optional)

Output:
  - tier0: join(parts, separator)
  - tier0_integrity: [{slot, state, chars, severity}, ...]
```

**Supplement summary rule** `summarize_supplement_bg`:

- Input: full `build_user_background_block`
- Output ≤800 chars: keep **time-of-day labels** (morning/noon/evening/bedtime) + each segment’s **core item names** + fixture-med/fixture-med-C
- On truncate keep the header note + first item of each `####` subsection

**Wearable summary compress** `compress_wearable_summary`:

- Keep: interval, HRV mean/range, activity energy daily mean, one Pearson line
- Drop: Historical Baseline long section, lowest-5-day detail (Tier1 or omit)

---

## 7. Collaboration with system second fuse `_cap_system_tiered`

```
Soul + MASTER_ANCHOR
  + Tier0 (budget assembly result, integrity already checked)
  + Tier1 (DOSSIER / PATIENT_STATE / AUDIT / RECALL)
  -> if total len <= SYSTEM_CONTENT_MAX_CHARS: OK
  -> else: truncate Tier1 only (existing logic)
  -> if Soul+Tier0 alone > cap:
       record cap_system_tiered_overflow
       fall back to assemble degradation for another round (forbid silent _cap_system_content cutting Tier0)
```

---

## 8. HarnessBuildReport extension

### 8.1 New field `tier0_integrity`

```json
{
  "tier0_integrity": {
    "budget_limit": 4500,
    "used_chars": 4120,
    "slots": [
      {"id": "TASK", "state": "full", "chars": 134, "severity": "ok"},
      {"id": "LDL_AUTHORITY", "state": "full", "chars": 288, "severity": "ok"},
      {"id": "WEARABLE_90D_SUMMARY", "state": "full", "chars": 766, "severity": "ok"},
      {"id": "SUPPLEMENT_BG", "state": "summary", "chars": 780, "severity": "ok"}
    ],
    "errors": [],
    "warnings": []
  }
}
```

### 8.2 Severity

| Condition | Level |
|------|------|
| Protected + `dropped` | **ERROR** → CI fail |
| Protected + `min` | WARNING |
| `absent` and profile requires data | WARNING |
| `tier0_budget_exceeded` | **ERROR** |
| `cap_system_tiered_overflow` and Tier0 was cut | **ERROR** |

### 8.3 `plan_vs_actual` enhancement

- New diff: `tier0_not_materialized:<slot>` — slot_contents has value but tier0 string lacks that slot’s marker
- `compute_plan_vs_actual(..., tier0_text=, tier0_integrity=)`

---

## 9. Bug1: tool-status copy (same-version delivery)

| Condition | SSE status copy |
|------|-----------------|
| `plan.tools_allowed == []` | “This turn uses Harness pre-injected evidence; no tools” |
| `not _model_supports_ollama_tools(model)` | “Current model does not support tool calls; switched to single-round evidence streaming…” |
| else | enter tool loop |

Report adds: `runtime_mode`: `evidence_preload` | `tool_loop` | `model_no_tools`

---

## 10. Acceptance (v2.2.6.1 Done Definition)

### 10.1 Automated

| ID | Scene | Pass |
|------|------|----------|
| G1 | T1 long-supplement dry-run | profile=supplement_manifest; tier0 TASK present |
| G2 | T2 combined dry-run (DB has supplement notes) | tier0 contains WEARABLE marker; TASK present; integrity no ERROR |
| G3 | T2 tier0_integrity | WEARABLE state ∈ {full, summary}; not dropped |
| G4 | golden script | exit 0 |

### 10.2 E2E (human, same script)

1. New session send the full long supplement table
2. Send: “Based on lipids in all my lab reports, analyze whether HRV and workout energy affect lipids, then give an updated supplement plan”

| Check | Pass |
|------|------|
| UI status | no “model does not support tools” (Qwen) |
| Harness JSONL | `tier0_integrity.errors` empty; WEARABLE full/summary |
| LLM answer | does not ask for raw HRV/lipid data; cites in-ledger numbers |
| Supplement part | mentions morning/noon/evening/bedtime structure |

---

## 11. Implementation file map (after Review)

| File | Change |
|------|------|
| `pha/harness_plan.py` | `assemble_tiered_supplemental_v2`, compressors, profile priority table |
| `pha/chat_service.py` | call v2 assembly; tool status three-way branch |
| `pha/harness_report.py` | `tier0_integrity`, enhanced plan_vs_actual |
| `pha/chat_background.py` | `summarize_supplement_bg_for_tier0()` |
| `docs/harness-evidence-matrix.md` | sync combined Tier0 order and Protected table |
| `scripts/pha_harness_golden_run.py` | tier0_integrity asserts |
| `pha/build_marker.py` | `pha-v2.2.6.1` |
| `CHANGELOG.md` | entry |

---

## 12. Risks and rollback

| Risk | Mitigation |
|------|------|
| Supplement summary drops detail | Raw User Lane still keeps this-turn original; Tier0 summary is for same-session turn 2 |
| Compressor too aggressive | integrity marks summary; E2E human looks at the answer |
| Regress wearable_only | profile-independent priority table + G1-G4 |

Rollback: env `PHA_HARNESS_TIER0_ASSEMBLY=legacy` switches back to old `assemble_tiered_supplemental` (keep for 1 release at implement time).

---

**Review sign-off**: □ principles  □ priority  □ acceptance  → start coding after pass

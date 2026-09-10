# Wave 4b — Chronic Health Brief (CHB) Spec v0.1

> **Language / 语言**：English (this document) · [中文](wave4b-chronic-health-brief-spec.md)

> **Filename**: `docs/wave4b-chronic-health-brief-spec.md`  
> **Version**: v0.1 (2026-07-04)  
> **Status**: 📋 **Ratified (minimum encodable edition · 4-β-1 skeleton)**  
> **Governing docs**: [`pha-pm-constitution.md`](pha-pm-constitution.md) Article 3 · [`rfcs/rfc-stage4b-personalization-flywheel.md`](rfcs/rfc-stage4b-personalization-flywheel.md)  
> **Code entry**: `pha/chb_compiler.py` · `scripts/pha_chb_compiler_selfcheck.py`

---

## 1. Non-goals

- **Does not replace** Numerics Manifest / LabelLedger / CompareTable SSO  
- **Does not modify** Harness Profile topology or `harness_profile_registry.json`  
- **Does not** pull the warehouse synchronously on the attachment round (3H forbidden unchanged)  
- **Does not let the LLM** write T0 numbers or unverified inferences into the ledger  

---

## 2. CHB JSON Schema (`pha.chb/v0.1`)

```json
{
  "schema": "pha.chb/v0.1",
  "user_id": "default",
  "compiled_at": "ISO8601",
  "ledger_hash": "sha256-prefix",
  "facts": [
    {
      "text": "LDL 2025-12-07: 2.45 mmol/L",
      "ref_id": "lab_2025-12-07_ldl",
      "prov_type": "lab_report",
      "metric_id": "ldl",
      "value": "2.45",
      "unit": "mmol/L",
      "observed_at": "2025-12-07"
    }
  ],
  "interpretation": [
    {"text": "…", "derived_from": ["lab_2025-12-07_ldl"]}
  ],
  "open_questions": ["尚未有咖啡因敏感性化验记录"],
  "slot_hints": [],
  "facts_markdown": "## §Facts …",
  "interpretation_markdown": "## §Interpretation …"
}
```

### 2.1 Physical isolation of columns

| Column | Source | May be a numerics source? |
|------|------|-------------------|
| **§Facts** | T0 clean rows (lab / wearable aggregates) | ✅ must carry `[ref:*]` |
| **§Interpretation** | LLM or stub, `derived_from` §Facts only | ❌ |
| **§Open Questions** | Gap enumeration | ❌ |

---

## 3. Compiler trigger and flags

| Flag | Default | Notes |
|------|------|------|
| `PHA_CHB_COMPILER` | `0` | Enable LLM Interpretation path (4-β-2) |
| Offline compile CLI | anytime | `compile_chronic_health_brief(user_id)` |

**4-β-1 delivery**: deterministic §Facts path + stub §Interpretation; **do not** hang a Harness slot.

---

## 4. T0 read pipeline (read-only)

| prov_type | Read entry | ref_id pattern |
|-----------|----------|-------------|
| `lab_report` | `medical_storage.query_metrics_in_range` | `lab_{date}_{code}` |
| `wearable_import` | `sqlite_storage.query_wearable_daily_range` 90d mean | `wearable_90d_{date}_{metric}` |

Forbidden: raw device timeseries dumps · unverified LLM inferences.

---

## 5. Harness slot (4-β-2a ✅)

- Slot name: **`USER_CONTEXT_BRIEF`** (Tier1 read-only)  
- Injected profiles: `lifestyle` · `combined_review` advisory path  
- **Forbidden** to inject `attachment_grounded_review` (3H warehouse isolation)
- Disk read: `reports/chb/{user_id}/brief_*.json` (newest mtime); no artifact → empty slot, do not block the Turn

---

## 6. Stale strategy

```text
ledger_hash = sha256(json(facts[]))[:16]
```

T0 change → hash changes → trigger async recompile (**4-β-2c** Ingest/Compile Loop, parked this round).

---

## 7. Loop Slot Candidates (Tier-C managed)

File: [`rules/loop_slot_candidates.jsonl`](../rules/loop_slot_candidates.jsonl)

| token | kind | backlog |
|-------|------|---------|
| 昨晚 | time | temporal_router \| episodic |
| 日均 | aggregation | chb_window \| compare_table |

**Forbidden** to write `health_intent_catalog.json` metric_aliases.

---

## 8. Acceptance

- [x] `pha_chb_compiler_selfcheck.py` all green  
- [x] Every §Facts row has `ref_id`  
- [x] §Interpretation stub is not a number source  
- [x] Harness `USER_CONTEXT_BRIEF` wired (4-β-2a)  
- [x] Mock LLM §Interpretation + `PHA_CHB_COMPILER` default off (4-β-2b)  
- [x] T0 Ingest proposal on disk (4-β-2c · offline stale compile loop)  

---

## 9. Revision history

| Date | Notes |
|------|------|
| 2026-07-04 | v0.1 minimum encodable edition; 4-β-1 skeleton |
| 2026-07-04 | 4-β-2a/b: Harness slot + Mock LLM Interpretation |

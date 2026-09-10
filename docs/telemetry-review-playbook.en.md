# PHA Route Telemetry operations playbook

> **Language / 语言**：English (this document) · [中文](telemetry-review-playbook.md)

> **Version**: v1 (Week 0)  
> **Goal**: make “observe first” **weekly-executable**, not merely “the fields exist”.  
> **Related**: HarnessBuildReport · [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) §8

---

## 1. Principles

1. **Every chat turn** should be reconstructable: which L0 lane was chosen, what L2 ledger was injected, what L3 actually said.  
2. **Divergence** matters more than “average accuracy”: routing says followup, but the model asks “why did you upload” = rule-of-law failure.  
3. Attachment turns **must** record `paths` / `merge` / `ingredients`, or you cannot tell “frontend sent 1 path” vs “OCR empty”.

---

## 2. `intent_route` fields (existing + 3B extensions)

### 2.1 Already present (partially written in code)

| Field | Notes |
|-------|-------|
| `authoritative_profile` | e.g. `attachment_asset_qa` |
| `attachment_qa_mode` | initial / followup / lipid_bridge / none |
| `session_focus_turns_remaining` | focus TTL |
| `vision_parse_confidence` | high / low (to unify with 3B) |
| `document_type` | supplement_label / … |

### 2.2 3B extensions (RFC v1.0 implementation)

| Field | Type | Notes |
|-------|------|-------|
| `attachment_path_count` | int | |
| `merge_count` | int | |
| `ingredient_row_count` | int | |
| `client_parse_reuse` | bool | |
| `perception_channel` | string | |
| `reject_reasons` | string[] | |
| `l3_focus_violation` | bool | see §3 |

---

## 3. Core KGI: `L0_L3_Alignment_Rate`

> **Gemini note adopted**: the key metric for “C-layer rule of law” strength.

### 3.1 Definition

On **attachment-related** session samples:

```text
L0_L3_Alignment_Rate =
  1 - (focus_violation_turns / eligible_attachment_turns)
```

- **eligible_attachment_turns**: turns where `attachment_qa_mode ∈ {initial, followup, lipid_bridge}` and the turn has `parsed_payload`.  
- **focus_violation_turns**: any of:
  - `attachment_qa_mode=followup|lipid_bridge` and the assistant reply hits a **re-ask upload / why-supplement** pattern;
  - `attachment_qa_mode=initial` and the assistant **does not** show a “how does this help me” style section (structure breach);
  - `lipid_bridge` and the assistant attributes **historical LDL improvement** to this turn’s new label (causal breach).

### 3.2 Detection (implementation suggestion)

- **Rule layer** (deterministic): regex/phrase table `FOCUS_VIOLATION_PATTERNS` (small set, not business corner cases).  
- After each LLM completion, write `l3_focus_violation: true/false` into the Harness report.  
- Weekly report: `alignment_rate`, `top_violation_types`.

### 3.3 Targets (draft)

| Stage | Target |
|-------|--------|
| Week 2 | Computable (low baseline allowed) |
| 2 weeks after 3B golden green | `≥ 0.85` (small sample) |
| Production | `≥ 0.90` + human spot check |

---

## 4. Weekly review template (30 minutes)

### 4.1 Export

```bash
# after v1.0 lands
python scripts/pha_telemetry_sample_export.py --days 7 --user default
```

Output: de-identified JSONL → `reports/telemetry-YYYY-WW.jsonl`

### 4.2 Checklist

| # | Question | Action |
|---|----------|--------|
| 1 | Share of `attachment_path_count=1` while UI shows 2 attachments? | >5% → inspect frontend `attachment_paths` |
| 2 | `ingredient_row_count` distribution (p50/p95)? | p50<2 and two images → 3B OCR |
| 3 | Share of `parse_confidence=low`? | Spike → OCR/lighting |
| 4 | `L0_L3_Alignment_Rate`? | <0.85 → inspect TASK/Strip |
| 5 | Share of `client_parse_reuse=false`? | High → send did not carry parsed_parts |
| 6 | Profile divergence (if Shadow on)? | T2+ only |

### 4.3 Record

Each week write `reports/telemetry-review-YYYY-MM-DD.md` with:

- Sample size N  
- The 6 numbers above  
- 1 typical failure transcript (de-identified)  
- One action item for next week  

### 4.4 Stage 3F — goal / arbiter fields (design-locked · see 3F RFC)

After coding, Harness report (v1.3+) should support these fields for **under-specified intent** clustering (not single-phrase E2E acceptance):

| Field | Notes | Health signal |
|-------|-------|---------------|
| `goalClass` | `holistic_assessment` / `metric_specific` / `casual` | holistic sentences should not sit on lifestyle long-term |
| `arbiterDecision.router_profile` | SchemaRouter candidate | contrast with authoritative |
| `arbiterDecision.authoritative_profile` | final profile | whether combined upgrade happened |
| `arbiterDecision.reason` | e.g. `goal_holistic_upgrade` | attribution enum |
| `arbiterDecision.existence_probe` | `{lab, wearable}` | upgrade gate |
| `episodic.focusGoal` | session synthetic-goal continue | multi-turn drop-off debug |

**One extra weekly question** (after 3F lands):

7. Share of `goalClass=holistic` and `authoritative_profile=lifestyle`? → should → 0 (when dual-domain probe passes)

Details: [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) §7.

### 4.5 Stage 3F-δ — Shadow Intent Scout fields

When `PHA_SHADOW_ROUTING=1` and `PHA_GOAL_CLASSIFIER=1`, the `shadow_routing` block extends:

| Field | Notes |
|-------|-------|
| `goal_class` | Shadow-side `classify_goal` result (telemetry only) |
| `goal_source` | `catalog` / `explicit_metric` / … |
| `suggested_domains` | holistic → `["lab","wearable"]`; metric → inferred domain |

**One extra weekly question** (after 3F-δ lands):

8. Share of `authoritative_profile=lifestyle` and `goal_class=holistic_assessment`? → Shadow may only emit a status hint, **must not** rewrite the plan.

**Forbidden**: writing Shadow `goal_class` / `suggested_domains` into Arbiter or `TurnEvidencePlan` (zero-adopt).

---

## 5. Golden datasets (with track 3 T4)

| File | Content |
|------|---------|
| `tests/fixtures/intent_route_golden.jsonl` | 20–50 routing sentences |
| `tests/fixtures/attachment_qa_golden.jsonl` | 5 attachment questions + expected qa_mode |
| `tests/fixtures/e2e-failures-2026-05/README.md` | real-device failure summaries |

---

## 6. Relation to Shadow

- Shadow is **off by default**; Telemetry still treats **authoritative_profile** as source of truth.  
- If sampling Shadow: also record `shadow_profile`, `shadow_confidence`, `disagrees_with_authoritative`.  
- **Forbidden** for Shadow proposals to change L0 directly (before Stage 3 Hybrid).

---

## Appendix: sample Harness snippet

```json
{
  "intent_route": {
    "authoritative_profile": "attachment_asset_qa",
    "attachment_qa_mode": "followup",
    "attachment_path_count": 2,
    "merge_count": 2,
    "ingredient_row_count": 4,
    "parse_confidence": "high",
    "client_parse_reuse": true,
    "perception_channel": "ocr_only",
    "l3_focus_violation": false
  }
}
```

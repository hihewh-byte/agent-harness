# Stage 3C — K-layer medication interaction Lookup Backlog (AR-3 · Spec-only)

> **Language / 语言**：English (this document) · [中文](stage3c-k-interaction-lookup-backlog.md)

> **Version**: v0.1 (2026-05-26)  
> **Status**: 📋 **docs only** · coding is after Wave 2 (AR-1/2)  
> **Depends on**: [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.en.md) §6.2 · [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) §7.7 Medication

---

## 1. Purpose

When supporting R3-class questions (“risk of taking this with a current Rx / OTC”):

- `interaction_context` assertions come **only** from a K-layer lookup summary
- L3 **must not** claim “you are taking a fixture-med” with no ledger evidence
- Triggers **do not** use a hardcoded drug-name table; they go through Schema intent `medication_interaction`

---

## 2. Trigger (aligned with Active Recall L-1)

| Source | Use |
|------|------|
| `SchemaIntentRouter` | Intent family `medication_interaction` |
| MC `trigger_keywords` | Asset-class interaction domain (configured, not NOW / fixture-med literals) |
| `focus_tokens` | Normalized names of focus ingredients |

---

## 3. Lookup contract (draft)

```text
catalog.lookup_interactions(
  normalized_ingredient_rows,  # from LabelLedger
  user_medication_profile,     # from Patient State / medication ledger
) -> InteractionLookupResult
```

| Field | Notes |
|------|------|
| `hits[]` | Each hit has `source_id`, `severity`, `summary_zh` (≤80 chars) |
| `empty` | Allowed; Recall omits `interaction_context`; L3 must say “no medication record in the ledger, cannot assess co-administration” |

---

## 4. With P-layer refusal

- Ledger `low` → **forbid** interaction conclusions
- lookup `empty` + user insists on interaction → state unknown; **forbid** common-sense fabrication

---

## 5. Coding gate

- [ ] Wave 1 P0-E2 R1 ledger green or Yellow logged
- [ ] Wave 2 AR-2 `RECALL_FOCUS` shipped
- [ ] Wenhui confirms AR-3 coding start

---

## 6. Revision log

| Date | Version | Notes |
|------|------|------|
| 2026-05-26 | v0.1 | AR-3 Spec-only backlog; folded into the master plan after Gemini final review |

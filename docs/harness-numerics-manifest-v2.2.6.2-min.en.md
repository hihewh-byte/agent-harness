# v2.2.6.2-min: Numerics Manifest + C-layer post-audit

> **Language / 语言**：English (this document) · [中文](harness-numerics-manifest-v2.2.6.2-min.md)

## Goal

Without tearing down the **Catalog wall**, give PHA a machine-checkable numeric whitelist and a post-answer gate so a 7B model cannot pass lab / wearable numbers with no ground truth.

This module is the shared base of the v2.2.7 Catalog **Reduce** stage: after `fetch_evidence` picks, the same `build_numerics_manifest()` still builds the whitelist.

## Architecture position

```text
user question → build_turn_evidence_plan
       → fill LDL / WEARABLE / … slots
       → build_numerics_manifest()     ← new (SQLite + wearable structured summary)
       → format_manifest_tier0_block → NUMERICS_MANIFEST slot
       → assemble_tiered_supplemental → Tier0 inject
       → LLM single-round reasoning
       → audit_response_numerics()     ← C-layer post-audit
       → HarnessReport / done SSE
```

## Module API (`pha/numerics_manifest.py`)

| Function | Duty |
|------|------|
| `build_numerics_manifest(user_id, profile, user_message, …)` | Assemble `NumericsManifest` from SQLite lipids + `HealthDataResult` wearable summary |
| `format_manifest_tier0_block(manifest, max_chars=600)` | Tier0 machine-whitelist text block |
| `audit_response_numerics(text, manifest, require_citation=…)` | Answer numbers/dates ⊆ whitelist; returns `passed` / `violations` / `citations` |

### ManifestEntry fields

- `domain`: `lipid` \| `wearable`
- `metric`: canonical code (TC/LDL/HDL/TG/HRV mean/activity energy daily mean)
- `value`: float
- `unit`: mmol/L, ms, kcal, etc.
- `anchor`: report day `YYYY-MM-DD` or interval `start~end`
- `source`: `sqlite.medical_reports` \| `wearable.summary`

### Tier0 inject (hybrid transition)

The `combined_review` profile in v2.2.6.2-min **keeps** short `LDL_AUTHORITY` + `WEARABLE_90D_SUMMARY` blocks and **adds** `NUMERICS_MANIFEST` (≤600 chars, protected, cannot be dropped).

TASK copy is appended: any lab / wearable number written must cite a Manifest KV triple.

## C-layer audit rules

1. **Forbidden dates**: known hallucination dates (e.g. `2026-04-30`), future dates, and dates that are not on the whitelist but appear in a lab-citation context.
2. **Forbidden values**: decimals in the answer in the `0.5–15.0` range that are not on the whitelist and are not dose context (g/mg/FU) are violations.
3. **require_citation** (E2E / `PHA_NUMERICS_REQUIRE_CITATION=1`): a combined turn must cite at least one lipid whitelist date or value.
4. **Execution mode** (`PHA_NUMERICS_AUDIT`): `warn` (default, write report) \| `block` (replace the answer) \| `off`.

## v2.2.7 Catalog handoff

```text
Catalog Map:  LLM sees directory → fetch_evidence(ids)
Catalog Reduce: fetch result → build_numerics_manifest(selected_ids=…)  # same module, extended
Catalog Guard:  audit_response_numerics()                            # unchanged
Fallback:       1 round with no tool call → Harness default-pulls LDL_TABLE + WEARABLE_90D
```

## Acceptance (E2E + golden)

| Case | Expectation |
|------|------|
| T2 combined dry-run | `NUMERICS_MANIFEST` tier0 integrity = full, contains `2023-12-15` / `2025-12-07` |
| `pha_numerics_manifest_selfcheck.py` | manifest rows ≥8 lipid; audit samples PASS/FAIL |
| E2E Turn2 | no `2026-04-30`; `numerics_audit.passed=true`; at least 1 ground-truth date or value |

## Environment variables

| Variable | Default | Notes |
|------|------|------|
| `PHA_NUMERICS_AUDIT` | `warn` | Post-audit: `warn` / `block` / `off` |
| `PHA_NUMERICS_AUDIT_SCOPE` | `t0_plus_disclosure` | `t0_strict` (rollback) \| `t0_plus_disclosure` (production default) |
| `PHA_NUMERICS_T1_M4_MODE` | `warn` | M4 disclaimer: `strict` / `warn` / `off` |
| `PHA_NUMERICS_REQUIRE_CITATION` | `0` | E2E sets `1` to force ground-truth citation |
| `PHA_MANIFEST_MAX_CHARS` | `600` | Tier0 manifest cap |

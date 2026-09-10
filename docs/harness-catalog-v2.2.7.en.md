# v2.2.7: Catalog behavior mode

> **Language / 语言**：English (this document) · [中文](harness-catalog-v2.2.7.md)

## Goal

Cut the ~4000-character Tier0 pre-inject on a single `combined_review` turn. Replace it with **Catalog directory + fetch pick-list + second-round reasoning + C-layer audit**.

## Flag

| Variable | Default | Notes |
|------|------|------|
| `PHA_HARNESS_CATALOG_MODE` | `1` | `0`/`legacy` rolls back to v2.2.6.2-min full pre-inject |

## `combined_review` (Catalog on)

**Tier0**: `TASK` + `EVIDENCE_CATALOG` (~300 chars) + `NUMERICS_MANIFEST` (lipid preloaded, ~200 chars)

**Off Tier0**: full text of `LDL_AUTHORITY` / `WEARABLE_90D_SUMMARY` / `SUPPLEMENT_BG`

**Tier1**: `RECALL` + `AUDIT` (no Patient State / dossier)

**tools_allowed**: `["fetch_evidence_by_id"]`

## Asset IDs

| ID | Content |
|----|------|
| `LDL_TABLE` | SQLite LDL / lipid authority table |
| `WEARABLE_90D` | Last-90-day wearable summary |
| `SUPPLEMENT_BG` | Supplement background summary |

## Flow

```text
Tier0 light context → LLM round 1 (fetch_evidence_by_id)
  → no pick → Harness fallback: LDL_TABLE + WEARABLE_90D
  → inject picked blocks + recompute Manifest (incl. wearable)
  → LLM round 2 stream
  → audit_response_numerics(REQUIRE_CITATION)
```

## Acceptance

- golden T2: `EVIDENCE_CATALOG` present; Tier0 `used_chars` < 1500
- E2E: `fetch` or `harness_fallback_fetch`; `numerics_audit` + ground-truth citation (strict mode)

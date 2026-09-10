# PHA Harness Evidence Matrix (v2.2.5 declarative contract)

> **Language / 语言**：English (this document) · [中文](harness-evidence-matrix.md)

> **Status**: Phase 0 spec. When `mode=as_is`, runtime only emits a comparison report; it does not force behavior from this table.  
> From **Phase 1**, `TurnEvidencePlan` executes by table lookup.

## 1. Profile definitions

| profile | Trigger (declarative) | Tier0 slots (non-fusable) | Tier1 slots (fusable) | forbidden | tools_allowed | Rewrite user body |
|---------|-------------------|-------------------------|----------------------|-----------|---------------|----------------|
| `casual` | Greeting / very short social | `MASTER_ANCHOR` | — | dossier, Snapshot, tools | `[]` | No |
| `supplement_manifest` | Supplement / medication self-report as primary; **no** lipid / multi-year compare question | `MASTER_ANCHOR`, `SUPPLEMENT_BG` | — | `USER_SNAPSHOT`, `GET_HEALTH_DATA` | `[]` | No |
| `combined_review` | Lipids + (90d wearable window **or** supplement reasonableness) | `TASK`, `LDL_AUTHORITY`, `WEARABLE_90D_SUMMARY`, `SUPPLEMENT_BG` (summary) | `PATIENT_STATE_LAB`, `DOSSIER_CLINICAL_COMPACT`, `AUDIT`, `RECALL`, supplement full-text overflow | `USER_SNAPSHOT` | `[]` (target) | No |
| `lab_cross_year` | Multi-year / compare + lipids | `MASTER_ANCHOR`, `LDL_AUTHORITY`, `DOSSIER_LAB` | `PATIENT_STATE_LAB`, `AUDIT` | `GET_HEALTH_DATA` (default) | `get_temporal_history_dossier` | No |
| `wearable_only` | Sleep / steps / HRV / activity energy only | `MASTER_ANCHOR`, `WEARABLE_90D` | `PATIENT_STATE_WEARABLE` | full cross-year dossier | `get_health_data` (controlled) | No |
| `lifestyle` | Other lifestyle | `MASTER_ANCHOR` | `SUPPLEMENT_BG`? | — | `[]` | No |

## 2. Slot notes

| slot_id | Source module (current as-is) |
|---------|------------------------|
| `MASTER_ANCHOR` | `build_system_date_block()` |
| `LDL_AUTHORITY` | `build_ldl_authority_system_block()` |
| `SUPPLEMENT_BG` | `build_user_background_block()` |
| `PATIENT_STATE_LAB` / `PATIENT_STATE_WEARABLE` | `build_patient_state_evidence_slice()` |
| `DOSSIER_*` | `prepare_chat_evidence_bundle(build_dossier=True)` |
| `WEARABLE_90D_SUMMARY` | Phase 1: precomputed summary; as-is may be Snapshot / tool instead |
| `USER_SNAPSHOT` | `apply_health_heuristic_override()` writes into user body |
| `AUDIT` / `RECALL` | `build_chat_audit_payload` / `build_chat_context_block` |

## 3. Legacy mapping (v2.2.4 → target profile)

| as-is signal | Target profile | Known gap (Phase 0 observation) |
|------------|--------------|-------------------------|
| Long supplement table (with sleep / workout words) | `supplement_manifest` | Often misclassified `WEARABLE` → injects Snapshot |
| `QuestionType.COMBINED` | `combined_review` | Snapshot forbidden, but tool loop can still `get_health_data` |
| `QuestionType.LAB` + dossier | `lab_cross_year` | Dossier front-load + `SYSTEM_CONTENT_MAX_CHARS` easily squeezes out LDL |
| `user_message_needs_wearable_query` | `wearable_only` | Conflicts with supplement-copy regex |

## 4. Change governance (forbidden)

- Do not add scattered `should_*` functions (legacy is read-only until Phase 2)
- Do not treat raising `SYSTEM_CONTENT_MAX_CHARS` as the only fix
- Do not concatenate `User Data Snapshot` inside `user_message` (from Phase 1)

## 5. Golden cases (Phase 0 acceptance)

| ID | Input | Report must explain |
|----|------|-------------------|
| T1 | Long supplement table only | `primary_goal_guess=supplement_manifest`; if `USER_SNAPSHOT` appears, `warnings` include `matrix_gap_snapshot_on_supplement` |
| T2 | Compare multi-year lipids + last-90-day HRV/activity + supplements | `combined_review`; LDL slot length >0 or `warnings` include missing LDL; `tools.executed` records whether a tool ran |
| T3 | T2 in the same session after T1 | `SUPPLEMENT_BG` length reflects DB; history turn count |

## 6. Environment variables

| Variable | Default | Meaning |
|------|------|------|
| `PHA_HARNESS_DEBUG` | `0` | `1` writes report JSONL + human-readable summary |
| `PHA_HARNESS_REPORT_PATH` | `/tmp/pha-harness-reports.jsonl` | JSONL path |
| `PHA_HARNESS_DEBUG_FULL` | `0` | `1` also dumps full messages (redacted directory) |

# Stage 3d — Wearable Merge Coerce and no-data gate Spec

> **Language / 语言**：English (this document) · [中文](stage3d-wearable-merge-and-gates-spec.md)

> **Status**: v0.1 first draft (2026-05-30)  
> **Baseline build**: `pha-v2.3.9-wave3d-wearable-merge-coerce`  
> **Governing docs**: [`pha-pm-constitution.md`](pha-pm-constitution.md) · [`stage3c-wearable-snapshot-bridge.md`](stage3c-wearable-snapshot-bridge.md)  
> **E2E checklist**: [`stage3d-wearable-e2e-checklist.md`](stage3d-wearable-e2e-checklist.md) (to write)

---

## 0. Document purpose

Freeze Wave 3d’s **architecture-level** fix for real-device msg-298-class failures. Forbidden: case-by-case patches.

**Non-goals**: do not change the Harness three-lane constitution; do not introduce new drug-name/brand hardcoding.

---

## 1. Problem statement (real-device audit summary)

| Symptom | Root cause |
|---------|------------|
| OCR has Sleep/HRV but `wearable_metrics=0` | 6 images `{unknown, wearable}` → `merge_family_conflict` aborts **before** metric extraction |
| Harness has no `WEARABLE_SNAPSHOT` | `document_family=unknown` → `attachment_parse_is_actionable=false` |
| No data still uses filler / invents | Wearable side has no `skip_llm` gate symmetric to supplements |
| Follow-up “图片里是什么” answers LDL | No attachment + no intent reuse + routes lifestyle |

---

## 2. `merge_family_coerce` (P0)

### 2.1 Decision table

| Multi-image family set | batch is Health UI | Behavior |
|------------------------|--------------------|----------|
| `{wearable}` | — | Normal `merge_wearable_parts` |
| `{unknown, wearable}` | ✅ `parts_should_finalize_as_wearable` or merged OCR hit | **coerce** → wearable, continue merge |
| `{supplement, wearable}` | — | **hard** `merge_family_conflict` |
| `{lab, wearable}` | — | **hard** conflict |
| Other mixes | — | hard conflict |

### 2.2 Implementation anchors

- `pha/wearable_snapshot_v1.py` → `finalize_wearable_attachment`
- Warning key: `merge_family_coerced:unknown,wearable` (not reject)

### 2.3 Acceptance

- 6-image Health UI batch → `wearable_metrics ≥ 4`, `parse_confidence` is not low from conflict alone

---

## 3. `family_from_parsed` and actionable (P0)

| Condition | Routing |
|-----------|---------|
| `document_family=unknown/other` + `ocr_suggests_wearable_ui` | → `wearable` |
| Has `wearable_metrics` | actionable |
| Has Health UI OCR (no metrics) | actionable (triggers screenshot profile) |

**Implementation**: `pha/perception_family.py`

---

## 4. Wearable deterministic refuse G_wearable (P0)

Symmetric to `maybe_deterministic_attachment_reply` (supplements).

| Condition | Behavior |
|-----------|----------|
| screenshot profile + no `wearable_metrics` + (low conf or compare question) | `skip_llm=true`, fixed guidance copy |
| Has metrics | Do not refuse; inject WEARABLE_SNAPSHOT |

**Implementation**: `pha/wearable_harness.py` → `maybe_deterministic_wearable_reply`  
**Wiring**: `pha/chat_service.py`

---

## 5. No-attachment follow-up reuse (P0)

### 5.1 Intent

`user_message_needs_attachment_recall`: “图片/附件/上传的/截图” + “是什么/分析/信息”

### 5.2 Reuse chain

1. `get_latest_session_attachment_parse(session_id)`
2. If `wearable_metrics=0` and OCR is Health UI → **re-finalize** (compat old DB rows)
3. `should_use_wearable_screenshot_review` includes recall intent

**Implementation**: `pha/intent_gates.py` · `pha/chat_service.py`

---

## 6. Harness trigger contract

| Slot | screenshot profile |
|------|-------------------|
| Tier0 | `WEARABLE_SNAPSHOT` · `WEARABLE_90D_SUMMARY` · `TASK` |
| Forbidden | full `SUPPLEMENT_BG` · `DOSSIER_*` · clinical three-step TASK |
| Soul | Lite (numeric contract + tone) — **pending 3d-β** |

---

## 7. Telemetry (suggested fields)

| Field | Meaning |
|-------|---------|
| `merge_family_coerced` | soft coerce happened |
| `merge_family_conflict` | hard reject |
| `wearable_metrics_count` | ledger KPI count |
| `wearable_skip_llm` | refuse-and-pass |
| `attachment_parse_reused` | no-image reuse |

---

## 8. Relation to Wave 3c

| 3c delivery | 3d increment |
|-------------|--------------|
| `WearableSnapshotLedgerV1` | actually produce metrics after coerce |
| `wearable_screenshot_review` profile | actionable + recall trigger |
| Multi-image skip supplement merge | finalize no longer aborts unknown+wearable |

---

## 9. Open items (3d-β)

- `layout_region` split-screen to raise KPI precision (sleep stages)
- 6-image async parse client UX
- F-layer `apple_health_screens_6panel` fixture
- screenshot profile Lite Soul

---

## 10. Revision history

| Date | Version | Notes |
|------|---------|-------|
| 2026-05-30 | v0.1 | First draft: coerce · refuse · reuse · real-device msg-298 regression |

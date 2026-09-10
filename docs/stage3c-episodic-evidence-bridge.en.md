# Stage 3C — Attachment focus × full-ledger evidence bridge spec

> **Language / 语言**：English (this document) · [中文](stage3c-episodic-evidence-bridge.md)

> **Version**: v0.1 (2026-05-26)  
> **Status**: 📋 Spec (pending code)  
> **Depends on**: 3A session focus, `session_turn_focus`, Harness Plan  
> **Analysis**: [`stage3c-attachment-evidence-bridge-analysis.md`](stage3c-attachment-evidence-bridge-analysis.en.md)

---

## 1. Problem

| Symptom | Root cause |
|------|------|
| R1 talks supplements only, no HRV/LDL | `attachment_asset_qa` **forbids** Patient State / WEARABLE / CATALOG |
| R2 “body metrics” claims missing baseline | Falls to `lifestyle` + Patient State not injected / empty table + full medical Soul |

**Goal**:
- R1: without **opening the full board**, let the LLM **know** what data is in the ledger and what it may cite.
- R2: while **session focus is still active**, inject lab/wearable slices related to the question via a **bridge Profile**.

---

## 2. Evidence-scope enum `evidence_scope`

| Value | R1 attachment initial | Notes |
|------|-----------------|------|
| `focus_only` | optional | ATTACHMENT_LABEL + narrow SUPPLEMENT_BG only (current) |
| `focus_plus_availability` | **recommended default** | + `DATA_AVAILABILITY` block (2–6 lines) |
| `focus_plus_lipid` | user asks lipids | + `LDL_AUTHORITY` or lipid snapshot (lipid_bridge already covers part) |
| `focus_plus_wearable` | user asks HRV/workout | + short `WEARABLE_90D_SUMMARY` |

**Forbidden**: secretly stuffing full Patient State under `focus_only` (breaks 3A focus).

---

## 3. New slot `DATA_AVAILABILITY` (C layer · 0ms)

**Producer**: `build_data_availability_block(user_id, question_hint)` — read-only SQLite counts/latest dates; no LLM.

**Example output**:

```text
【数据可用性 · 本轮只披露下列，勿声称「系统无任何数据」】
- 化验账本：有；最近报告日 2025-11-12；含 LDL/HDL/甘油三酯 等（未注入全表，点名可展开）
- 穿戴近90日：有；HRV 均值约 33 ms（n=12 天）；步数/睡眠 有摘要
- 本轮焦点：上传标签资产（磷脂酰丝氨酸类）；非化验单
```

**Rules**:

- If the ledger has **none**, write “none”; LLM must not invent
- If present but not injected into Tier0, write “present, not expanded this turn; name the metric if analysis is needed”
- Must not contain hardcoded brand/ingredient names

---

## 4. Profile: `attachment_episodic_bridge`

### 4.1 Trigger (all must hold)

1. `session_focus_active == true` (`chat_session_turn_focus`)
2. This message is **not** `initial` (this turn has a new attachment and hits the dual-question form)
3. This message is **not** `lipid_bridge` (lipid-specific questions still take the lipid profile + LDL snapshot)
4. **Default lane**: any non-empty short sentence inside focus (≤320 chars) → `episodic_bridge` (**retired** followup-phrase-table routing)

**C-layer TASK**: `build_episodic_bridge_task(msg)` — unified `ATTACHMENT_EPISODIC_BRIDGE_TASK`; append structural `EPISODIC_BRIDGE_NARROW_ADDENDUM` only when `len(msg)≤120` and not lipid (not L0 regex).

### 4.2 Slots

**Tier0**:

- `MASTER_ANCHOR`
- `ATTACHMENT_LABEL` (session-focus ledger summary from `session_turn_focus`)
- `DATA_AVAILABILITY`
- `TASK` (bridge TASK, see §5)
- `NUMERICS_MANIFEST` (compact)
- `WEARABLE_90D_SUMMARY` (only when the question contains HRV/sleep/activity or COMBINED intent)

**Tier1**:

- `PATIENT_STATE_LAB` or **evidence slice** (`build_patient_state_evidence_slice`, trimmed by question)
- `SUPPLEMENT_BG` (**narrow**; forbid full-plan recitation)

**Forbidden**:

- Full `DOSSIER` (unless the user explicitly asks multi-year compare)
- `GET_HEALTH_DATA` tool (v1 still C-layer prefetch, to avoid 7B tool loops)

**Soul**: `PHA_ATTACHMENT_SOUL_MINIMAL` + short bridge addendum; **forbid** three-step consult titles.

### 4.3 Relation to `attachment_asset_qa`

| Turn | Profile |
|------|---------|
| R1 “what is it + help” + new attachment | `attachment_asset_qa` + `evidence_scope=focus_plus_availability` |
| R2 “which metrics can it raise” + focus active | `attachment_episodic_bridge` |
| R2 focus expired | `combined_review` or `wearable_only` / `lab_cross_year` per Schema |

---

## 5. TASK constitution (bridge turns)

```text
【本轮任务 · 焦点资产 × 指标桥接】
1) 用 1 句确认仍在讨论「会话焦点资产」（来自 ATTACHMENT_LABEL）。
2) 回答用户关于「身体指标/改善」的问题：
   - 仅引用 DATA_AVAILABILITY、Patient State、Manifest、穿戴摘要中已出现的数据；
   - 每条数字须对应可见行；无则写「库内暂无该指标」而非「缺乏基线」套话；
   - 说明指标与「焦点补剂」的关联强度（有证据/证据弱/无关）— 允许结论「无关可不讨论」。
3) 禁止：三步看诊法标题；复述完整补剂时间表；将历史 LDL 改善归功于焦点补剂。
```

---

## 6. Session-focus TTL

| Param | Default | Notes |
|------|------|------|
| `focus_turns_remaining` | 3 | includes 2 follow-up/bridge turns after initial |
| Renew | user hits focus_tokens | same as 3A.2 |

Focus ledger is stored in `focus_summary` (`label_ledger` truncated); **do not** re-run Vision every turn.

---

## 7. Telemetry

| Field | Notes |
|------|------|
| `evidence_scope` | focus_plus_* |
| `profile` | attachment_episodic_bridge |
| `data_availability_nonempty` | bool |
| `patient_state_rows` | int |
| `bridge_reason` | focus_active \| intent_metric |

---

## 8. Acceptance

- [ ] R1: Harness contains `DATA_AVAILABILITY`; no full PATIENT_STATE table
- [ ] R2: profile=`attachment_episodic_bridge`; no “longitudinal trend reconcile” title
- [ ] R2: if DB has LDL/HRV, the answer must cite it or explicitly say “not in ledger yet”
- [ ] Logs: `forbidden` does not block PATIENT_STATE on the bridge profile
- [ ] R3 (Active Recall): see [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.en.md) §8 — `RECALL_FOCUS` contains the ledger asset; interaction questions do not drift brand/ingredients

---

## 9. Active Recall (L2.5)

Focus TTL solves the **lane**; **grip** is solved by Active Recall: [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.en.md).

---

## 9. Non-goals

- Does not replace 3B-β Vision
- Do not write `if fixture-med` / `if soy` in the mid-tier (K-layer Catalog)

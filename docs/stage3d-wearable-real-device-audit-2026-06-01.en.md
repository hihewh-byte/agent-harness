# Real-device 6-image wearable compare · data path and truth audit (2026-06-01)

> **Language / 语言**：English (this document) · [中文](stage3d-wearable-real-device-audit-2026-06-01.md)

> **Build**: `pha-v2.3.19-wave3d-epsilon-interpretation-audit`  
> **DB anchors**: user msg **330/332** (DeepSeek / Qwen) → assistant **331/333**

---

## 1. Test setup

| Round | Model (user operation order) | session | user message id | assistant id |
|-------|------------------------------|---------|-----------------|--------------|
| First | **DeepSeek** | `4dda92f5-caeb-4d0e-b83b-04df3b826567` | 330 | 331 |
| Second | **Qwen** | `07886377-d00c-4c76-93fd-f321526e74f9` | 332 | 333 |

User question (identical both times):

> 附件是5月30号的apple watch上的一些指标，其中一张是5月29号的work out数据，请分析与过去90的指标相比，这些指标是否正常，尤其是分析睡眠数据

---

## 2. Full user-visible replies

### 2.1 DeepSeek (msg 331 · 581 characters)

**Character-identical** to the Qwen body (see §2.2). DB `content` matches the table below.

### 2.2 Qwen (msg 333 · 581 characters)

```
根据您上传的 Apple Watch 截图，与过去约 90 天记录对比：

睡眠总时长：本次 8 小时 43 分钟；过去约 90 天平均 8.0 hr（常见区间 0.4–9.9），落在近 90 天正常区间内。

HRV：本次 30 ms；过去约 90 天平均 32.9 ms（常见区间 23.1–45.0），落在近 90 天正常区间内。

静息心率：本次 58 bpm；过去约 90 天平均 57.4 bpm（常见区间 49.0–67.0），落在近 90 天正常区间内。

呼吸率：本次 11-17.5 breaths/min；过去约 90 天平均 13.2 breaths/min（常见区间 12.3–15.0），落在近 90 天正常区间内。

睡眠分期：本次为 深睡 1 小时 9 分钟、REM 2 小时 17 分钟。系统没有保存深睡/REM 的 90 天历史，无法与过去 90 天对比。

锻炼：

锻炼心率范围：76-147 bpm（仅来自本次截图）

近期锻炼次数：8 次（仅来自本次截图）

说明：深睡与 REM 仅来自截图，系统没有保存这两项的 90 天历史，无法与过去 90 天对比。
```

---

## 3. Path conclusion (identical both times)

```text
6-image upload → Vision/OCR merge (attachment_count=6)
  → wearable_metrics ledger (9 KPI)
  → CompareTableV1 (8 rows, no SpO2)
  → LLM stream
  → compare audit failed (typical: compare_table_numeric_drift:17.5)
  → Deterministic Fallback (compare_table_to_user_summary + polish)
  → write assistant message
```

| Judgment | Result |
|----------|--------|
| OCR/ledger | ✅ sleep 8h43m, HRV 30, RHR 58, respiratory 11–17.5, deep/REM, workout 76–147 / 8 times |
| CompareTable | ✅ tables inside both parsed_json identical |
| User-visible copy source | ✅ **Fallback template**, not “audit-passed LLM original” |
| DeepSeek vs Qwen difference | ❌ **none** (same 581 characters) — audit layer flattened model output |

---

## 4. Data-truth check

### 4.1 Screenshot layer (L0)

| metric_id | Value | Screen type |
|-----------|-------|-------------|
| sleep_time_asleep | 8hr43min | sleep |
| sleep_deep | 1hr9min | sleep |
| sleep_rem | 2hr17min | sleep |
| hrv_rmssd_ms | 30 | hrv |
| resting_heart_rate_bpm | 58 | heart_rate |
| respiratory_rate | 11-17.5 | respiratory_rate |
| workout_* | 76-147 / 8 | workout |
| spo2_percent | — | not recognized |

### 4.2 Warehouse 90d (reference_date=2026-06-01, 79 days)

| Metric | mean | min–max (in-table range) | Notes |
|--------|------|--------------------------|-------|
| Sleep | 8.0 hr | **0.4–9.9** | min from 2026-03-19 abnormal short-sleep day (~27min), not hallucination |
| HRV | 32.9 ms | 23.1–45.0 | matches reference-date window |
| RHR | 57.4 bpm | 49.0–67.0 | warehouse min/max |
| Respiratory rate | 13.2 | 12.3–15.0 | warehouse max=15.0; screenshot upper 17.5 triggered drift |
| Deep/REM | NO_BASELINE | — | **before 3d-δ C-15**: daily table had no stage columns |

---

## 5. Product backlog (no implementation this round)

| ID | Item | Notes |
|----|------|-------|
| **UI-1** | Show attachment thumbnails in chat bubbles | `loadChatSessionMessages` only renders `content`; `attachment_path` is server absolute-path JSON, no preview API |
| **UI-2** | Send-state attachment preview | `appendChat` is text-only, no `<img>` |

**No re-upload inside a session**: same-session no-image follow-up can reuse `get_latest_session_attachment_parse`; **a new session must re-upload the 6 images**.

---

## 6. Default-model suggestion (record)

This round **should not** set DeepSeek as default because of this: both models ended as the same Fallback. Model choice should prioritize **audit pass rate / latency**; trusted wearable-compare output is **CompareTable + Fallback**.

---

## 7. Follow-on coding (original plan)

| ID | Task | Status |
|----|------|--------|
| C-15 | Sleep-stage daily aggregate + deep/rem comparable | ✅ v2.3.20 (`sleep_deep_hours`/`sleep_rem_hours` + rebuild) |
| C-16 | HKWorkout import + workout comparable | ✅ v2.3.21 (real device needs **re-import export.zip**) |
| ε+ | Authorize screenshot range endpoints (e.g. 17.5) to reduce false Fallback | 📋 |

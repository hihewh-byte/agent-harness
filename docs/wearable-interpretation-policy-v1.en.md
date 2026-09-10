# Wearable Interpretation Policy v1

> **Language / 语言**：English (this document) · [中文](wearable-interpretation-policy-v1.md)

> **Status**:**v1.0 signed** (2026-06-01 · PM/Gemini/Cursor architecture alignment)  
> **Governing docs**: [`pha-pm-constitution.md`](pha-pm-constitution.md) · [`stage3d-gamma-wearable-compare-contract-spec.md`](stage3d-gamma-wearable-compare-contract-spec.md)  
> **Related**: [`stage3d-delta-wearable-fact-pipeline-spec.md`](stage3d-delta-wearable-fact-pipeline-spec.md) (warehouse extension)  
> **Implementation mapping**: `audit_wearable_compare_table` rule family (not one-off prompt patches)

---

## 0. Purpose

On top of 3d-γ “CompareTable = comparison-number SSO”, freeze **how PHA and the LLM split “judgment”**:

| Role | Duty |
|------|------|
| **PHA (fact layer + compute layer)** | Keep numbers true and traceable; emit a **deterministic verdict** vs the personal baseline |
| **LLM (narrative layer)** | Doctor-style interpretation **when a baseline supports it**; when **there is no baseline**, only state screenshot facts |

**Non-goals**: replace the personal 90-day baseline with LLM-trained common sense; use audit regex to patch one on-device phrasing at a time.

---

## 1. Two kinds of judgment (architectural core)

### 1.1 Type A — data-bound judgment (allowed)

**Premise**: CompareTable row `row_kind=comparable_90d`, and `baseline_90d_value` is a number (not `NO_BASELINE`).

| LLM may | Example |
|----------|------|
| Restate screenshot value, 90d mean, range | “This reading 30 ms; last-90-day average 32.9 ms (23.1–45.0)” |
| Relative wording **logically consistent** with `verdict` | “Slightly below the mean, still inside your usual personal range” |
| Polish that cites `verdict_note` | “Falls inside the last-90-day normal range” |

**PHA guarantee**: mean / range / verdict come from SQL + the compute layer, not LLM arithmetic.

**Audit intercepts**: numeric drift, missing items, “clearly high/low” that contradicts verdict.

### 1.2 Type B — no-baseline judgment (forbidden)

**Premise**: `snapshot_only` / `NO_BASELINE` (including deep sleep, REM, workout in the current MVP; reason codes in the Fact Pipeline Spec).

| LLM may | LLM must not |
|----------|----------|
| Report screenshot numbers | Sufficient, normal, low, high, good, excellent, inadequate |
| State clearly “no personal 90-day history, cannot compare” | Population medical-common-sense “is this normal” |
| — | Any number that implies a baseline (“generally should be >1.5 hours”) |

**Typical overreach**: DeepSeek “deep sleep and REM are **fairly sufficient**” — Type B, same family as msg-311 “warehouse-invented stage means” (no personal baseline).

**Principle**: “normal deep sleep” in training data is a **population prior**, not **this user’s 90-day distribution** → in PHA this is **unrooted judgment / pseudo-analysis**.

---

## 2. Compatibility with “doctor interpretation”

User expectation: PHA provides a real lab slip; the LLM interprets like a doctor.

**Architecture answer**:

```text
PHA  = the lab (values + reference interval + whether it sits in the personal interval)
LLM  = the doctor (interpret only when CompareTable already gave a “relative to this person” verdict)
```

| Scene | Doctor-like? |
|------|------------|
| 90d baseline + verdict | ✅ “Relative to your usual, slightly low but still normal” |
| No 90d baseline | ⚠️ Only like a doctor who “saw today’s slip and has no prior chart” — **must not** conclude |

**Judgment PHA does not take on**: diagnosis, prescription, or population norms substituting for a personal baseline, when there is no personal data.

---

## 3. Macro block (`WEARABLE_90D_SUMMARY`) boundary

| Allowed | Forbidden |
|------|------|
| Pearson, month-to-month **change**, unusual-day hints | Copying sleep/HRV/RHR **mean/range** from the macro block for comparison |
| Trends such as “HRV monthly slightly up over the last two months” | Replacing CompareTable as the comparison-number source |

From v2.3.18: the wearable compare-round Summary is **weakened** to a macro trend block (no mean/range), consistent with TASK.

---

## 4. Audit rule family (the Policy compiler)

The following rules **apply uniformly to all models** (Qwen / DeepSeek / …). Case-by-case exemptions are forbidden.

| Rule family | Violation code (example) | Matching Policy |
|--------|----------------|-------------|
| Numeric SSO | `compare_table_numeric_drift` | Only Table-authorized tokens |
| Stage 90d fabrication | `compare_forbidden_90d_stage` | Type B + no invented means |
| Summary hijack | `compare_summary_mean_hijack` | §3 forbidden |
| Incomplete coverage | `compare_incomplete:*` | Broad user “is this normal” must go row by row |
| Verdict contradiction | `compare_verdict_contradiction` | Type A wording must match verdict |
| **No-baseline subjective words** | `compare_no_baseline_subjective:*` | **§5 · 3d-ε P0** |

### 4.1 No-baseline subjective lexicon (v1 · minimal set)

For `NO_BASELINE` / `snapshot_only` rows, the following **evaluative** wording in the answer is a violation (zh and en; configurable to extend):

```text
充足 不足 正常 异常 良好 优异 偏差 偏低 偏高 理想 欠佳
sufficient adequate normal abnormal excellent poor
```

**Do not intercept**: restating screenshot duration + “cannot compare to the past 90 days”.

**Span matching**: same as `compare_forbidden_90d_stage`; do not join across paragraphs (v2.3.17+ in-span match).

---

## 5. Fallback vs Policy

| Component | Role |
|------|------|
| `compare_table_to_user_summary` | Policy-compliant **deterministic** narrative template |
| `apply_compare_table_fallback_if_needed` | **Hybrid exit** when Audit fails (v2.3.26+) |

**Hybrid Fallback**: first emit `compare_table_to_user_summary` (SSO comparison numbers), then **keep** fact-based “advice / in summary / sleep interpretation” paragraphs from the LLM (`extract_llm_health_advisory`). Paragraphs that invent numbers are still dropped.

Fallback is **not** “sleep 8h43 dedicated copy”; the comparison block walks CompareTable rows; health advice comes from compliant LLM narrative.

---

## 6. Soul / TASK alignment (`wearable_screenshot_review`)

| Component | Requirement |
|------|------|
| `PHA_WEARABLE_SOUL_MINIMAL` | No three-step consult, Patient State, or unrooted comparison |
| `WEARABLE_SCREENSHOT_REVIEW_TASK` | Item-by-item coverage; copy comparison numbers only from CompareTable |
| Global `PHA_MEDICAL_SOUL` | **Must not** be injected into this profile (prevent instruction collision) |

---

## 7. Implementation waves (doc → code)

| Wave | Content | Status |
|------|------|------|
| **3d-γ** | CompareTable SSO + Audit + Fallback | ✅ encoded |
| **3d-γ-ux** | Soul split · macro Summary denoise · LLM table · UI shows `answer_text` | ✅ v2.3.17–18 |
| **3d-ε** | Interpretation Policy audit: `compare_no_baseline_subjective` | ✅ encoded in v2.3.19 |
| **3d-ε** | `respiratory_rate` into CompareTable comparable | ✅ encoded in v2.3.19 |
| **3d-δ** | Fact Pipeline: stage/workout daily rollup → rows upgrade to `comparable_90d` | 📋 see dedicated doc |

---

## 8. Revision history

| Version | Date | Notes |
|------|------|------|
| **v1.0** | 2026-06-01 | First edition: two kinds of judgment · no-baseline subjective words · aligned with Gemini/Cursor architecture |

# Manifest Tier v1: disclosure-protocol edition (Design RFC)

> **Language / 语言**：English (this document) · [中文](manifest-tier-v1.md)

> **Status**:**Approved** — implementation waits for 文辉 confirmation; default audit behavior remains `t0_strict`  
> **Baseline build**: `pha-v2.2.11-a-plus`  
> **Related docs**: [`harness-numerics-manifest-v2.2.6.2-min.md`](harness-numerics-manifest-v2.2.6.2-min.md), [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md)  
> **Revision date**: 2026-05-24 (v1.1 — absorbed Grok / Gemini audit comments)  
> **What this supersedes**: this edition **does not adopt** Schema T1 injection / offline distillation / Harness knowledge-pack sidecar schemes

---

## 0. Purpose

The combined E2E yellow light (`unauthorized_value:3.4`) exposed a **C-layer audit domain that is too wide**, not an A+ routing failure. While citing user Manifest ground truth (T0), the model also emitted an LLM-internalized guideline reference (e.g. LDL ideal upper bound 3.4 mmol/L), which the current rule intercepts indiscriminately.

This document defines **Manifest Tier v1 (disclosure-protocol edition)**:

- **T0**: Harness is responsible only for measured values in the user store; **strict whitelist audit** (current spirit unchanged).
- **T1**: LLM-internalized medical/guideline reference values; **not injected into Manifest, not written to Schema, not verified by PHA**; only a **disclosure format** is required; the user verifies.
- **T2**: Model inference/estimate; Prompt constraint + audit warning (v1 does not force block).

**Core principle**: Harness owns data, the LLM owns common-sense phrasing, the user owns verification.

---

## 1. Problem statement and root cause

### 1.1 Yellow-light phenomenon

| Item | Fact |
|----|------|
| Profile | `combined_review` ✅ |
| User ground-truth citations | `4.05`, `2.45`, `33.05`, etc. inside Manifest ✅ |
| Intercepted item | `unauthorized_value:3.4` |
| Model wording (illustrative) | “Ideal value should be below **3.4** mmol/L” |

### 1.2 Current C-layer rule (as-is)

`audit_response_numerics()` on decimals in the answer in the **0.5–15.0** range: if not in `manifest.allowed_values` and not dose context → `unauthorized_value:{token}`.

The rule **does not distinguish** “user lab value” from “guideline reference value”, so it false-kills T1.

### 1.2a fact_card policy (`manifest.profile == "fact_card_interpret"`, M1-P9.4)

Fact-card interpretation uses a separate audit policy (`audit_scope=fact_card`) and **does not** apply the 0.5–15 decimal band. It grades by **clause context**:

| Level | Rule | Behavior |
|----|------|------|
| S | Date/time; non-zero decimal; personal-claim clause (possession / time / measurement words); card label or unit with no educational words | `unauthorized_*`, reject the whole span |
| E | Integers under population/advice/reference words; bare integers with no possession, no label, no unit | Pass, telemetry `educational_ints` |
| T1 | Complete disclosure block (zh/en `LANG_DISCLOSURE_MAP`) | Do not verify numbers inside the block; possession words inside the block → `t0_forgery_in_t1_block` |

Digits inside identifiers (letter-adjacent) do not count. Lexicon lives in `LANG_T0_CLAIM_MAP`; labels/units come from the card; Python does not write metric names. Details and 18 cases: [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) §2.

### 1.3 Problems this scheme **does not** solve

- Does not verify whether 3.4 matches the latest *Chinese Guidelines for the Prevention and Treatment of Dyslipidemia in Adults* — **intentionally not done**.
- Does not eliminate LLM authority hallucination (e.g. fake guideline name + fake 4.2) — **product risk is borne by disclosure + user verification**.
- Does not expand Harness operational responsibility for medical common sense.

---

## 2. Responsibility boundary (product / compliance)

```text
┌─────────────────────────────────────────────────────────────┐
│ PHA / Harness (T0)                                          │
│   · Responsible only for measured values imported into      │
│     user SQLite / wearable warehouse                        │
│   · Numerics Manifest = this-round verifiable user-data     │
│     whitelist                                               │
│   · Wrong user number → C-layer block (100% physical        │
│     reconciliation)                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LLM (T1 / T2)                                               │
│   · May cite internalized guidelines, textbooks, ideal      │
│     ranges, etc.                                            │
│   · Must mark “not personal lab data” + source + verify     │
│     yourself per the disclosure protocol                    │
│   · PHA does not endorse T1 numeric correctness             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ User                                                        │
│   · Verify T1 references themselves and follow medical      │
│     advice                                                  │
│   · UI / disclaimer: see §9                                 │
└─────────────────────────────────────────────────────────────┘
```

**Divergence from the Gemini/Grok “Schema T1 injection” route (intentional)**:

| Dimension | Injection route | Disclosure-protocol edition (this doc) |
|------|----------|-------------------|
| Who maintains 3.4 | Developer / Schema / CI distill | Nobody; LLM self-supplies |
| C-layer on 3.4 | Pass if whitelist hit | Pass if inside a disclosure block (no truth check) |
| Legal liability | Platform indirectly endorses the reference | Platform endorses T0 user data only |
| Maintenance cost | Schema PR + guideline sync | No T1 config |

---

## 3. Tier definitions

### 3.1 Overview

| Tier | Name | Source | Enters Manifest? | C-layer v1 policy |
|------|------|------|-----------------|--------------|
| **T0** | User measured evidence | SQLite `medical_reports`, wearable summaries | ✅ yes | **Strict**: numbers/dates must ⊆ whitelist |
| **T1** | External reference standard | LLM internalized knowledge | ❌ no | **Disclosure**: do not verify numbers; verify format; bare run is a violation |
| **T2** | Model inference | LLM generated | ❌ no | **warn**: require “estimate/possibly”-class cue; v1 does not block |

### 3.2 T0 — user measured evidence

**Semantics**: numbers and dates traceable to this-round `NumericsManifest` KV.

**ManifestEntry unchanged** (see existing docs):

- `domain`: `lipid` | `wearable`
- `metric`, `value`, `unit`, `anchor`, `source`

**Audit invariants** (still hold under `PHA_NUMERICS_AUDIT_SCOPE=t0_plus_disclosure`):

1. Known hallucination dates / future dates / unauthorized lab dates → block  
2. Lab-range decimals appearing in **T0 claim context** → must ∈ `allowed_values`  
3. `require_citation` (combined + `PHA_NUMERICS_REQUIRE_CITATION=1`) → must cite ≥1 T0 date or lipid value  

### 3.3 T1 — external reference standard (LLM domain)

**Semantics**: guideline lines, ideal upper bounds, population reference ranges that are not the user’s personal lab results.

**Forbidden**:

- Writing `reference_values` / `T1_reference` into `*.schema.json`
- Merging guideline constants in `build_numerics_manifest()`
- Injecting a “medical knowledge pack” block into Tier0

**Allowed**:

- The LLM giving 3.4, 2.6, 6.1, etc. in the answer, **but they must** fall inside a §4 disclosure block.

### 3.4 T2 — model inference (v1 lenient)

**Semantics**: “next LDL may drop to…” / “I infer your…”

**v1 policy**:

- Prompt requires “estimate / possibly / infer” labeling
- Audit: `missing_inference_cue` → **warning** only, does not make `passed=false`
- v2 may require an independent disclosure block like T1

---

## 4. T1 disclosure protocol (Out-of-Manifest Reference Protocol)

### 4.1 Normative format (7B-friendly compact edition · bilingual)

> **v1.1**: the compact edition is the only normative format.  
> **v1.2 (implementation)**: audit features live in `LANG_DISCLOSURE_MAP`; when **adding a language**, only append a MAP entry and recompile regex; do not scatter literals on the `audit_*` main path.

**Chinese**:

```text
【参考标准】<描述>（来源：<指南名>，请自行查证，非医疗建议）
```

**English**:

```text
[Reference Standard] <description> (source: <name>, verify by yourself, not medical advice)
```

**T0 precedes T1 (audit principle)**: in the same answer, numbers in “您的/your/report/化验/Manifest date” context **always reconcile against the T0 whitelist**; only when the number sits inside a **masked T1 disclosure block** is T0 bare-run intercept skipped. T0 forbidden words inside a T1 block are banned (`t0_forgery_in_t1_block`).

**Mixed zh/en**: the same round may contain both a Chinese block and an English block; `extract_disclosure_blocks` takes the bilingual union mask, then runs T0 audit (see case A-mix).

**Example (compliant)**:

```text
【参考标准】部分指南将 LDL 理想上限定在 3.4 mmol/L 以下（来源：中国成人血脂异常防治指南，请自行查证，非医疗建议）
```

```text
【参考标准】普通人群空腹血糖参考上限约为 6.1 mmol/L（来源：糖尿病防治指南摘要，请自行查证，非医疗建议）
```

**Compatible aliases (auditor accepts as equivalent)**:

- Block header may also be `【参考标准·非个人化验数据】` (longer; not recommended in Prompt)
- Disclaimer may also be `不构成医疗建议` or `不能替代医嘱` (equivalent to `非医疗建议`)

### 4.2 Minimum Viable Disclosure

The auditor checks four elements M1–M4 on **each disclosure block**:

| # | Element | Allowed keywords / patterns |
|---|------|---------------------|
| M1 | Non-personal statement | Block header must match `【参考标准` |
| M2 | Source | `来源：` or `来源:` followed by non-empty text (≥4 characters) |
| M3 | Self-verify | `请自行查证` or `请自行核对` |
| M4 | Disclaimer | `非医疗建议` or `不构成医疗建议` or `不能替代医嘱` |

**Block boundary**: from `【参考标准` through the closing parenthesis `）` that contains M2–M4 (implementation in §6).

**M4 soft degrade (Grok audit comment · v1.1)**:

| `PHA_NUMERICS_T1_M4_MODE` | M1+M2+M3 hold, M4 missing | Behavior |
|---------------------------|----------------------|------|
| `strict` (E2E default) | — | `t1_disclosure_incomplete` → **block** |
| `warn` (7B production recommended) | missing M4 | `passed=true` + warning `t1_missing_disclaimer` |
| `off` | — | same as `strict` (debug only) |

> Bare T1 decimals (no disclosure block) are **not** affected by M4 softness; they remain `unauthorized_value`.

### 4.3 Forbidden patterns (anti-patterns)

| Anti-pattern | violation |
|--------|-----------|
| “Your LDL ideal value should be below 3.4” (no disclosure block) | `unauthorized_value:3.4` |
| “Per the lab, your LDL is 3.4” (Manifest is 2.45) | `unauthorized_value:3.4` |
| Disclosure block writes “your report date 2023-12-15 LDL 3.4” (Manifest is 4.05) | **`t0_forgery_in_t1_block`** (Gemini: T0 forgery wearing a T1 shell, severe block) |
| Disclosure block has `您的` + Manifest date + a value that conflicts with the whitelist | **`t0_forgery_in_t1_block`** |
| Only “generally below 3.4” with no disclosure block | `unauthorized_value:3.4` |

**T0 forbidden-word list inside T1 blocks (scan the disclosure block at implement time)**:

`您的`, `你的是`, `你的`, `化验日期`, `报告日期`, `检验报告`, `上次化验`, `个人化验`

### 4.4 Coexistence with T0 in the same span

The same answer **may do T0 then T1**, for example:

```text
您的 LDL 从 2023年12月15日 的 4.05 mmol/L 降至 2025年12月7日 的 2.45 mmol/L。

【参考标准】部分指南将 LDL 理想上限定在 3.4 mmol/L 以下（来源：中国成人血脂异常防治指南，请自行查证，非医疗建议）
```

- First sentence `4.05`, `2.45`, dates → **T0 audit**  
- Second-sentence block `3.4` → **T1 disclosure audit**, do not verify whether 3.4 is true  

---

## 5. Split-domain audit logic (Design Spec)

### 5.1 Audit modes

| `PHA_NUMERICS_AUDIT_SCOPE` | Behavior |
|----------------------------|------|
| `t0_strict` (**default, current behavior**) | Whole-answer 0.5–15 decimals ⊆ whitelist, else `unauthorized_value` |
| `t0_plus_disclosure` | §5.2 split-domain logic |

**Other env vars unchanged**: `PHA_NUMERICS_AUDIT` (warn/block/off), `PHA_NUMERICS_REQUIRE_CITATION`.

New optional:

| Variable | Default | Notes |
|------|------|------|
| `PHA_NUMERICS_T1_DISCLOSURE` | `required` | Bare T1 decimal: `required`=block; `warn`; `off` (debug) |
| `PHA_NUMERICS_T1_M4_MODE` | `warn` | M4 disclaimer softness: `strict` / `warn` / `off` (§4.2) |
| `PHA_NUMERICS_INFERENCE_CUE` | `warn` | Level when T2 is missing a cue |

### 5.2 `t0_plus_disclosure` algorithm (pseudocode)

```text
INPUT: answer_text, manifest, require_citation

1. Extract all T1 disclosure blocks DISCLOSURE_BLOCKS (§4 boundary rules)
2. Mask character ranges occupied by DISCLOSURE_BLOCKS from answer_text → masked_text

3. T0 date audit (on masked_text, same rules as current):
   - forbidden_date / future_date / unauthorized_date

4. T0 numeric audit (on masked_text):
   FOR each decimal token t in 0.5..15.0:
     IF t in manifest.allowed_values: CONTINUE
     IF t in dose_context: CONTINUE
     IF t appears in T0 claim context (§5.3):
        VIOLATION unauthorized_value:t
     ELSE IF t is not inside any disclosure block:
        VIOLATION unauthorized_value:t   # bare-run decimal

5. T1 disclosure audit:
   FOR each disclosure block B:
     IF B contains T1 forbidden words (§4.3) and conflicts with T0:
        VIOLATION t0_forgery_in_t1_block
     FOR each lab-like decimal t in B:
       IF B does not satisfy M1–M3:
          VIOLATION t1_disclosure_incomplete:t
       ELIF B missing M4:
          IF T1_M4_MODE == strict: VIOLATION t1_disclosure_incomplete:t
          ELIF T1_M4_MODE == warn: WARNING t1_missing_disclaimer:t
       ELSE:
          WARNING t1_unverified_reference:t   # format compliant, no truth check

6. require_citation (combined): check T0 citations on masked_text (current logic)

7. passed = violations empty
```

**Key points**:

- **Mask first**: numbers inside disclosure blocks **do not participate** in T0 whitelist check, and **do not participate** in `unauthorized_value` bare-run check (already in-block).
- **Outside the block**, 0.5–15 decimals: still treated as current strict → prevent silent fabrication.
- Numbers in **T0 claim context**: even outside dose context, **must** hit the whitelist.

### 5.3 T0 claim context (Heuristic)

If **any** of the following holds, the window around the token is T0 claim (window = 48 characters before and after the token):

| Signal | Example |
|------|------|
| Manifest date nearby | Window contains a day from `allowed_dates` (zh / ISO format) |
| Possession / report cue | `您的`, `你的是`, `报告`, `化验`, `检验`, `上次`, `历史` |
| Metric + number structure | `LDL`/`HDL`/`TC`/`TG`/`血脂`/`HRV`/`血氧` + number |
| Manifest value nearby | Window contains a “compare sentence” whose value differs from some allowed_value by ≤0.15 (e.g. “from 4.05 down to 2.45”) |

**Deliberately unused** as T0-pass evidence: “ideal / guideline / reference” — those belong inside T1 disclosure-block wording.

### 5.4 Violation types (v1 extension)

| violation | Severity | Meaning |
|-----------|--------|------|
| `unauthorized_value:{t}` | block | Unauthorized decimal outside a block or in T0 context |
| `unauthorized_date:{d}` | block | Same as current |
| `forbidden_date:{d}` | block | Same as current |
| `future_date:{d}` | block | Same as current |
| `missing_ground_truth_citation` | block | No T0 citation when require_citation |
| `t1_disclosure_incomplete:{t}` | block | Missing M1–M3, or missing M4 in strict mode |
| `t1_missing_disclaimer:{t}` | warning | Missing M4 in warn mode |
| `t0_forgery_in_t1_block` | block | Forged T0 user data inside a disclosure block (§4.3) |
| `t1_unverified_reference:{t}` | warning | Format compliant; PHA does not verify guideline truth (including fake guideline names) |
| `missing_inference_cue` | warning | T2 missing estimate label |

### 5.5 `apply_numerics_audit_to_answer` copy (block mode)

When scope=`t0_plus_disclosure`, intercept copy **distinguishes** T0 / T1:

```text
【PHA 数字合规审计未通过，本轮答复已拦截】
违规项：<violations>
· 您的个人化验/穿戴数据：请仅引用 Numerics Manifest 白名单中的报告日与数值。
· 参考标准/指南数值：请使用【参考标准】…（来源：…，请自行查证，非医疗建议）格式。
若库内无该指标，应明确写「库内无该指标」。
```

---

## 6. Implementation reference (regex sketch, not production code)

For implement-phase Review; **this document does not require immediate encoding**.

```python
# T1 disclosure block (7B-friendly compact edition)
DISCLOSURE_BLOCK_RE = re.compile(
    r"【参考标准[^】]*】.*?"
    r"（来源[^）]{4,}，请自行查证[^）]*）",
    re.S,
)

T0_FORBIDDEN_IN_T1_RE = re.compile(
    r"您的|你的是|你的|化验日期|报告日期|检验报告|上次化验|个人化验",
)

def disclosure_block_compliant(block: str, *, m4_mode: str = "warn") -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if T0_FORBIDDEN_IN_T1_RE.search(block):
        return False, ["t0_forgery_in_t1_block"]
    has_m1 = block.startswith("【参考标准") or "【参考标准" in block[:20]
    has_source = bool(re.search(r"来源[:：]\s*\S{4,}", block))
    has_verify = any(k in block for k in ("请自行查证", "请自行核对"))
    has_m4 = any(k in block for k in ("非医疗建议", "不构成医疗建议", "不能替代医嘱"))
    if not (has_m1 and has_source and has_verify):
        return False, ["t1_disclosure_incomplete"]
    if not has_m4 and m4_mode == "strict":
        return False, ["t1_disclosure_incomplete"]
    if not has_m4 and m4_mode == "warn":
        warnings.append("t1_missing_disclaimer")
    return True, warnings
```

**7B friendliness**: Prompt **gives only one §4.1 compact-edition example**; Task lists the M1–M4 four-element checklist.

---

## 7. Prompt contract (Task / System, not Manifest injection)

### 7.1 Applicable profiles

- `combined_review`
- `lab_cross_year` (if output includes guideline comparison)
- Optional: `supplement_manifest` when comparing dose vs guideline upper bound

**Do not modify** existing Task for `wearable_only` / `casual` (unless wearable later also needs T1 references).

### 7.2 Task addendum (draft)

```text
【数字与引用契约 · Manifest Tier】
1. 以下为您的个人化验/穿戴数据（T0）：必须来自 Numerics Manifest；写清报告日/区间与数值。
2. 指南/理想线等非个人数据（T1），必须使用单行格式（请仿写）——
   「【参考标准】…（来源：xxx，请自行查证，非医疗建议）」
   示例：「【参考标准】LDL 理想上限常见为 3.4 mmol/L 以下（来源：中国成人血脂异常防治指南，请自行查证，非医疗建议）」
   本系统不验证该数值是否与最新指南一致。
3. 禁止将参考标准数字写成「您的化验结果」；禁止在【参考标准】块内写「您的」「化验日期」等个人数据措辞。
4. 推测/预测（T2）须标注「可能/估算/推测」，示例：「估算您的 HRV 可能随训练量缓慢回升」——避免与 Manifest 数字混写。
```

**Explicitly not written**: a concrete T1 number list — avoid injecting knowledge via Prompt.

### 7.3 Manifest Tier0 block copy (T0 explicit mark · Grok audit comment)

In `format_manifest_tier0_block` header **add** (at implement time):

```text
【T0 · 您的个人化验/穿戴实测值 · 以下 KV 为库内真值，答复中引用须严格一致】
格式：domain|anchor|metric|value|unit
…
引用指南/理想线请用【参考标准】披露格式；该数值不在此白名单内，PHA 不对其准确性负责。
```

---

## 8. Acceptance criteria

### 8.1 Regression: current behavior unchanged

When `PHA_NUMERICS_AUDIT_SCOPE=t0_strict` (default):

- `pha_numerics_manifest_selfcheck.py` results **identical** to `v2.2.11-a-plus`
- All existing golden dry-runs **no diff**

### 8.2 New mode: `t0_plus_disclosure`

| # | Case | Expectation |
|---|------|------|
| A | combined ground truth + in-block 3.4 + complete disclosure | `passed=true` |
| B | combined ground truth + “ideal line 3.4” no block | `passed=false`, `unauthorized_value:3.4` |
| C | Manifest LDL 2.45, write “your LDL 3.8” | `passed=false`, `unauthorized_value:3.8` |
| D | In-block 3.4 but missing “请自行查证” | `passed=false`, `t1_disclosure_incomplete:3.4` |
| D′ | In-block 3.4, M1–M3 complete, missing M4, `T1_M4_MODE=warn` | `passed=true`, warning `t1_missing_disclaimer` |
| E | In-block fake 4.2 + complete format (authority hallucination) | `passed=true`, warning `t1_unverified_reference:4.2` |
| H | In-block 3.4 + **fake guideline name** + complete format (Grok addendum) | `passed=true`, warning `t1_unverified_reference:3.4`; **explicitly do not verify source authenticity** |
| I | In-block “your LDL 3.4” + format shell | `passed=false`, `t0_forgery_in_t1_block` |
| F | `2026-04-30` hallucination date | `passed=false` (T0 rules unchanged) |
| G | require_citation + T1 only, no T0 citation | `passed=false`, `missing_ground_truth_citation` |
| **A-mix** | T0 + Chinese block + English block same round | `passed=true` |

### 8.3 E2E

| Script | scope / flags | Expectation |
|------|---------------|------|
| `pha_e2e_qwen_combined.py` | `t0_plus_disclosure`, `T1_M4_MODE=warn` | Turn2 `numerics_audit.passed=true` (allow warning-only if the model omits M4) |
| `pha_e2e_qwen_combined.py` | same + `T1_M4_MODE=strict` | Optional stricter regression; should still be green when model format is compliant |
| `pha_e2e_qwen_spo2_sleep.py` | default | behavior unchanged |
| `pha_e2e_qwen_supplement.py` | default | behavior unchanged |

---

## 9. Risks and mitigations

| Risk | Notes | Mitigation |
|------|------|------|
| **Authority hallucination** | LLM may still write a wrong 4.2 inside a disclosure block | Product disclaimer; T1 warning telemetry; **do not accept Harness truth-checking** |
| **Low 7B format compliance** | Omits the disclosure block | Prompt example + E2E regression; early `PHA_NUMERICS_AUDIT=warn` |
| **T0/T1 boundary misclassify** | False-kill 3.4 outside the block, or leak inside | golden set 20+ sentences; tunable window 48→64 |
| **User ignores “请自行查证”** | Compliant but misleading | Fixed UI footnote (below) |

**Suggested UI footnote (product layer, not Harness data)**:

> Content marked “【参考标准】” is AI-generated, not verified by PHA, cannot replace a physician’s diagnosis; please verify against authoritative sources yourself.

---

## 10. Migration and rollback

```text
Phase 0 (current)
  PHA_NUMERICS_AUDIT_SCOPE undefined → equivalent to t0_strict

Phase 1 (after implementation · dev / E2E)
  PHA_NUMERICS_AUDIT_SCOPE=t0_plus_disclosure
  PHA_NUMERICS_REQUIRE_CITATION=1
  PHA_NUMERICS_T1_M4_MODE=warn          # 7B-friendly; strict for tighter regression

Phase 2 (production switch)
  Production set to t0_plus_disclosure + T1_M4_MODE=warn; monitor violations / warnings JSONL

Rollback
  PHA_NUMERICS_AUDIT_SCOPE=t0_strict → instant return to v2.2.11 audit behavior
```

**Relation to A+ / Catalog**: this RFC **only touches L2 C-layer audit + L3 Prompt contract**; it does not modify SchemaIntentRouter, TurnEvidencePlan state machine, or Catalog second-round flow.

---

## 11. Explicit non-goals

- ❌ `*.schema.json` adding `reference_values` / `T1_reference` / `knowledge_base`
- ❌ Offline `distill_metrics_reference.py` writing Schema
- ❌ `build_numerics_manifest()` merging guideline constants
- ❌ Tier0 injecting “Protected Knowledge Channel” body
- ❌ C-layer semantically understanding “this is a guideline so pass” **with no disclosure block**
- ❌ PHA taking responsibility for T1 numeric correctness

---

## 12. Implementation checklist (approved · encode after 文辉 confirms)

| # | Module | Change summary | Estimate |
|------|------|----------|------|
| 1 | `pha/numerics_manifest.py` | `numerics_audit_scope()`, `numerics_t1_m4_mode()` | 0.5h |
| 2 | `pha/numerics_manifest.py` | Disclosure-block extract + mask + split-domain audit + new violation types | 2h |
| 3 | `pha/numerics_manifest.py` | `format_manifest_tier0_block` T0 header (§7.3) | 0.5h |
| 4 | `pha/harness_plan.py` | combined/lab Task addendum §7.2 (compact format + T2 example) | 0.5h |
| 5 | `pha/evidence_catalog.py` or `combined_catalog_task_text` | If Task copy is centralized here, sync §7.2 | 0.25h |
| 6 | `scripts/pha_numerics_manifest_selfcheck.py` | Cases A–I + strict/warn dual mode | 1h |
| 7 | `docs/harness-numerics-manifest-v2.2.6.2-min.md` | Link Tier v1 + new env table | 0.25h |
| 8 | `docs/pha-architecture-evolution-v2.3.md` | §1.4(B) points at the disclosure-protocol edition | 0.25h |
| 9 | `pha/build_marker.py` | → `pha-v2.2.12-manifest-tier-v1` (after implementation) | — |

**Do not change**: SchemaIntentRouter, TurnEvidencePlan state machine, Catalog second round, `chat_service` core flow.

---

## 13. External audit record (v1.1)

| Auditor | Score | Conclusion | Absorbed comments |
|--------|------|------|------------|
| Grok | 9.2/10 | Approve implementation | M4 soft degrade; T0 header; case H; T2 Task example |
| Gemini | 100/architecture | Approve implementation | 7B compact disclosure format; `t0_forgery_in_t1_block` severe violation |

**Cursor ruling**: both audits approve; v1.1 has merged the above. **Implementation gate**: execute after 文辉 signs §15 of this file.

---

## 14. Appendix: alignment with pha-architecture-evolution-v2.3

`pha-architecture-evolution-v2.3.md` §1.4(B) once suggested “write T1 into Schema reference_values”. **This document supersedes that suggestion**, replacing it with:

- T1 = **LLM out-of-domain + disclosure protocol**
- Stage 1 closeout = implement `t0_plus_disclosure` + E2E all green, **not** Schema distillation

Stage 2 Metadata Catalog / Shadow Routing **are not affected by this document**.

---

## 15. Implementation plan (execute after 文辉 confirms)

### 15.1 Goals

- combined E2E Turn2: `numerics_audit.passed=true` (eliminate `unauthorized_value:3.4`)
- Default `t0_strict` zero regression; new capability only under `t0_plus_disclosure`

### 15.2 Execution order (single PR, ~5–6h)

```text
Step 1  numerics_manifest.py — helper + disclosure-block parse + mask audit core
Step 2  numerics_manifest.py — format_manifest_tier0_block header
Step 3  harness_plan / combined_catalog_task_text — Task §7.2
Step 4  pha_numerics_manifest_selfcheck — cases A–I (offline)
Step 5  Regression: scope=t0_strict → bit-identical to v2.2.11 output
Step 6  scope=t0_plus_disclosure + M4=warn → combined E2E
Step 7  golden + spo2/supplement E2E unchanged
Step 8  docs + build_marker + restart 8787
```

### 15.3 Environment matrix (for verification)

| Scene | `AUDIT_SCOPE` | `T1_M4_MODE` | `REQUIRE_CITATION` | Expectation |
|------|---------------|--------------|-------------------|------|
| Production default (not yet switched) | `t0_strict` | — | 0 | Same as current |
| Dev/E2E | `t0_plus_disclosure` | `warn` | 1 | combined green |
| Stricter regression | `t0_plus_disclosure` | `strict` | 1 | selfcheck all green |

### 15.4 Risks and rollback

- **7B still does not write a disclosure block** → E2E may still be yellow; mitigation: Task example + if second round blocks, Harness may append “please rewrite in 【参考标准】 format” (**v1 does not do this**; observe first)
- **Rollback**: one env `PHA_NUMERICS_AUDIT_SCOPE=t0_strict` restores

### 15.5 Deliverables

- [ ] Code Diff (§12 checklist 1–5)
- [ ] selfcheck A–I output screenshot / log
- [ ] combined E2E exit 0 summary
- [ ] `t0_strict` regression PASS note

**Please 文辉 confirm**: reply “确认实现” or point out Flag defaults / disclosure-format wording that need adjustment, then start encoding.

---

## 16. Review Checklist (for 文辉 sign-off)

- [ ] Accept that T1 does not verify truth, only disclosure (including case H fake guideline)  
- [ ] Accept the 7B compact disclosure format (§4.1)  
- [ ] Confirm `T1_M4_MODE` default `warn` (missing disclaimer does not block)  
- [ ] Confirm production stays `t0_strict` until the switch  
- [ ] Confirm UI disclaimer copy (§9)  
- [ ] **Approve §15 implementation plan and authorize encoding**

**Until signed**, keep `v2.2.11-a-plus` audit behavior unchanged.

# Manifest Tier v1 implementation preview (v2.2.12)

> **Language / 语言**：English (this document) · [中文](manifest-tier-v1-impl-preview.md)

> **Status**: Diff / design preview — **code lands after Wenhui Review**  
> **Baseline**: `pha-v2.2.11-a-plus`  
> **Spec**: [`manifest-tier-v1.md`](manifest-tier-v1.en.md) v1.1 + multilingual sandbox addenda  
> **Target build**: `pha-v2.2.12-manifest-tier-v1`

---

## 1. Change overview

| File | Change type | Est. lines |
|------|----------|------|
| `pha/numerics_manifest.py` | **core** | +220 / ~30 edits |
| `pha/evidence_catalog.py` | Task copy | +25 |
| `scripts/pha_numerics_manifest_selfcheck.py` | cases A–I + zh/en | +120 |
| `scripts/pha_e2e_qwen_combined.py` | env hint / optional bilingual asserts | +15 |
| `docs/manifest-tier-v1.md` | §4 §5 bilingual notes | +40 |
| `docs/harness-numerics-manifest-v2.2.6.2-min.md` | env table | +10 |
| `pha/build_marker.py` | version | 1 |

**Do not change**: `chat_service` state machine, `SchemaIntentRouter`, `harness_plan` profile logic (Task copy is centralized in `evidence_catalog.combined_catalog_task_text`).

---

## 2. Feature Flag (defaults locked)

| Variable | Default | Notes |
|------|--------|------|
| `PHA_NUMERICS_AUDIT_SCOPE` | **`t0_strict`** | unset or illegal → strict (production zero behavior change) |
| `PHA_NUMERICS_T1_M4_MODE` | **`warn`** | M1–M3 present, missing M4 → warning, do not fail |
| `PHA_NUMERICS_T1_DISCLOSURE` | `required` | bare T1 decimals still block |
| `PHA_NUMERICS_AUDIT` | `warn` | unchanged |
| `PHA_NUMERICS_REQUIRE_CITATION` | `0` | E2E script sets `1` |

**E2E / dev matrix**:

```bash
PHA_NUMERICS_AUDIT_SCOPE=t0_plus_disclosure \
PHA_NUMERICS_T1_M4_MODE=warn \
PHA_NUMERICS_REQUIRE_CITATION=1 \
PHA_NUMERICS_AUDIT=block \
python scripts/pha_e2e_qwen_combined.py
```

---

## 3. `LANG_DISCLOSURE_MAP` (forbid scattered Chinese hardcoding inside the auditor)

### 3.1 Structure (`numerics_manifest.py` top-level constants)

```python
from typing import TypedDict

class _LangDisclosureSpec(TypedDict):
    id: str
    block_open_re: str          # disclosure-block open (M1)
    block_full_re: str          # full disclosure block (extract + mask)
    source_re: str              # M2
    verify_substrings: tuple[str, ...]   # M3 (any hit)
    disclaimer_substrings: tuple[str, ...]  # M4 (any hit)
    t0_forbidden_in_block_re: str  # T1 shell forbids T0 wording

LANG_DISCLOSURE_MAP: tuple[_LangDisclosureSpec, ...] = (
    {
        "id": "zh",
        "block_open_re": r"【参考标准[^】]*】",
        "block_full_re": (
            r"【参考标准[^】]*】.*?"
            r"[（(]来源[:：][^）)]{4,}[，,][^）)]*?(?:请自行查证|请自行核对)[^）)]*?[）)]"
        ),
        "source_re": r"来源[:：]\s*\S{4,}",
        "verify_substrings": ("请自行查证", "请自行核对"),
        "disclaimer_substrings": ("非医疗建议", "不构成医疗建议", "不能替代医嘱"),
        "t0_forbidden_in_block_re": (
            r"您的|你的是|你的|化验日期|报告日期|检验报告|上次化验|个人化验"
        ),
    },
    {
        "id": "en",
        "block_open_re": r"\[(?:Reference Standard|Ref\. Standard)[^\]]*\]",
        "block_full_re": (
            r"\[(?:Reference Standard|Ref\. Standard)[^\]]*\].*?"
            r"[\(（]source\s*[:：]\s*[^）)]{4,}\s*[,，]\s*"
            r"(?:verify by yourself|please verify independently)[^）)]*?"
            r"(?:[,，]\s*(?:not medical advice|not a substitute for medical advice))?"
            r"[\)）]"
        ),
        "source_re": r"source\s*[:：]\s*\S{4,}",
        "verify_substrings": (
            "verify by yourself",
            "please verify independently",
            "verify independently",
        ),
        "disclaimer_substrings": (
            "not medical advice",
            "not a substitute for medical advice",
            "not medical advice)",
        ),
        "t0_forbidden_in_block_re": (
            r"\byour\b|\byours\b|your lab|your report|report date|test date|"
            r"personal lab|my lab results",
        ),
    },
)

# Precompile: DISCLOSURE_BLOCK_RES[id] = re.compile(..., re.I | re.S)
# Runtime extract: finditer all langs' block_full_re on text, merge intervals, then mask
```

### 3.2 Design constraints (addenda 5–7)

1. **Audit main path** (`extract_disclosure_blocks` / `audit_t1_block` / `mask_text`) **only reads `LANG_DISCLOSURE_MAP`**; no bare zh/en literals except the one MAP definition site.
2. **Mask bilingual union**: one answer may contain both Chinese and English blocks; merge intervals then mask once (avoid overlap leaks).
3. **T0 claim context** is likewise extracted into `LANG_T0_CLAIM_MAP` (peer of the disclosure MAP) so `_looks_like_lab_citation` does not scatter more Chinese.

### 3.3 Spec format (Prompt aligned with audit)

**Chinese (§4.1)**:

```text
【参考标准】…（来源：xxx，请自行查证，非医疗建议）
```

**English (new §4.1-en)**:

```text
[Reference Standard] … (source: xxx, verify by yourself, not medical advice)
```

Parentheses `()` / `（）` both accepted; separators `,` / `，` both accepted.

---

## 4. `numerics_manifest.py` function Diff preview

### 4.1 New exports

```python
def numerics_audit_scope() -> str:
    raw = os.environ.get("PHA_NUMERICS_AUDIT_SCOPE", "t0_strict").strip().lower()
    if raw in ("t0_plus_disclosure", "disclosure", "tier_v1"):
        return "t0_plus_disclosure"
    return "t0_strict"

def numerics_t1_m4_mode() -> str:
    raw = os.environ.get("PHA_NUMERICS_T1_M4_MODE", "warn").strip().lower()
    if raw in ("strict", "warn", "off"):
        return raw
    return "warn"
```

### 4.2 New internal API

```python
def _compile_disclosure_patterns() -> dict[str, re.Pattern[str]]: ...

def extract_disclosure_blocks(text: str) -> list[tuple[int, int, str, str]]:
    """Returns [(start, end, block_text, lang_id), ...] sorted, non-overlapping."""

def mask_disclosure_blocks(text: str, blocks: list[tuple[int, int, ...]]) -> str:
    """Replace block ranges with spaces (same len) to preserve indices optional; or join skip."""

def audit_disclosure_block(block: str, lang_id: str, *, m4_mode: str) -> tuple[list[str], list[str]]:
    """Returns (violations, warnings) for single block."""

def block_contains_t0_forgery(block: str, lang_id: str, manifest: NumericsManifest) -> bool:
    """T0 forbidden words + optional: in-block decimal conflicts with manifest near a user-claim cue."""

def _audit_response_numerics_strict(...) -> dict:
    """Move current audit_response_numerics logic as-is, no line edits."""

def _audit_response_numerics_t0_plus_disclosure(...) -> dict:
    """§5.2 domain split + bilingual blocks."""

def audit_response_numerics(...):
    if numerics_audit_scope() == "t0_plus_disclosure":
        return _audit_response_numerics_t0_plus_disclosure(...)
    return _audit_response_numerics_strict(...)
```

### 4.3 `audit_response_numerics` entry Diff (conceptual)

```diff
 def audit_response_numerics(answer_text, manifest, *, require_citation=False):
+    if numerics_audit_scope() == "t0_plus_disclosure":
+        return _audit_response_numerics_t0_plus_disclosure(
+            answer_text, manifest, require_citation=require_citation,
+        )
     text = answer_text or ""
     violations: List[str] = []
     ...  # existing strict logic stays in this body or _strict subfunction
```

### 4.4 `format_manifest_tier0_block` Diff (conceptual)

```diff
     header = (
-        "【Numerics Manifest · 机器白名单 · 答复中化验/穿戴数字必须 ⊆ 下列 KV】\n"
-        "格式：domain|anchor|metric|value|unit\n"
+        "【T0 · Personal lab/wearable values · 您的个人化验/穿戴实测值】\n"
+        "Numerics Manifest (T0): reply citations must match KV below.\n"
+        "格式 / format: domain|anchor|metric|value|unit\n"
+        "Guide/reference values (T1): use 【参考标准】 or [Reference Standard] disclosure; "
+        "not in this whitelist.\n"
     )
```

Empty-manifest branch also adds one T0/T1 note (one zh + one en sentence, still in the header constant string, **not** into MAP).

### 4.5 `apply_numerics_audit_to_answer` Diff (conceptual)

Block-mode failure copy adds bilingual T1 format hint (constant `BLOCK_MSG_T1_HINT`, one zh + one en line).

---

## 5. `LANG_T0_CLAIM_MAP` (T0 claim context · bilingual)

Defined at the same layer as the disclosure MAP, for `unauthorized_value` on **masked_text**:

```python
LANG_T0_CLAIM_MAP = {
    "owner_cues": (
        "您的", "你的", "你的是",
        "your", "yours", "your lab", "your ldl",
    ),
    "report_cues": (
        "报告", "化验", "检验", "report", "lab result", "test result",
    ),
    "metric_cues": (
        "LDL", "HDL", "TC", "TG", "血脂", "胆固醇", "HRV", "spo2", "blood oxygen",
    ),
}
```

`_token_in_t0_claim_context(text, token, window=48)`: if the window hits any owner/report/metric cue and token is 0.5–15 → must ∈ allowed_values.

**`_looks_like_lab_citation`**: keep current logic; cue tuples move into MAP (zh/en side by side); the function only iterates MAP.

---

## 6. `evidence_catalog.combined_catalog_task_text` Diff preview

**Append** after the existing “numeric citation contract” paragraph (constant `MANIFEST_TIER_TASK_APPENDIX`):

```text
【Manifest Tier · T0/T1 · 中英披露协议】
· T0 个人数据：必须来自 Numerics Manifest / 点单证据。
· T1 指南/理想线（非个人数据）须用披露块：
  中文：「【参考标准】…（来源：xxx，请自行查证，非医疗建议）」
  English: "[Reference Standard] … (source: xxx, verify by yourself, not medical advice)"
· 禁止在披露块内写「您的/your」个人化验措辞；禁止将参考值写成您的化验结果。
· 推测用 may/estimate/可能/估算 标注。
示例 EN: [Reference Standard] LDL ideal upper limit is often below 3.4 mmol/L
(source: clinical guidelines, verify by yourself, not medical advice)
```

**Do not** inject the specific 3.4 as knowledge in the Prompt; the example is format-only.

---

## 7. Selfcheck case matrix (`pha_numerics_manifest_selfcheck.py`)

| ID | Lang | Input summary | scope | Expect |
|------|------|----------|-------|------|
| A | zh | T0 truth + 【参考标准】3.4 complete | plus | pass |
| A-en | en | T0 + [Reference Standard] 3.4 full | plus | pass |
| B | zh | ideal line 3.4 no block | plus | unauthorized_value:3.4 |
| B-en | en | ideal 3.4 bare | plus | unauthorized_value:3.4 |
| C | zh | 您的 LDL 3.8 (manifest 2.45) | plus | unauthorized_value:3.8 |
| D | zh | in-block 3.4 missing verify | plus | t1_disclosure_incomplete |
| D′ | zh | in-block 3.4 M1–M3 missing M4 | plus + M4=warn | pass + warning |
| E | zh | fake 4.2 format complete | plus | pass + t1_unverified_reference |
| H | en | fake guide name, format ok | plus | pass + warning |
| I | zh | in-block “您的 LDL 3.4” | plus | t0_forgery_in_t1_block |
| R0 | — | existing GOOD/BAD samples | **strict** | **bit-identical** to v2.2.11 |

---

## 8. E2E expectations

| Script | env | Expect |
|------|-----|------|
| `pha_e2e_qwen_combined.py` | plus + M4=warn + REQUIRE_CITATION=1 | Turn2 `numerics_audit.passed=true` |
| `pha_e2e_qwen_spo2_sleep.py` | default strict | exit 0 unchanged |
| `pha_e2e_qwen_supplement.py` | default strict | exit 0 unchanged |
| `pha_harness_golden_run.py` | default strict | unchanged |

**Note**: combined E2E depends on whether 7B emits a compliant disclosure block; Task appendix + M4=warn raises pass rate. If it still flakes, first check whether `done.numerics_audit.violations` is still a bare 3.4.

---

## 9. Regression guarantee (t0_strict zero change)

Implementation:

1. `audit_response_numerics` branches on the first line; the strict branch = **move the current function body wholesale into `_audit_response_numerics_strict` with no edits**.
2. Selfcheck `R0`: GOOD/BAD asserts identical to today when scope is unset.
3. Local CI: `PHA_NUMERICS_AUDIT_SCOPE=t0_strict python scripts/pha_numerics_manifest_selfcheck.py` must pass.

---

## 10. Risks and mitigation

| Risk | Mitigation |
|------|------|
| English block regex too strict | selfcheck A-en/B-en; zh/en parentheses/commas mutually accepted |
| Bilingual block overlap | extract then merge intervals by start/end |
| 7B omits disclosure block | Task dual examples; E2E uses M4=warn |
| strict regression | R0 case + forbid editing the strict function body |

---

## 11. Land order (after Review)

1. `numerics_manifest.py` — MAP + strict extract + plus branch
2. `evidence_catalog.py` — Task appendix
3. `pha_numerics_manifest_selfcheck.py`
4. docs + `build_marker`
5. strict regression → plus selfcheck → combined E2E → restart 8787

---

## 12. Review sign-off

- [ ] `LANG_DISCLOSURE_MAP` structure and zh/en formats OK
- [ ] Default `t0_strict` / `T1_M4_MODE=warn` OK
- [ ] Approve landing code per §11

**Reply “confirm land” then coding.**

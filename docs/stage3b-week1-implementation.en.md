# Stage 3B · Week 1 implementation checklist (P layer · no β Worker)

> **Language / 语言**：English (this document) · [中文](stage3b-week1-implementation.md)

> **Status**: 🚧 coding (2026-05-26)  
> **Spec**: [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md) v0.1  
> **Test strategy**: **pause** Fixture / live blocking tests until the architecture is complete; after code lands, tick this checklist for regression.

---

## Week 1 goal

Converge the production path onto **P-layer G1–G6**, strip product-facing `reject_reasons`; introduce **layout-weighted merge** + `merge_trace`; move Fixture assertions into `tests/fixtures/`.

---

## Docs (done / in progress)

| Item | Status |
|------|------|
| `stage3b-beta-vision-worker-spec.md` v0.1 | ✅ |
| `tests/fixtures/supplement/README.md` | ✅ |
| RFC §4.2 sunset note → β Spec §5 | ✅ |
| `pha-architecture-evolution-v2.3.md` Fixture wording | ✅ |
| This checklist | ✅ |

---

## Code (Week 1)

| Item | Module | Status |
|------|------|------|
| G1–G6 `assess_confidence` | `label_ledger_v1.py` | ✅ |
| Remove `missing_choline_row` / `missing_inositol_row` | `label_ledger_v1.py` | ✅ |
| Weighted merge + `merge_trace` | `perception_merge.py` | ✅ |
| `layout_hints_per_image` output | `label_ledger_v1.py` | ✅ |
| Fixture golden moved out | `tests/fixtures/supplement/golden_now_ps.py` | ✅ |
| Refusal copy generalized | `attachment_asset_qa.py` | ✅ |
| Telemetry `gate_triggered` / `merge_trace` | `telemetry_attachment.py` | ✅ |

---

## Regression results (2026-05-26 · authorized)

| Item | Result |
|------|------|
| `scripts/pha_perception_golden_6800_6801.py` | ✅ OK (F-layer Fixture) |
| P-layer unit smoke (G gates · weighted merge) | ✅ |
| `scripts/pha_stage3a22_selfcheck.py` | ✅ |
| `scripts/pha_stage3a1_attachment_qa_selfcheck.py` | ✅ |
| `scripts/pha_stage3a2_selfcheck.py` | ✅ |
| `scripts/pha_restart_accept.sh` | ✅ build `week1-p-gate-merge-trace` |

**Still pending**: live IMG_6800+6801 two-image chat E2E (needs local UI).

---

## Paused

- ❌ 3B-β VLM Worker coding (Week 3)

---

## Week 2+ (not started)

- Two-image send-contract hardening (frontend + `PHA_PERCEPTION_FORCE_SERVER_PARSE`)
- 3B-β Vision Worker JSON
- Generalized Benchmark set (appendix Spec §11.3)

---

## Regression gate (open once architecture is complete)

1. `python scripts/pha_perception_golden_6800_6801.py`
2. Live IMG_6800+6801 + Harness excerpt audit
3. Telemetry: `L0_L3_Alignment_Rate`, `gate_triggered` distribution

# Stage 3B — Live desensitized-label E2E (F layer)

> **Language / 语言**：English (this document) · [中文](stage3b-e2e-real-label-fixture.md)

> **Version**: v0.1 (2026-05-26)  
> **Script**: `scripts/pha_e2e_attachment_label_real.py`  
> **Related**: [`tests/fixtures/supplement/README.md`](../tests/fixtures/supplement/README.md) · [`stage3b-beta-vision-worker-spec.md`](stage3b-beta-vision-worker-spec.md)

---

## 1. Purpose

After lifting the `len(ocr)>=25` supplement OCR-only short-circuit, verify with **real (desensitized) two-sided images**:

- Each image takes the **Vision primary path** (or explicit `ocr_only` degrade + Telemetry)
- Two-image **server merge** and `merge_trace`
- F-layer golden: `golden_now_ps.py` (**not** a production P-layer gate)

---

## 2. Desensitization and check-in rules

| Rule | Notes |
|------|------|
| Path | `tests/fixtures/supplement/now_ps_6800_6801/IMG_6800.jpg` · `IMG_6801.jpg` |
| Forbidden | Undesensitized originals; ecommerce screenshots with address / phone / order id in git |
| Allowed | Crop UI chrome, blur order areas; keep NOW + Supplement Facts readable |
| CI | No images → script **exit 2 SKIP** (not red); with images **exit 0/1** |

Environment variables:

- `PHA_E2E_LABEL_FRONT` — absolute path to the front image
- `PHA_E2E_LABEL_FACTS` — absolute path to the Facts back image

---

## 3. Wave 1 gate (blocks Active Recall AR-1)

| Level | Condition | Effect on AR |
|------|------|----------------|
| **Green** | R1 real/synthetic: `parse_confidence=high` + golden ingredients pass | Allow AR-1 coding |
| **Yellow** | `high` not reached but `reject_reasons` are explainable | AR-1 skeleton only; do not assert fabrication |
| **Red** | No images and synthetic golden also fails | Fix L0 first; do not open AR |

---

## 4. Pass line (F layer)

| Assertion | Source |
|------|------|
| `golden_match_now_ps_choline_inositol` | `tests/fixtures/supplement/golden_now_ps.py` |
| `LabelLedgerV1` parseable | Pydantic |
| Telemetry print | `perception_channel`, `reject_reasons`, `attachment_count` |
| Target telemetry (after 3B-β) | `media_route`, `document_family`, `family_confidence` (see Spec §7.8) |

**Note**: live images may get `parse_confidence=low` when the VLM is unstable; the script **WARN but exit 0** until the 3B-β adapter lands, then hard fail.

---

## 5. Run

```bash
cd agent-harness
export PHA_E2E_LABEL_FRONT=/path/to/desensitized_front.jpg
export PHA_E2E_LABEL_FACTS=/path/to/desensitized_facts.jpg
python3 scripts/pha_e2e_attachment_label_real.py --json-out /tmp/pha_e2e_label.json
```

Synthetic OCR regression (no live images):

```bash
python3 scripts/pha_perception_golden_6800_6801.py
```

---

## 6. Multi-turn acceptance (planned · Active Recall · Wave 4)

| Turn | User intent | Assertion (F layer / Harness DEBUG) |
|------|----------|------------------------------|
| R1 | Two images + what is it / help | Ledger ≥3 ingredients; `parse_confidence` |
| R2 | Body metrics / improve | `profile=attachment_episodic_bridge` |
| R3 | Drug interaction (e.g. with a fixture-med) | `RECALL_FOCUS` contains R1 asset; `l0_l3_asset_drift=false` |

See [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.en.md) §8. Script `pha_e2e_attachment_multiturn.py` **waits on AR-5**.

## 7. Relation to 3C routing

Attachment-focus multi-turn routing is in [`stage3c-episodic-evidence-bridge.md`](stage3c-episodic-evidence-bridge.en.md): `followup` is already merged into the `episodic_bridge` default lane.

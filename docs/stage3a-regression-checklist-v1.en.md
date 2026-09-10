# Stage 3A regression acceptance checklist v1

> **Language / 语言**：English (this document) · [中文](stage3a-regression-checklist-v1.md)

> **Purpose**: gold-style scan of **already coded** 3A.1–3A.2.2; **do not recode** 3A.2.1.  
> **Principle**: red items go into **3B dependencies**; do not pile regex corner cases in 3A.  
> **Related**: [`stage3b-perception-worker-rfc.md`](stage3b-perception-worker-rfc.md) · [`pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md)

---

## 0. Baseline comparison (track 0)

| Item | Doc claim | Live / notes | Status |
|------|----------|-----------|------|
| Manifest Tier production | `t0_plus_disclosure` | see `/health` + env | ⏳ Wenhui confirm |
| Build | `pha-v2.3.3-stage3a2.2.2-attachment-label-tier0` or newer | `/health` `pha_build` | ⏳ |
| 3A.2.2 coding | ✅ | multi-image API, `ATTACHMENT_LABEL` | ⏳ |
| 3B golden | blocking 6800+6801 | live still wrong brand / missing ingredients | 🔴 → 3B |
| Tesseract | PATH + pytesseract | `tesseract --version` | ⏳ |

---

## 1. Automated self-checks (scripts)

| ID | Command | Pass | Status |
|------|------|----------|------|
| 1.1 | `scripts/pha_stage3a21_harness_route_sim.py` | initial→followup→lipid_bridge | ⏳ |
| 1.2 | `scripts/pha_stage3a2_selfcheck.py` | attachment_qa routing | ⏳ |
| 1.3 | `scripts/pha_stage3a22_selfcheck.py` | merge contains Inositol 50 | ⏳ |
| 1.4 | `scripts/pha_harness_report_v11_selfcheck.py` | intent_route field present | ⏳ |
| 1.5 | `scripts/pha_perception_golden_6800_6801.py` | **after 3B sign-off** blocking | ⏳ not implemented |

---

## 2. Routing and Harness (1.1–1.3)

| ID | Item | Method | Pass | Status | Fail owner |
|------|--------|------|----------|------|----------|
| 2.1 | Attachment initial | short “what is this? how does it help me?” + attachment | `profile=attachment_asset_qa`, `qa_mode=initial` | ⏳ | 3A |
| 2.2 | Multi-turn followup | focus present + “why/help” | `qa_mode=followup`, do not ask “why upload” | ⏳ | 3A |
| 2.3 | lipid_bridge | focus + lipid sentence | LDL snapshot block present; no full multi-year dossier | ⏳ | 3A |
| 2.4 | Hard-cut boundary | initial sentence contains “multi-year lipid trend” | **must not** be attachment_qa only | ⏳ | 3A |

---

## 3. Presentation layer (1.4)

| ID | Item | Method | Pass | Status |
|------|--------|------|----------|------|
| 3.1 | Presentation Strip | output scan | no `【依据】→【推论】`, `账本`, `静态解构` | ⏳ |
| 3.2 | Status copy | attachment mode | not only “Harness pre-inject”; includes ledger/merge semantics | ⏳ | 3A+3B |

---

## 4. Tier0 and ledger inject (1.5 — critical)

| ID | Item | Method | Pass | Status | Fail owner |
|------|--------|------|----------|------|----------|
| 4.1 | ATTACHMENT_LABEL not a placeholder | Harness tier0 dump / DEBUG | contains real “ingredient ledger” rows; **not** “Tier0 min placeholder” | ⏳ | 3A.2.2 fixed / retest |
| 4.2 | Two-image merge Telemetry | log `[Chat Attach] paths=2` | `ingredient_row_count>=3` | ⏳ | **3B** |
| 4.3 | Brand/ingredients correct | 6800+6801 live | NOW; PS/Choline/Inositol 50mg | 🔴 | **3B** |
| 4.4 | Forbid invented doses | blurry image / low confidence | do not write mg numbers absent from the ledger | ⏳ | **3B** TASK |

---

## 5. User structure (1.6)

| ID | Item | Method | Pass | Status |
|------|--------|------|----------|------|
| 5.1 | Dual question must both be answered | “what is this? how does it help me?” | independent sections ①② | ⏳ |
| 5.2 | Do not collapse to lecithin | multi-ingredient ledger | list each row, not a single “lecithin” | ⏳ | 3B ledger |

---

## 6. Ingest UX (1.7)

| ID | Item | Method | Pass | Status |
|------|--------|------|----------|------|
| 6.1 | Supplement label | upload supplement image | no forced “Save to health record” | ⏳ |
| 6.2 | Lab manual | auto fail | ingest button only when `manual_required` | ⏳ |

---

## 7. Known-failure archive (2026-05 live)

| Model | Issue summary | Owner |
|------|----------|------|
| DeepSeek-R1 | ZENESSE; missed back; generic lipids | 3B ledger + 3A structure |
| Qwen2.5 7B | first turn front only; follow-up then mentions image 1/2 | 3B merge + 3A structure |

See `tests/fixtures/e2e-failures-2026-05/README.md` (redacted summaries).

---

## 8. Stage 3C-δ clarify chips (multi-year labs)

| ID | Item | Method | Pass | Status |
|------|--------|------|----------|------|
| 8.1 | Ambiguity short-circuit | DB has ≥2 years of lipids + “how are my lipids” | SSE `event=clarify`, **no** `delta`; `harness profile=clarify` | ⏳ |
| 8.2 | chips render | PHA Console live | assistant bubble + year chips; click resends `clarify_choice_id` | ⏳ |
| 8.3 | Explicit continue | pick a year chip | R2 `turnScope.yearSource=explicit`; no more clarify | ⏳ |
| 8.4 | episodic not consumed | after clarify turn, inspect harness | `record_health_turn_focus` did not write focus / TTL did not decrement | ⏳ |

Scripts: `scripts/pha_e2e_clarify_multiturn_report.py` (API) · live browser (Console).

---

## 9. Sign-off

| Role | Conclusion | Date |
|------|------|------|
| Cursor | v1 checklist created; most items wait Week 0 scan | 2026-05-26 |
| Wenhui | ⏳ | |

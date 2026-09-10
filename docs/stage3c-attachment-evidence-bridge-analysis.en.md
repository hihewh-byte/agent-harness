# PHA attachment Q&A × full-ledger evidence — architecture analysis and action plan

> **Language / 语言**：English (this document) · [中文](stage3c-attachment-evidence-bridge-analysis.md)

> **Version**: v0.1 (2026-05-26)  
> **Trigger**: live two-image dialog + turn 2 “body metrics” + product-experience feedback  
> **Constraint**: analysis and plan only; **this file does not promise architecture-level issues will be “patched closed”**  
> **Based on**: `/tmp/pha-8787.log` Harness excerpt, `harness_plan.py`, `attachment_asset_qa.py`, `stage3b-beta-vision-worker-spec.md`

---

## 0. Executive summary

| Symptom | Root-cause layer | Nature |
|------|----------|------|
| Brand Cognitive Health®, missing Choline/Inositol | **L0 perception (OCR)** + back face not in `ingredient_rows` | Architecture: 3B-β Vision not shipped |
| “only relate to supplements”, cites a whole supplement plan | **L0 lane design** `attachment_asset_qa` explicitly **forbids** labs/wearable | Architecture: evidence isolation too strong |
| Turn 2 “lacks baseline”, three-step consult | **L0 routing drop** `lifestyle` + **Patient State not injected / empty** | Architecture: missing session bridge |
| User must wait “attachment ready” | **product contract** frontend blocks send | Experience architecture: should be async orchestration |
| Synthetic golden green, live still red | **CI vs live disconnect** | Engineering: missing live Fixture E2E |

**Conclusion**: current issues are **not** curable by more TASK edits or longer `SUPPLEMENT_BG`. Need three parallel architecture lines: **async attachment orchestrator (UX)**, **3B-β perception**, **attachment session → full-evidence bridge Profile (3C)**.

---

## 1. Your four points —对照 table

### 1.1 “Need not wait for attachment ready; can type the question first”

**Current**: frontend disables send while `attachParseInFlight`; copy requires “send after attachment is ready”.

**Should-be (product architecture)**:

```text
user picks images + types question (any order)
        ↓
message queued (pending_turn)
        ↓
background: upload → parse → merge → LabelLedgerV1
        ↓
when ready: one Harness pass with “user question + ledger” (or refuse)
```

**Principle**: the user always clicks Send once; waiting happens inside the system; status bar shows “parsing, will answer automatically”.

**Owner**: **Stage 3C-UX · Async Attachment Orchestrator** (parallel with 3B-β; does not depend on Vision finishing).

---

### 1.2 Automated live verification

**Current**:

- ✅ `scripts/pha_perception_golden_6800_6801.py` — **synthetic OCR**, not pixels
- ✅ `scripts/pha_stage3a*_selfcheck.py` — routing/slot dry-run
- ❌ **no** “upload real 6800/6801 → parse → chat → assert Harness” pipeline

**Should-be**:

| Layer | Name | Input | Assert |
|------|------|------|------|
| F0 | synthetic OCR | text fixture | P-layer merge, G gates |
| F1 | desensitized live images | `tests/fixtures/supplement/now_ps_6800_6801/*.png` | `ingredient_rows`, brand, confidence |
| F2 | HTTP E2E | local `8787` + SSE | `harness.plan.profile`, Tier0 contains/omits blocks, forbid invention |

**Note**: before F1/F2 are **blocking**, images must be desensitized into the repo or CI secret mount; otherwise nightly local only.

**Owner**: **Stage 3C-QA · `scripts/pha_e2e_attachment_label_real.py`** (action plan §4.2).

---

### 1.3 Wrong brand, empty back, no wearable/lab association

#### Live turn 1 — log reconstruction (`pha-8787.log` · week1 build)

Harness **ATTACHMENT_LABEL** actually contained:

**Image 1 (6800)**

- OCR excerpt contains `Cognitive Health®`, `Phosphatidy!` / `Serine` split lines, **NOW not seen**
- **Ingredient ledger only 1 row**: `Phosphatidyl Serine: 100 mg`
- Layout: `supplement_front`

**Image 2 (6801)**

- Excerpt contains `Supplement Facts`, `19 Capsule` (OCR broken)
- **No “ingredient ledger” block** (0 rows)
- Layout: `supplement_facts_panel` (layout recognized; row extract failed)

**Merge result**: what the LLM saw as the global ledger was essentially **1 ingredient**; brand came from marketing line **Cognitive Health®**, not NOW.

**Data chain (turn 1)**:

```text
2 JPEGs
  → OCR (Tesseract) + regex row extract     ← bottleneck
  → merge (layout weights)                  ← image 2 had no rows to merge
  → ATTACHMENT_LABEL (per-image markdown)
  → attachment_asset_qa Profile
       slots: ATTACHMENT_LABEL, TASK, SUPPLEMENT_BG
       forbidden: PATIENT_STATE_*, WEARABLE_*, CATALOG, DOSSIER  ← intentional isolation
  → SUPPLEMENT_BG = 3 “citable grounds” historical supplement dialogs (not labs/wearable)
  → L3 copies ledger + marketing copy + associates archive supplement plan
```

**Therefore**:

- **Not** “forgot to associate wearable/labs” — **turn-1 lane forbids inject** (3A design: `attachment_asset_qa` prevents lipids/HRV from polluting the focus asset).
- **Is** perception not producing the back three ingredients + brand OCR fail → L3 can only be wrong.

#### Gap vs Gemini

| Capability | Gemini/Grok | PHA live |
|------|-------------|----------|
| Read image | native Vision | OCR 175–300 char fragments |
| Image-2 Facts | row-by-row audit | layout hint present, **0 rows** |
| Archive | optional retrieve | turn 1 **forbids** Patient State |

---

### 1.4 Turn 2 “which body metrics can it help me raise?”

#### Log reconstruction

- `POST /api/chat`, **no new attachment**
- Harness: `system_chars=4909`, **full Medical SOUL + three-step consult**
- `metrics=0 narratives=0 wearable_windows=0`
- Task: `【本轮任务】基于用户问题与 Patient State 作答` → typical **`lifestyle` default profile**
- Visible: long `SUPPLEMENT_BG` supplement archive; **no Patient State / wearable summary block** (excerpt has no tabular ledger)

#### Routing chain

```text
“which body metrics can it help me raise?”
  → resolve_attachment_qa_mode → none
       (no new attachment; does not match initial/followup regex)
  → build_turn_evidence_plan → lifestyle (not combined_review / wearable_only)
  → tier0: MASTER_ANCHOR + TASK
  → tier1: SUPPLEMENT_BG + PATIENT_STATE_LAB (if assembly succeeds)
  → no WEARABLE_90D_SUMMARY (lifestyle default does not carry it)
  → Patient State empty table if DB has no lab rows
  → L3 executes Soul rule 3: “lacks historical baseline” + three-step titles
```

**Therefore**: the user feels “didn’t look up wearable data and all the numbers” — **structurally turn 2 neither took attachment follow-up nor combined/wearable lanes, and Patient State may be empty or not in Tier0**.

This is not LLM “laziness”. It is a **session state-machine + Profile-matrix gap**.

---

## 2. Architecture issue list (do not replace with corner cases)

### P0 · Perception (continues 3B-β Spec)

| ID | Issue | Notes |
|------|------|------|
| P0-1 | OCR-only cannot support ecommerce two-image golden | logs prove image 2 0 rows; weighted merge cannot invent |
| P0-2 | High-confidence gate inconsistent with live | two images with only 1 row should `merge_incomplete` → refuse; if still L3, audit Telemetry `gate_triggered` |
| P0-3 | Per-image markdown present, merged ledger weak | LLM treats marketing line as brand; need **merged block pinned “ingredient ledger (merged)”** or low-confidence refuse |

### P0 · Evidence and session (new · Stage 3C)

| ID | Issue | Notes |
|------|------|------|
| P0-4 | **Hard isolation of Attachment QA from full-ledger evidence** | `forbidden` includes PATIENT_STATE, WEARABLE, CATALOG; reasonable user expect “combine with my data” cannot be met |
| P0-5 | **No cross-turn Episodic Bridge Profile** | after attachment-focus session ends, metric questions fall to `lifestyle` + empty Patient State |
| P0-6 | **No “data availability disclosure”** | LLM should see in System: `labs: yes/no`, `wearable: yes/no`, `this-turn allowed cite scope`, not blindly say lacks baseline |

### P1 · Experience and QA

| ID | Issue | Notes |
|------|------|------|
| P1-1 | Sync “attachment ready” blocks | should be async orchestration (§1.1) |
| P1-2 | No live E2E | human repeat waste (§1.2) |
| P1-3 | `SUPPLEMENT_BG` is only historical-dialog excerpts | not structured lab/wearable Manifest |

---

## 3. Target architecture (sketch)

### 3.1 Single turn: attachment + optional full evidence

```text
                    ┌─────────────────────┐
                    │  L0 Router          │
                    │  attachment_qa_mode │
                    │  + evidence_scope   │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   focus_only            focus_plus_lab        focus_plus_wearable
   (label only)          (label+lipid snapshot) (label+HRV/activity)
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  3B Perception      │
                    │  LabelLedgerV1      │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Evidence Assembler │
                    │  · ATTACHMENT_LABEL │
                    │  · DATA_AVAILABILITY│
                    │  · optional slices  │
                    └──────────┬──────────┘
                               ▼
                         L3 narrative
```

**Key new**: `DATA_AVAILABILITY` block (2–4 lines):
`labs: N rows latest LDL/HDL …; wearable: last-90d HRV mean xx; if not injected this turn, forbid claiming “no data”.`

### 3.2 Cross-turn: focus asset → metric follow-up

Suggested new Profile name: **`attachment_episodic_bridge`**

| Turn | Profile | Tier0 points |
|------|---------|------------|
| R1 dual-Q | `attachment_asset_qa` | ledger + narrow archive |
| R2 metrics/trend | `attachment_episodic_bridge` | session-focus ledger + **Numerics Manifest summary** + **Patient State slice** + WEARABLE summary (by question) |

**Forbidden**: R2 falling to `lifestyle` + full three-step Soul.

### 3.3 Async send (UX)

```text
POST /api/chat  { message, attachment_paths?, wait_for_parse: true }
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
  parse not done                parse done
  SSE: status=pending_attach    normal Harness
  queue holds user_message
```

---

## 4. Action plan (phased · no corner-case patches)

### Phase A — docs and contract lock (1 week)

| # | Delivery | Notes |
|---|------|------|
| A1 | **`stage3c-async-attachment-orchestrator.md`** | ✅ v0.1 written |
| A2 | **`stage3c-episodic-evidence-bridge.md`** | ✅ v0.1 written |
| A2b | **`stage3c-vision-capability-matrix.md`** | ✅ v0.1 written |
| A3 | Update `stage3a-regression-checklist-v1.md` | add R1/R2 two-turn cases |
| A4 | Telemetry contract | every turn must emit: `profile`, `data_availability`, `gate_triggered`, `merge_row_count` |

### Phase B — perception (3B-β, 2–3 weeks)

| # | Delivery | Notes |
|---|------|------|
| B1 | Vision Worker JSON (Spec §7) | T2 pilot |
| B2 | F1 desensitized live Fixture + `pha_e2e_attachment_label_real.py` | **replace human two-image** |
| B3 | Merged-block UX | Tier0 top “ingredient ledger (merged)” and readable `merge_trace` |

### Phase C — evidence bridge (3C, 2 weeks)

| # | Delivery | Notes |
|---|------|------|
| C1 | `DATA_AVAILABILITY` slot | C-layer assembly, 0ms |
| C2 | `attachment_episodic_bridge` Profile | R2 metric questions take this profile |
| C3 | optional `evidence_scope=focus_plus_lipid` | when user asks lipids, explicitly open LDL/HRV (still forbid whole-plan recitation) |
| C4 | Tighten `lifestyle` drop | when `session_focus_active`, forbid three-step Soul |

### Phase E — Active Recall (3C · per Wave gate)

| # | Delivery | Wave | Notes |
|---|------|------|------|
| E1 | Spec v0.2 + Gemini three locks | Wave 0 | ✅ [`stage3c-active-recall-bridge.md`](stage3c-active-recall-bridge.en.md) |
| E2 | P0 live-image ledger E2E | Wave 1 | **before** E3/E4; blocks high-quality `anchored_asset` |
| E3 | `RECALL_FOCUS` + Ledger upsert | Wave 2 | pending Wenhui start-work code |
| E4 | multi-turn E2E R1–R3 | Wave 4 | `l0_l3_asset_drift` KGI |
| E5 | K lookup + 1.5B Shadow | Wave 3–4 | AR-3 Spec-only may go first; **forbid** drug-name trigger tables |

### Phase D — experience (parallel with A)

| # | Delivery | Notes |
|---|------|------|
| D1 | Frontend: type first then send; auto-answer after background parse | drop “can only send when ready” |
| D2 | Status: `received question · parsing 2/2` | observable |

---

## 5. Automated live verification — recommended scheme (Phase B2 detail)

```text
pha_e2e_attachment_label_real.py
  1. GET /health → build version
  2. POST /api/chat/attachments × N
  3. POST /api/chat/attachments/parse × N  (or wait_for_parse merged)
  4. POST /api/chat SSE
       message: “what is this? how does it help me?”
       attachment_paths: [...]
  5. From done.harness / log_harness excerpt assert:
       - merge_count == 2
       - ingredient_row_count >= 3  (Fixture product-facing, F layer only)
       - or parse_confidence == low + deterministic_reply (legal when OCR fails)
  6. Turn 2 POST chat (no attachment)
       message: “which body metrics can it help me raise?”
       assert profile == attachment_episodic_bridge (after impl)
       assert system contains Patient State or DATA_AVAILABILITY non-empty
```

**CI strategy**: PR runs F0; nightly runs F1 (local secret path); do not block merge until F1 is stable.

---

## 6. This live dialog — per-item attribution (for you to对照)

| User saw | Root cause |
|----------|------|
| Brand Cognitive Health® | OCR excerpt contains marketing mark; **no NOW row**; L3 was not told “if ledger has no brand, do not write one” |
| Only PS 100mg | image 2 extracted no ingredient rows; merged global 1 row |
| “combine with supplement plan” three points | `SUPPLEMENT_BG` only injected historical supplement dialogs; TASK requires “in your situation” |
| Did not mention HRV/LDL numbers | **attachment_asset_qa forbidden** wearable/labs |
| Turn 2 lacks baseline | **lifestyle** profile + Patient State not presented + Soul rule 3 templated |

---

## 7. Explicit “do not” (avoid the patch trap again)

- ❌ Add back `missing_choline_row` and other product-facing reasons in `assess_confidence`
- ❌ Use a longer TASK to make L3 “guess NOW”
- ❌ Only frontend-prompt “please wait until ready” without async orchestration
- ❌ Secretly stuff full Patient State into `attachment_asset_qa` (breaks 3A focus; needs a new Profile)
- ❌ Use a corner-case if on the “body metrics” string to hijack routing (should be **session_focus + intent enum**)

---

## 8. Suggested decision points (please lock)

1. **Does R1 attachment Q&A allow “light evidence”?**
   - Option A: keep pure focus, label only (current)
   - Option B: `focus_plus_availability` — do not open the full board, but allow 2 HRV/LDL lines **if in ledger** (recommended)

2. **R2 default Profile?**
   - Recommend: `attachment_episodic_bridge` (focus ledger + Manifest summary + question-related Patient State)

3. **Live images into repo?**
   - After desensitization, into `tests/fixtures/supplement/now_ps_6800_6801/` to enable F1 automation

4. **3B-β schedule**
   - Can run parallel with 3C bridge; before Vision, F1 may stay `low` refuse long-term — **acceptable** (better than inventing)

---

## 9. Revision log

| Date | Version | Notes |
|------|------|------|
| 2026-05-26 | v0.1 | Live logs + user four-point feedback; action plan A–D |

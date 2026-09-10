# Stage 3A.2.1 — Response-layer UX purge + topic lock + temporal causal anchor (RFC)

> **Language / 语言**：English (this document) · [中文](stage3a2.1-response-ux-and-causal-anchor.md)

> **Baseline**: `pha-v2.3.3-stage3a2-episodic-focus-grounded` (3A.2 already coded)  
> **Target build**: `pha-v2.3.3-stage3a2.1-response-ux-causal-anchor`  
> **Status**: ✅ coded  
> **Depends on**: [3A.1](stage3a1-attachment-qa-governance.en.md) · [3A.2](stage3a2-episodic-focus-and-grounded-rationale.en.md)

---

## 0.1 Chief-designer final review (three locks · frozen)

| # | Issue | Ruling | Cursor addendum (impl constraint) |
|---|------|------|-------------------------|
| **1** | `lipid_bridge` boundary | **Adopt Grok dual insurance**: `session_turn_focus` implicit lock **OR** user sentence hits `focus_tokens` (from OCR/summary, **no product-name hardcode table**) → force `lipid_bridge` / `followup` | Keyword anchor = intersection of `focus_tokens_json` + this-turn summary tokens, not a “quercetin” literal table |
| **2** | Lipid hard switch | **Adopt Gemini as too strict**: `lipid_bridge` is **latest-period only** LDL/HDL snapshot (≤2 report days, ≤400 chars); **forbid** DOSSIER / multi-year trend / full Manifest | Only explicit hard-switch words (`对比历年|历年趋势|所有报告|整体趋势` etc.) → `lab_cross_year` |
| **3** | Ingest button | **Adopt Grok compromise**: supplement / no metrics → no button + focus booked; lab metrics → **still parse in background by default**, UI **requires user confirm** before writing trend ground truth (`manual_required`) | OCR wrong-number risk > fluency; decouple from `auto_ingest` as “preview ingest / signed ingest” |

**Coding order unchanged**: UX → RT → PR (§9).

---

## 0. Live evidence (2026-05 three-turn dialog)

| Turn | User sentence | Expect | Live |
|------|--------|------|------|
| 1 | attachment + “what is this? how does it help me?” | label ledger + ≤3 individual cross-points | ✅ mostly met; but internal format `【依据】→【推论】` leaked |
| 2 | “any other benefits?” | stay on the same label; deepen mechanism/scene | ❌ dropped `attachment_asset_qa`; Soul “ledger lacks baseline…”; asked user “why supplement quercetin” |
| 3 | “…lipids… does quercetin and bromelain help much?” | discuss lipid-lowering evidence strength under the focus asset | ❌ `血脂` triggered topic hard-cut → lab/combined; read LDL/HDL but **attributed historical lipid improvement to the new supplement** |

**Conclusion (chief-designer ruling)**:

1. **Turn-3 data path is connected** (Patient State / LDL numbers injected correctly).
2. **Intent and temporal semantics broke on turns 2–3** (followup lexicon too narrow; lipids = forced exit from focus).
3. **Display layer = none**: Harness TASK / global Soul original text entered the user bubble.
4. **Frontend copy and auto-ingest out of sync**: “pending send”, per-turn “one-click ingest” coexisted with `auto_ingest`.

This RFC **does not replace** 3A.2; it adds **response-layer constitution + UX state machine** on top; orthogonal to Stage 2D MC/Shadow.

---

## 1. Goals and non-goals

### 1.1 Goals

| # | Goal |
|---|------|
| G1 | Inside an attachment short session **3-turn TTL**, lock the topic on “current focus asset”; vague continuation questions do not drop profile |
| G2 | When “lipids/LDL” appear inside a focus session, **soft-bridge** (limited lab numbers + temporal causality); forbid a full three-step consult |
| G3 | User bubble **zero internal jargon** (ledger / static deconstruct / 【依据】→【推论】 / three-step titles) |
| G4 | Attachment UI **three states** (parsing / ready / sent); drop “pending send/pending upload” |
| G5 | Supplement **no button**; labs write trend ground truth **after user confirm** (parse may preview; no default overwrite of ground truth) |
| G6 | Harness observable: `attachment_qa_mode`, `focus_ttl`, `ingest_auto_status`, `regimen_dump_detected` |

### 1.2 Non-goals (not this stage)

- ❌ Site-wide “every 4 turns summarize into background” (easy to pollute regimen logs again → **3A.3 / P2**)
- ❌ Vector RAG long memory
- ❌ LLM fully chooses Profile
- ❌ Changing lab SQLite ground truth or Manifest algorithm

---

## 2. Memory-assembly priority (revises 3A.2 §1.2)

When `session_turn_focus.active` and `attachment_qa_mode ∈ {initial, followup, lipid_bridge}`:

| Priority | Source | This-turn behavior |
|--------|------|----------|
| P0 | This-turn user explicit sentence | Answer follows; may capture |
| P0.5 | **Core Subject Anchor** (`focus_summary` + label parse) | **Forbid** asking “what did you upload” |
| P1 | Temporal causal review block (§5) | Historical LDL improvement **must not** be attributed to this-turn new label |
| P2 | ≤3 “citable grounds” (background preselect) | User-visible layer becomes natural sentences (§6) |
| P3 | Focused background slice | Not full SUPPLEMENT_BG |
| P4 | Chat history (same session, ≤N turns) | Keep anaphora; **still close cross-session RECALL** |
| P5 | Full Patient State / three-step Soul | **Forbidden by default**; `lipid_bridge` injects **LDL/HDL summary ≤2 time points** only |

**Explicit topic switch** (clear focus, ordinary pricing):

- User sentence matches: `换个话题|另一张|新图|只看 HRV|历年所有指标|对比所有报告` etc. (maintain a lexicon, **no drug names**).
- User sentence matches **hard switch**: only when there is **no** valid `session_turn_focus`, `血脂|化验|趋势` go `lab_cross_year` / `combined_review`.

---

## 3. Phase UX — attachment and ingest state machine

### 3.1 Chat attachment label (`#chat-attach-label`)

| State | Trigger | User-visible copy (example) | Forbidden |
|------|------|----------------------|------|
| `idle` | no file | (empty) | pending upload, pending send |
| `parsing` | after pick | only **global** `showChatStatus`: “parsing attachment…” | “pending…” beside the input |
| `ready` | parse OK | “ready: {filename}” | pending send |
| `failed` | parse fail | “parse failed: {filename}” | |
| `sent` | `sendAsk` success | clear the label | “saved to disk” (easy to misread as more action needed) |

**Principle**: picking a file already upload+parse (current prod); the label only means **whether it can ride the next message**, not “whether it already uploaded to the server”.

### 3.2 Ingest UI

| Condition | UI |
|------|-----|
| `document_type` ≈ supplement label / no metrics | **do not show** ingest button; optional toast “noted in session focus” |
| Lab metrics ≥1 | **always show** “Save to health record” pending confirm (final review: sign-off right); parse may write preview; **trend ground truth** waits for click |
| `auto_ingest` fail or `stored < parsed` | same, plus toast that confirm is needed |
| User already ingested manually | button → “✓ saved”, disabled |

**SSE `done` event extension (design)**:

```json
{
  "ingest_payload": { ... },
  "ingest_status": "auto_ok | auto_partial | auto_skipped | manual_required",
  "ingest_metrics_stored": 0
}
```

Frontend `attachIngestButton` mounts **only when** `ingest_status === "manual_required"` (or partial).

**Vs Discover→Promote**: chat-attachment ingest writes `health_metrics` / `health_narratives`; Discover writes MC asset tables — **two pipelines**. Docs must distinguish them so Gemini-style “backend already auto-did everything” is not mixed.

---

## 4. Phase 3A.2.1 — intent-routing hardening

### 4.1 `attachment_qa_mode` enum (extends 3A.2)

| Mode | Condition | Profile | TASK |
|------|------|---------|------|
| `initial` | parsed attachment + short Q (3A.1) | `attachment_asset_qa` | `ATTACHMENT_ASSET_QA_TASK` |
| `followup` | focus active + **continuation Q** (§4.2) and not hard-switch | same | `ATTACHMENT_ASSET_QA_FOLLOWUP_TASK` |
| `lipid_bridge` | focus active + lipids/LDL/cholesterol + **still mentions focus token/semantics** | `attachment_asset_qa_lipid_bridge` (new) or same profile + dedicated TASK | `ATTACHMENT_LIPID_BRIDGE_TASK` |
| `none` | other | SchemaIntentRouter ordinary pricing | — |

**Key changes**:

1. **`血脂` is no longer unconditional `topic_switch → none`**. If (`session_turn_focus.active` **or** user sentence hits `focus_tokens`) and not hard-switch, take **`lipid_bridge`**.
2. Lipids enter `lab_cross_year` / `combined_review` **only** when “no focus and no token anchor” or **hard-switch lexicon** (`对比历年|历年趋势|所有报告|整体趋势`).
3. **`lipid_bridge` must not** pull full historical trends “to be more complete” (Gemini 7B VRAM/attention defense).

### 4.2 Continuation (followup) lexicon — structural rules, no product names

Add on existing `_FOLLOWUP_QA_RE` (example class; implement with regex/tokenize):

- `还有|其他|更多|继续|然后呢|还有没有|除此之外|还能|进一步`
- `.*帮助` (e.g. “any other benefits?”)
- `怎么吃|怎么服用|剂量|副作用|冲突`

**Still exclude** (hard switch): `对比历年|所有报告|穿戴趋势|另一张图|换个话题`.

**Length cap**: suggest `≤200` chars (original 180 may loosen).

### 4.3 `lipid_bridge` Profile slots

| Slot | Behavior |
|------|------|
| Tier0 | `MASTER_ANCHOR` (lite), `TASK`, `SUPPLEMENT_BG` (focus + grounds) |
| Tier0 optional | `LDL_AUTHORITY` **or** compressed “LDL/HDL at most 2 report days” block, ≤400 chars |
| Forbidden | `DOSSIER_*`, `WEARABLE_*`, `EVIDENCE_CATALOG`, full `NUMERICS_MANIFEST`, `RECALL` |
| Tier1 Soul | **only** `ATTACHMENT_QA_SOUL_ADDENDUM` + temporal causal block; **do not inject** full `PHA_MEDICAL_SOUL` |

### 4.4 TASK hard constraints (followup + lipid_bridge share)

- **Forbid asking back** information already given in the previous attachment or `session focus asset` (“why do you supplement…” class).
- **Forbid** “whole supplement-plan review” structure.
- **Forbid** outputting Soul stock sentences: “current ledger lacks historical baseline for this item… static deconstruct”. When no lab need, write: “You don’t yet have continuous labs directly related to this ingredient; I’ll start from the label and current medication background…”

---

## 5. Temporal causal anchor — Gemini B′ engineered

Inject at: `lipid_bridge` and (optional) followup that mentions lipids, as Tier0 `TASK` or independent slot `CAUSAL_ANCHOR` (impl choice; must enter Harness report).

**Constitution body (draft)**:

```text
【时空因果审查 · 必读】
1. 历史化验改善（如 LDL 已降至 2.45）若发生在用户开始讨论【当轮焦点资产】之前，
   其主因应归因为档案中已存在的干预（如药物项A、运动、饮食），不得归功于当轮新拍照的补充剂。
2. 当轮焦点资产视为「拟引入 / 尚未证明疗效」变量；不得声称「您的 LDL 下降证明该补剂有效」。
3. 若用户问「对降血脂有没有帮助」：须区分
   (a) 临床证据：该成分对 LDL 的直接证据强度；
   (b) 用户个体：历史 LDL 已控时，新补剂边际收益；
   (c) 与现有药物项A等方案是否重复或干扰。
4. 输出须给出明确立场（有帮助 / 帮助有限 / 不建议为降脂而服用），禁止含糊把历史数字与新品捆绑。
```

**Accept sentence (turn-3 golden)**: the answer **must** include wording like “historical LDL improvement relates to fixture-med / existing management”, **must not** write “metric change is not enough to prove quercetin efficacy” without naming the fixture-med.

---

## 6. Phase 3A.2.2 — Presentation Layer

### 6.1 Three-layer model

```text
L0 audit track (Harness / internal TASK) — may keep structured fields for selfcheck and telemetry
L1 Profile Soul trim — attachment_* turns do not inject full PHA_MEDICAL_SOUL
L2 user track — model is required to emit L2 only; SSE exit may apply a light filter
```

### 6.2 User-track TASK addendum (parallel with L0)

- Allowed section titles: **“what this supplement is” “in your situation” “what to watch”**
- Must not appear in user-visible body: `【依据】`, `→【推论】`, `Patient State`, `Manifest`, `纵向趋势对账`, `多指标横向联动`, `静态解构`, `账本缺乏`
- “In your situation”: **at least 1 item** must cite a Context “citable grounds” row; not all 3 may be “label says”

### 6.3 Natural-language examples (quercetin scene)

| Audit track (forbid emitting raw) | User track (expect) |
|-------------------|----------------|
| 【依据】标签说明 →【推论】槲皮素抗氧化… | From the label, each capsule has 500mg quercetin… |
| 【依据】[用药] 药物项A →【推论】… | Your record has been on a fixture-med, and LDL is already 2.45, so lipid management itself is working… |
| 当前账本缺乏该项历史基线… | There is no long-term lab compare for this ingredient yet; I’ll start from mechanism and your current plan… |

### 6.4 Optional post-process (L2 filter)

| Mode | Rule |
|------|------|
| `off` | Prompt only |
| `warn` | record telemetry, do not rewrite |
| `strip` (recommended default) | replace forbidden-phrase table; fold `【依据】…→【推论】` into bullets |

**Forbidden-phrase table** lives in `docs/` or a config JSON; grow it at Review.

---

## 7. Harness telemetry (new 3A.2.1 fields)

Write into `HarnessBuildReport.intent_route` or extension fields:

| Field | Notes |
|------|------|
| `attachment_qa_mode` | initial / followup / lipid_bridge / none |
| `session_focus_active` | bool |
| `session_focus_turns_remaining` | int |
| `topic_switch_reason` | null / `lab_keyword` / `hard_pivot` / `no_focus` |
| `ingest_auto_status` | §3.2 |
| `presentation_filter` | off / warn / strip |
| `regimen_dump_detected` | answer hits historical-plan log pattern (3A.3 preset) |
| `causal_violation_detected` | answer attributes historical LDL improvement to this-turn new label (rule/spot-check) |

---

## 8. Golden accept set (redacted sentences · must-run after impl)

### 8.1 Routing selfcheck (extend `pha_stage3a2_selfcheck.py`)

| id | Input | Expect mode |
|------|------|-----------|
| R1 | attachment + “how does it help me” | initial |
| R2 | no attachment, focus on + “any other benefits?” | followup |
| R3 | no attachment, focus on + “why these benefits” | followup |
| R4 | no attachment, focus on + “does it help lipids much” + summary contains Quercetin | lipid_bridge |
| R5 | no attachment, focus on + “compare multi-year lipid trends” | none → lab |
| R6 | no focus + “my LDL trend” | none → lab |

### 8.2 Live E2E (same session · quercetin label image)

| id | Step | Pass |
|------|------|----------|
| E1 | T1 attachment + short Q | no literal `【依据】→`; contains “in your situation”; Harness profile=attachment_asset_qa |
| E2 | T2 “any other benefits?” | still attachment_*; **no** Soul ledger stock; **no** three-question ask-back; still talks quercetin/bromelain |
| E3 | T3 lipids + this product | lipid_bridge or attachment_*; cites LDL **and** distinguishes fixture-med history vs new product; **no** three-step titles |
| E4 | UI | no “pending send”; T1–3 supplement scene **no** gold ingest button (if auto_ok) |

---

## 9. Implementation order (code after sign-off)

```text
UX-1   attachment-label three states + drop pending-send copy + ingest_status SSE field design
UX-2   ingest-button conditional mount + copy “Save to health record”

RT-1   expand followup lexicon + resolve_attachment_qa_mode
RT-2   lipid_bridge profile / TASK / slot trim
RT-3   temporal causal CAUSAL_ANCHOR inject
RT-4   followup/lipid TASK forbid ask-back

PR-1   user-track TASK copy (attachment_asset_qa.py)
PR-2   Tier1 forbid full Soul (chat_service already partial; must cover lipid_bridge)
PR-3   presentation strip mode + telemetry

DOC    build_marker → stage3a2.1; update architecture-evolution § coding status
QA     extend selfcheck + tick live E2E table
```

**Suggested build**: `pha-v2.3.3-stage3a2.1-response-ux-causal-anchor`

---

## 10. Mapping to Grok / Gemini suggestions

| External suggestion | How this RFC adopts it |
|----------|-----------------|
| Grok: drop pending-upload, use parsing | §3.1 three-state machine |
| Grok: ingest default auto + optional confirm | §3.2 + ingest_status |
| Grok: raise Background rank | **only** non-attachment long dialogs; attachment turns use §2 P0.5–P3 |
| Grok: every-4-turn summary | **non-goal** → 3A.3 |
| Gemini: drop ingest button | supplement default none; labs only on fail |
| Gemini: topic lock | §2 + §4.1 followup/lipid_bridge |
| Gemini: temporal causality | §5 |
| Gemini: purge shield | §6 Presentation Layer |

---

## 11. Acceptance checklist (Review ticks)

- [x] This doc §0–§10 unambiguous
- [x] `lipid_bridge` vs `lab_cross_year` boundary confirmed
- [x] Forbidden-phrase table / user-track examples accepted
- [ ] §8 E1–E4 live E2E (quercetin three turns)
- [x] Coding done + `pha_stage3a2_selfcheck.py` extension passes
- [x] `pha_restart_accept.sh` build matches

---

## 12. Follow-on (3A.3, not this RFC)

- `user_declared_change` capture (stopping a drug, etc.)
- Rule-ize `regimen_dump_detected` / `causal_violation_detected`
- Background global rank (combined-only)
- Merge Guided fetch with the focus-asset contract

---

*Drafted: Cursor · synthesized Wenhui live three turns + Grok/Gemini Review · 2026-05*

# Handoff · Outline banding + chat dossier lookup (v1.14 · encoded)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-09-outline-and-context-lookup.md)

> For the successor coding / on-device acceptance agent · drafted 2026-09-09 18:21 · **encoded 2026-09-09 18:45**  
> Maintainer agreed with the 18:07 audit: previous plan “sweep the whole card + medication words beat HRV + fetch the May regimen” is **rejected**.  
> First implementation reply must output:

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.14** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) §15 · [`pha-pm-constitution.md`](pha-pm-constitution.md)  
Predecessors: [`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md) (P9.5b no extra paragraphs for unnamed rows) · [`handoff-2026-09-09-proactive-memory-sharing.md`](handoff-2026-09-09-proactive-memory-sharing.md) (P13–P15) · [`handoff-2026-09-09-chat-fact-card-parity.md`](handoff-2026-09-09-chat-fact-card-parity.md) (FR-6.13)

**Forbidden**: change TASK/skip-LLM before PRD/RFC; Python phrase / drug-name / metric-name tables; if for one golden sentence; flip Data > Context; start P15 early; replace `/api/chat` harness with LibreChat or similar.

---

## 0. Why this ticket exists (Constitution §2)

2026-09-09 on-device (`qwen3:14b` · 8788):

| # | Observed | Not this | Architecture gap |
|---|----------|----------|------------------|
| A | iPhone “Generate interpretation”: card has active energy, body never mentions it; reads as if it is still on the phone | Card has no numbers / sync failed | FR-2.10 copy domain mixed with sync disclaimer; `accrual` ≠ missing |
| B | Same assessment prompt contains “overall” + “focus on RHR/HRV/sleep” + training advice; interpretation only talks named rows | Regression red | P9.5b made “named” exclusive; catalog has no exclusive/emphasis/cover-card |
| C | “Medication vs HRV…”, “am I taking anything”, “what supplements” answer “not in records” and pop HRV-mean / active-energy cards | Empty ledger | `user_health_background_notes` has self-report; question stolen by Data lane + skip-LLM; manifest still emits default 90d core; question captured |
| D | P14 runtime acceptance notes 0/6 | brief is bad | Latest notes are Q&A; wait for P15 CHB. This ticket **does not** prefer long notes to bypass P15 |

Full audit in conversation 2026-09-09 18:07; conclusion: **reject the original implementation; change the docs first.**

---

## 1. Frozen contract (must not be rewritten while encoding)

1. **The whole card is the evidence source; the outline is the assessment prompt.** FR-6.8 unchanged: manifest contains checked rows. Whether narration sweeps the card is decided by **outline banding**, not “valued ⇒ must be named”.
2. **P9.5b red line stays.** “Only look at” users must not get extra topical paragraphs for unnamed rows. “Overall + focus on” must not overturn this.
3. **Data > Context stays.** Wearable/lab analysis turns must not silently dump full `SUPPLEMENT_BG`. Dossier listing uses `context_lookup`, not medication words beating HRV.
4. **Background injection is brief slices only.** Interpretation / `wearable_daily_review` still have exactly one Tier1 = `USER_BACKGROUND_BRIEF` (de-numerized, quota). Chat dossier listing uses the existing context/lifestyle lane + the same dedupe quota. **Forbidden**: a second “find the May schedule” heuristic.
5. **Card emission = this turn’s `metrics_in_scope`.** Empty scope ⇒ no SSE `fact_card`. No `if supplement: don’t emit card`.
6. **Lexicons live in JSON.** Intent Catalog / `supplement_bg.schema.json` / `fact_card_copy` language tables. Python does not special-case “只看”, “有没有药”, “活动消耗”.
7. **P15 order unchanged.** This ticket does not compile CHB. Question hygiene reuses P13 hygiene; chat injection only needs to align with P14 quota/dedupe.

---

## 2. Product contract (already in PRD v1.14)

### 2.1 FR-6.8 outline banding `outline_mode`

Declared at: `rules/health_intent_catalog.json` → `assessment_outline` (new section). TASK only cites the banding enum; **does not parse metric ids** (v4 §4.3).

| `outline_mode` | catalog markers (written into JSON at encode time; table is the design draft) | Narration |
|---|---|---|
| `exclusive` | tokens: 只看、仅看、only、only look at | **Keep P9.5b**: only named rows; unnamed rows must not start a paragraph or sentence |
| `emphasis` | tokens: 重点看、侧重、尤其、especially、focus on | Named rows as the main section; other checked valued rows **may be mentioned in the same paragraph**; no extra topical sections |
| `cover-card` | no metric tokens, or pure `holistic_assessment` / `daily_readiness` without exclusive/emphasis | Cover checked-and-valued rows on the card |

Priority (catalog `priority`; Python must not invent a third order besides the declared one): **exclusive > emphasis > cover-card**.  
`daily_readiness` **must not default to exclusive**. Golden sentence “评估今天整体…重点看静息心率与HRV，睡眠…训练” → `daily_readiness` + `emphasis`.

Unnamed metrics such as active energy: copy for `temporal.kind=accrual` is owned by the FR-2.10 language table; TASK adds one English general rule: `partial_day` = in-progress cumulative, not missing; do not restate the page sync disclaimer.

### 2.2 FR-2.10 copy domains

| Domain | When it appears | Must not appear |
|---|---|---|
| `advice_partial` / `until` | The row has a value and `partial_day` | “not yet on Mac”, “still on the phone”, “Health app having data ≠ in the ledger” |
| `hk_ok` / `hk_none` / `sync_*` | **Card top** sync status, or the row is truly empty | Body/interpretation of an accrual row that already has a cumulative value |

Language tables in zh/en; selfcheck: HTML/JSON assessment sentences for valued accrual rows must not contain the `hk_ok` template.

### 2.3 FR-6.14 dossier lookup + card-emission scope

**`goal_class=context_lookup`** (3F §15): catalog `goal_markers.context_lookup` (有没有/什么药/哪些补剂/用药清单… + English equivalents). Existence probe = notes table, not wearable.

| This turn | Arbiter | Manifest / card | Background |
|---|---|---|---|
| context_lookup only | Existing `lifestyle` (or schema `context_only`); **do not** upgrade combined | Do not assemble wearable default 90d core; `metrics_in_scope=[]` → **do not** emit `fact_card` | `build_user_background_block` uses P14-style dedupe+quota; if hit, list self-reported categories (no doses); if miss, one “none” sentence. Forbidden: “you are taking” without dossier categories |
| context_lookup **and** explicit metrics (medication vs HRV) | **Do not** skip-LLM warehouse focus; profile still emits **named metric** numbers on the Data lane | Card ⊆ named `metric_keys`; missing rows fail-closed in the body saying none; **must not** pad with 90d mean/energy | brief slice (TASK rule 5); no full schedule; no prescription doses |
| Pure “last 90 days HRV trend” | Unchanged | May emit HRV card | Data > Context: do not dump `SUPPLEMENT_BG` |

**Capture** (FR-6.11 continuation): `supplement_bg.schema.json` `background_capture_keywords` add interrogative/imperative **negatives** (吗、什么、哪些、有没有、请列出…). Only declarative self-report is written. Dirty questions go `pha_memory_hygiene.py` dry-run → maintainer confirm → apply. Do not write a new delete script.

**skip-LLM**: veto for `is_warehouse_metric_focus_turn` is **goal_class** (catalog), not a medication regex.

### 2.4 Explicitly not doing

- Interpretation “always sweep every checked row”  
- Dedicated `active_energy` template  
- Python “medication+HRV → turn off skip”  
- Flip SchemaIntentRouter Data beats Context  
- A new profile that only serves those three medication questions  
- Retrieve “prefer the longer May regimen”  
- Drug-category name blacklist  
- Start P15 early / restate dose schedules  

---

## 3. Task cards (encode order)

Docs green (this handoff + PRD v1.14 + 3F §15 + two change-logs) before opening cards. Each card: independent commit, independent flag, independent selfcheck.

| ID | Content | Depends | Flag (suggested) | Status |
|---|---|---|---|---|
| **M1-P17** | catalog `assessment_outline` + TASK cites banding + FR-2.10 copy domains; `daily_readiness` not default exclusive | this document | `PHA_ASSESSMENT_OUTLINE=1` (off falls back to P9.5b named ⇒ exclusive) | **DONE** offline O1–O3; on-device interpret O2+O3 |
| **M1-P18** | `goal_class=context_lookup` + Arbiter row + skip-LLM veto by goal + `fact_card` ⊆ `metrics_in_scope` (empty ⇒ no emit) + capture negative + chat injection aligned to P14 quota/dedupe | may parallel P17; **must not** wait for P15 | `PHA_CONTEXT_LOOKUP=1`; when lookup off, card emission falls back to “emit if entries exist” | **DONE** offline C1–C4; on-device chat C1–C4 |
| **M1-P15** | CHB (existing card) | ≥1 day after P14; **this handoff does not authorize starting early** | existing | TODO |

Harness priority: P17/P18 are consensus **P1** (catalog/Arbiter/plan contract; do not change Numerics algorithm body).

---

## 4. Golden cases (no single-sentence green light)

Into selfcheck (P17 → interpret/daily_readiness; P18 → chat). Full case text lives in fixture/catalog comments; **assert on enum fields**; no Python equals on a specific Chinese prompt.

| ID | Scene | Assert |
|---|---|---|
| **O1** | Assessment exclusive “只看 RHR”; card checks 9 items including SpO2/respiratory rate | `outline_mode=exclusive`; body does not start SpO2/respiratory topical sections (P9.5b regression) |
| **O2** | “整体…重点看 HRV/睡眠…力量训练” | `goal_class=daily_readiness` and `outline_mode=emphasis`; may mention other valued rows in passing; no topical sections |
| **O3** | Valued `accrual` row | Interpretation/card assessment sentence has no “未进 Mac / 还在手机”; has in-progress cumulative semantics |
| **C1** | “我现在有服用什么药物吗？” no wearable words | `context_lookup`; no `fact_card` event; no default 90d HRV/energy |
| **C2** | “近 90 天 HRV 趋势如何？” | not context_lookup; HRV card allowed (Data lane unchanged) |
| **C3** | “药物对于 HRV 和静息心率有没有影响？” | not warehouse skip-LLM; numbers ⊆ named metrics; if dossier miss, first paragraph has none, does not invent “您正在服用”; card ⊆ named rows |
| **C4** | After sending C1 | `user_health_background_notes` row count does not +1 because of that question |

O2/C1 use maintainer’s usual sentences as **E2E human**; CI uses isomorphic short sentences + catalog tokens, so real long sentences are not welded into Python.

---

## 5. Encode landing (docs locked; change code when starting)

| Layer | File (expected) | What |
|---|---|---|
| Catalog | `rules/health_intent_catalog.json` | `assessment_outline`; `goal_markers.context_lookup` (including a `wins_over_warehouse_skip`-class declaration field; name chosen at encode time) |
| Schema | `storage/schemas/supplement_bg.schema.json` | capture negative questions/imperatives |
| Copy | `pha/fact_card_copy.py` language tables | partial vs hk/sync domains |
| Goal/Arbiter | `pha/goal_classifier.py` · `pha/harness_arbiter.py` | read catalog only; no new drug-name lexicon |
| Skip | `pha/grounded_answer_composer.py` | veto = goal_class, not phrases |
| Card emission | `build_fact_card_event` call sites | filter entries to `metrics_in_scope`; empty scope → None |
| TASK | `pha/harness_plan.py` `_FACT_CARD_INTERPRET_TASK` | one banding contract sentence; no metric names |
| Chat inject | `pha/chat_background.py` | quota/dedupe aligned to P14; no “prefer schedule by body length” |
| Registry | `pha_harness_profile_registry_generate.py --write` | if plan slots change |

---

## 6. Acceptance and rollback

- `bash scripts/run_selfchecks.sh` all green; new O1–O3 / C1–C4.  
- `generate --check` catalog/registry.  
- On-device: iPhone generate interpretation O2+O3; Mac chat C1–C4. Do not block P9.5b O1.  
- Rollback: turn off the corresponding flag; copy keys git revert.  
- Do not weaken Numerics audit; do not change startup/ingest.

---

## 7. Mac chat UX (this ticket does not change UI)

The main cause of “bad experience” is **lane / outline / card emission** (this document), not a missing ChatGPT shell. Open-source chat products **cannot** replace the PHA harness (see PRD §4.2 / §7). If a UI reskin is later scoped, register it in §11, and it must be a thin client of `/api/chat` (consume existing SSE: `delta` / `fact_card` / `follow_ups` / `numerics_audit`), with no own routing or RAG.

# Handoff · Proactive agent and PHA memory sharing: stop the leak first, then share in layers (M1-P13 / P14 / P15)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-09-proactive-memory-sharing.md)

> For the successor coding agent · drafted 2026-09-09 12:10 · based on local `data/pha_storage.db` query evidence (§1) and maintainer 12:00 lock (§2)  
> First reply must output both lines:  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) v1.12 (§1.3a second meaning / FR-6.11–6.12 / §8 P13–P15) · [`pha-pm-constitution.md`](pha-pm-constitution.md) (anti-hardcode, no patches for a specific case) · previous handoff [`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md) (§4.3 “outline lives in TASK, do not parse metric ids” still holds)  
> This document **is design only, no code**. The three task cards are **strictly P13 → P14 → P15**; each card independent commit, independent acceptance; do not open the next until the previous is green.

---

## 0. Live state and start order

**git**: `main` locally ahead of `origin/main` (includes `0ed4898`: `OLLAMA_THINK` env switch); maintainer pushes manually. Workspace should be clean; if not, ask the maintainer first.

**Runtime**: PHA `:8788` (launchd `com.personal-health-agent.pha-8788`), build `pha-v2.3.34-fact-card-task-p95b`; model already switched to **`qwen3:14b`** (`OLLAMA_MODEL` / `OLLAMA_MEDICAL_MODEL`), `OLLAMA_THINK=false`; env in `~/Library/Application Support/pha/env-8788.sh` (ingest token is also there, **must not** echo into chat or logs); restart with `bash scripts/pha_restart_accept.sh`. `OLLAMA_KEEP_ALIVE=0` untouched (each interpretation cold-loads 9.3 GB, about 70 s; whether to change to `10m` is the maintainer’s call, out of this document).

**Test baseline**: `.venv/bin/python -m pytest -q tests/` currently 61 pass + 1 **pre-existing** fail `test_selfcheck_manifest[wearable_golden_fixture]` (`hrv_rmssd_ms` golden fixture missing a comparable row; unrelated to this document; do not drive-by fix).

**User prefs**: `data/fact_card_prefs.json` zh-CN; assessment prompt original: `重点看静息心率与HRV，睡眠的各项指标，用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议，是否可以进行力量训练？`. After tests **must restore as-is**.

Start order:

1. Read §1; reproduce the numbers locally with the §1.3 SQL (counts grow with use; magnitude is enough).
2. P13 (§4): stop the leak + hygiene. Selfcheck green; cleanup dry-run confirmed by maintainer then apply.
3. P14 (§5): background brief into interpretation. Selfcheck green + §5.8 runtime acceptance 6/6.
4. P15 (§6): CHB unified supply. Open ≥1 day after P14 acceptance.

---

## 1. Problem and evidence

### 1.1 Conclusion first

PRD §1.3a “do not split” currently only lands on the **numeric ledger** (fact-card rule layer uses full SQLite history for progressive baseline). Months of chat-precipitated **non-numeric memory** (supplement/medication/lifestyle self-report, long-term portrait) is **completely invisible** to button interpretation `fact_card_interpret` — that is FR-6.8’s deliberate design (narrow evidence surface, fail-closed), not a missed wire.

The other direction **is leaking**: when the interpretation turn borrows the chat pipeline, it writes synthetic messages and interpretation body **into the user’s chat memory**. So the status is not “isolation”; it is “chat → proactive blocked, proactive → chat writes without audit”.

### 1.2 Query evidence (2026-09-09 11:57, `data/pha_storage.db`)

| Table | Total | Produced by interpretation turns | Notes |
|---|---|---|---|
| `chat_sessions` | 1152 | **56** (plus 6 empty sessions) | Each tap of “Generate interpretation” creates a session |
| `chat_messages` | 13524 | 56 user + matching assistant | user content = `Generate today's fact-card interpretation` (now) or `请根据系统提供的当日事实卡数字与基线摘要…` (old) |
| `user_health_background_notes` | 158 | **7** category=`medication` | Old Chinese synthetic prompt contained “处方/用药剂量”, captured by `should_capture_background` |
| `user_health_background_notes` | — | **17** category=`unstructured_vision` | Content is `[vision_parse_failed] Server error '500 …'`; error strings, not memory (incidental find, see §4.4) |
| `chat_session_turn_focus` | 1008 | 7 | Interpretation sessions’ turn focus |
| `chat_session_active_recall` | 807 | 0 | Unaffected |
| `chb_briefs` | **0** | — | CHB has never compiled (P15 starting point) |

Real user memory scale: `supplement` 124, `medication` 12 (including 7 polluted), `sleep_lifestyle` 4, `symptom` 0, `general` 1.

### 1.3 Reproduction SQL (read-only, not in the repo)

```sql
-- Sessions manufactured by interpretation turns
select count(distinct session_id) from chat_messages
 where role='user' and (content like 'Generate today''s fact-card interpretation%'
                     or content like '请根据系统提供的当日事实卡%');
-- Polluted background notes
select category, count(*) from user_health_background_notes
 where content like '请根据系统提供的当日事实卡%' or content like '[vision_parse_failed]%'
 group by 1;
```

### 1.4 Code root cause

- `pha/fact_card_interpret.py` `run_interpretation` calls `stream_pha_chat_events` with `session_id=None`.
- `pha/chat_turn_orchestrator.py` `orchestrate_chat_turn_events`: empty `sid` → `create_session(uid)` (about lines 213–220); then `append_message(sid,"user",…)`, `maybe_set_title_from_first_message`, `dynamic_slot_registry.on_request_start`, `maybe_capture_chat_background` (about 237–264); finish `append_message(sid,"assistant",…)` + `record_health_turn_focus` (about 924–943); mid-turn `session_turn_focus.save/consume` (about 493–564). These writes treat every profile the same; there is no concept of “does this turn belong to user chat memory”.
- Read side already isolated: `pha/chat_turn_slots.py` sets `background_block=""`, `recalled_snippets=""` for `fact_card_interpret`; `pha/harness_plan.py` `_FACT_CARD_INTERPRET_FORBIDDEN` forbids `SUPPLEMENT_BG` / `WEARABLE_90D_SUMMARY` / `PATIENT_STATE_*` / dossier / tools. `EPISODIC_BRIDGE` is assembled for non-attachment profiles when `episodic_all_profiles_enabled()` (`chat_turn_slots.py` about 391–399), but interpretation turns have no session focus so it is empty in practice — P13 must make that an explicit rule rather than “happens to be empty”.

---

## 2. Maintainer lock (2026-09-09 12:00)

> “Agree with your recommendation… the proactive agent is also part of PHA; assessment is assessment of incremental data against the user’s whole historical background.”

Layered scheme adopted (**frozen**):

| Layer | Content | For button interpretation | Direction |
|---|---|---|---|
| **A structured facts** | Numeric ledger (already shared) + supplement/medication/lifestyle **self-report** in `user_health_background_notes` | **Share**, as a **non-numeric** Tier1 brief | chat → proactive (P14); proactive output **no longer** writes chat tables (P13) |
| **B situational/session memory** | `chat_session_turn_focus`, RECALL snippets, `EPISODIC_BRIDGE`, previous-turn summary | **Do not share** (a one-shot interpretation with no chat context cannot use it; it only causes topic drift) | Keep `recalled_snippets=""`, and explicitly forbid `EPISODIC_BRIDGE` |
| **C cross-session long-term portrait** | CHB (`chb_compiler`, `USER_CONTEXT_BRIEF` slot) | **Share**, but first make CHB actually compile, and include layer A plus interpretation history as compile inputs | Two-way loop (P15) |

Unchanged red lines:

- Numerics audit policy `fact_card` **not one character changed**; numbers on the card remain the only citable values; any number in the brief is not a manifest member; model citing it is rejected (that is the behavior we want).
- `WEARABLE_90D_SUMMARY` / `PATIENT_STATE_*` / `SUPPLEMENT_BG` / dossier / tools remain forbidden for `fact_card_interpret`.
- Constitution anti-hardcode: Python has no metric names or supplement names; no patches for “a particular note”; judgment is by profile attribute, category, lexicon.

---

## 3. Overall design: one attribute, one slot, one supply

```
                  ┌──────────── chat memory (user chat exclusive) ────────────┐
 Web/Mac chat ──▶ │ chat_sessions / chat_messages / turn_focus /              │
                  │ active_recall / user_health_background_notes              │
                  └───────────────┬───────────────────────────────────────────┘
                                  │ read-only, de-numerize, length-capped (P14)
                                  ▼
                  USER_BACKGROUND_BRIEF (Tier1 · non-numeric source)
                                  │
 iPhone full card “Generate interpretation” ──▶ fact_card_interpret (Tier0 = card) ──▶ audit ──▶ data/fact_card_interpret/*.json
        ▲                         │  memory_write_policy = none (P13)                       │
        │                         ✗ write no chat tables                                     │ interpretation history (P15 input)
        │                                                                                    ▼
        └──────────────── CHB daily compile (T0 §Facts + §Background + interpretation lineage) ◀────┘ (P15)
                          USER_BACKGROUND_BRIEF supply switches from live notes to CHB projection
```

- **One attribute**: harness profile registry adds `memory_write_policy` (`chat` | `none`). `fact_card_interpret = none`. The orchestrator asks only this predicate; no scattered `if profile == ...`.
- **One slot**: new Tier1 slot `USER_BACKGROUND_BRIEF`. P14 built from live background notes; P15 built from CHB projection; slot name, contract, audit behavior unchanged.
- **One supply**: after P15, chat-side `USER_CONTEXT_BRIEF` and interpretation-side `USER_BACKGROUND_BRIEF` both come from the same CHB artifact, with different projections (chat side includes §Facts; interpretation side does not).

---

## 4. M1-P13 · Stop the leak + memory hygiene (P0 · bug)

### 4.1 Goal

Interpretation turns **write zero rows** to these five tables: `chat_sessions`, `chat_messages`, `user_health_background_notes`, `chat_session_turn_focus`, `chat_session_active_recall`; also do not trigger `dynamic_slot_registry` discover/promote, do not write `dynamic_slots.json`. Interpretation results land **only** in `data/fact_card_interpret/<key>.json` (existing cache is already the trail; P15 reads it).

### 4.2 Design

**(a) Registry attribute** (`pha/harness_profile_registry.py` `_PROFILE_CONTRACTS` + `rules/harness_profile_registry.generated.json`)

- Each profile contract adds `memory_write_policy`, values `"chat"` (default, all existing profiles) or `"none"`.
- `fact_card_interpret` → `"none"`.
- Expose a single predicate, e.g. `profile_writes_chat_memory(profile: str) -> bool`; decidable after `resolve_profile_override`, **before `create_session`**.
- `scripts/pha_harness_profile_registry_selfcheck.py --write` regenerates JSON; registry selfcheck adds: a `none` profile must also have `slots_tier1` without `RECALL`/`EPISODIC_BRIDGE` (read/write consistency).

**(b) Orchestrator “sessionless turn”** (`pha/chat_turn_orchestrator.py`)

When `memory_write_policy == none`:

- Do not `create_session`; `sid` stays `None` (or an explicit sentinel; empty string must not pose as a session id; existing `sid or ""` writes need a per-site check that they do not mis-write under `None`).
- Skip: `append_message` (user and assistant), `maybe_set_title_from_first_message`, `on_request_start` / `on_background_captured`, `maybe_capture_chat_background`, `session_turn_focus.save/consume/revive/clear`, `record_health_turn_focus`, active_recall writes.
- `_prior_user_msg`, `_existing_focus`, `_route_focus`, `session_focus_row` take empty; `EPISODIC_BRIDGE` slot explicitly emptied (no longer rely on “happens to be empty”).
- SSE event stream **unchanged** for the caller (`status` / `done` / `error` structure same; `done.answer.answer_text`, `numerics_audit`, `model` still present); `session_id` field if present is `null`.
- Suggested shape: converge “session writes” into a small `TurnMemorySink` (or equivalent no-op functions) chosen at entry by policy, avoiding a dozen `if`s. Shape not required, but **must not** write `== "fact_card_interpret"` in the orchestrator.

**(c) Background-capture defense** (`pha/chat_background.py` `maybe_capture_chat_background`)

- Independent of (b), add another: content starting with `[` and matching `[<snake_case_tag>]` (e.g. `[vision_parse_failed]`) system error strings **do not enter the DB**; return reject reason `system_tag_message`. This is a generic rule, not vision-specific.
- Do not change `should_capture_background` lexicon logic.

**(d) Memory hygiene script** (new `scripts/pha_memory_hygiene.py`, **default dry-run**)

Identify three classes (match with **parameterized** synthetic message text, take current value from `harness_plan.FACT_CARD_INTERPRET_USER_MESSAGE`; old Chinese text as constant list `LEGACY_SYNTHETIC_USER_MESSAGES` in the script, annotated with source and date):

| Class | Judge | Disposition |
|---|---|---|
| A interpretation sessions | **All** `role=user` messages in the session ∈ the synthetic-message set | Delete matching rows in `chat_messages`, `chat_session_turn_focus`, `chat_session_active_recall`, `chat_sessions` |
| B polluted notes | `user_health_background_notes.content` starts with a synthetic-message prefix, or matches `^\[[a-z_]+\]` system tag | Delete the row |
| C empty sessions | `chat_sessions` with no messages | **Default do not delete**; `--include-empty` only (may be the user just tapped “new session”) |

Requirements:

- `--dry-run` (default) prints per-class counts + first 5 samples (session id / time / first 60 characters of content); before `--apply` copy the DB to `data/backups/pha_storage.<UTC timestamp>.db`, print the backup path; delete in a transaction; run stats again at the end to confirm zero.
- Expected dry-run magnitude: A ≈ 56 sessions, B ≈ 7 + 17, C ≈ 6. Stop and ask if the deviation is large.
- **apply must wait for the maintainer to confirm in chat**; the agent must not run it on its own.

### 4.3 Selfcheck (fold into `scripts/pha_fact_card_selfcheck.py`, temp DB)

1. Temp DB preloads 1 real session + 2 notes; mock `stream_fn` runs `run_interpretation` once → five table row counts **equal table-by-table**, `dynamic_slots.json` mtime unchanged.
2. Same mock with `profile_override="lifestyle"` (control) → `chat_sessions` +1, `chat_messages` +2, proving the predicate works and the pipeline is not broken.
3. `maybe_capture_chat_background("[vision_parse_failed] Server error …")` → not stored, reject=`system_tag_message`; `"每天补镁 400mg"` → stored (lexicon logic not collateral-damaged).
4. Registry selfcheck: `fact_card_interpret.memory_write_policy == "none"`, and Tier1 has no `RECALL`/`EPISODIC_BRIDGE`.
5. Hygiene script dry-run on a temp DB: construct 2 each of A/B/C → counts correct; after `--apply` zero, and non-target sessions and notes **not one missing**.

### 4.4 Incidental finds (write PRD §11; not this card)

- `unstructured_vision` category stored vision-parse-failure error strings as background (17). P13 (c) only blocks new ones; root cause (vision fail path returning the error as content) is a separate card.
- Origin of 6 empty sessions unknown (most likely Web “new session” left unused); P13 does not conclude.

### 4.5 Acceptance and commit

- On-device/browser tap “Generate interpretation” once → Web session list **does not add** a session; `select count(*) from chat_sessions` equal before/after.
- Interpretation behavior unchanged (audit pass, cache hit `started=False`).
- Commit message prefix: `fact-card: interpret turn writes no chat memory (M1-P13)`; one change-log entry; PRD §8 P13 → DONE.

---

## 5. M1-P14 · `USER_BACKGROUND_BRIEF` into interpretation (layer A · product)

### 5.1 Goal

Supplements / medications / lifestyle / symptoms the user self-reported in chat enter `fact_card_interpret` Tier1 as a **non-numeric source**, so training advice can carry personal cautions like “you take X / you have been going to bed late”; meanwhile **introduce no citable number or date**; audit policy untouched.

### 5.2 What not to do (write into TASK and slot head)

- Do not cite any number, dose, or date in the brief; do not restate doses; do not give a dose or prescription from it (FR-6 principle).
- Do not mention background unrelated to today’s card (outline is still `USER_ASSESSMENT_PROMPT`; brief only affects wording and cautions).
- Do not use the brief as an excuse for “related markers” (v4 handoff focus-drift must not return).

### 5.3 Slot contract

| Item | Value |
|---|---|
| Slot name | `USER_BACKGROUND_BRIEF` |
| Layer | Tier1; `fact_card_interpret` `slots_tier1=["USER_BACKGROUND_BRIEF"]` (currently empty list) |
| forbidden | unchanged; `SUPPLEMENT_BG` stays forbidden (same source table, different content policy; do not reuse `SUPPLEMENT_BG`) |
| Title (`harness_tier0_assembly` title table) | zh `用户背景 · 自述 · 非数字源` / en `User background · self-reported · not a numeric source` |
| Head lead-in (first line in the block, by locale) | zh: `以下为用户在对话中自述的补剂、用药、生活习惯与症状，仅用于调整建议的措辞与注意事项。不得引用为数值，不得复述或给出剂量，与今日卡片无关则忽略。` en equivalent |
| Budget | `PHA_FACT_CARD_BG_BRIEF_MAX_CHARS`, default zh 600 / en 900; overflow truncates by **whole line**, never mid-line; head lead-in not counted |
| Switch | `PHA_FACT_CARD_BG_BRIEF`, default `1`; `0` slot absent, cache key has no brief digest |
| Degrade | When Tier0 budget is short, Tier1 degrades as a whole first (existing mechanism); current system prompt already `WARN: tier0_budget_exceeded` (sys≈6170); after brief ships must confirm the four Tier0 slots **not one character missing**; only the brief may be cut |

### 5.4 Builder (new module, suggested `pha/fact_card_background_brief.py`; do not change `chat_background.py` write logic)

Input: `list_background_notes(uid, limit=…)` (existing read; take a large enough limit, e.g. 200).

Pipeline (order fixed):

1. **Filter**: keep only category ∈ {`supplement`,`medication`,`sleep_lifestyle`,`symptom`,`general`}; exclude `unstructured_vision`; exclude content matching `^\[[a-z_]+\]` (system tags) or ∈ the synthetic-message set (should be empty after P13 cleanup; this is defense).
2. **Dedupe**: normalize by “strip whitespace, strip punctuation, lowercase”, keep newest.
3. **Quota**: keep newest N per category, default supplement 6 / medication 4 / sleep_lifestyle 3 / symptom 3 / general 2 (env-tunable, `PHA_FACT_CARD_BG_BRIEF_QUOTA` JSON).
4. **De-numerize** (core):
   - **Keep** identifiers with letters flush against digits, no whitespace (`D3`, `B12`, `Omega-3`, `CoQ10`, `SpO2`) — same criterion as FR-6.10 “digits in identifiers do not count”.
   - **Delete** all other number tokens (Arabic digits, decimals, ranges, and following units `mg|g|mcg|μg|IU|ml|粒|片|次|小时|h|点|%` etc.), replace with `〔数值略〕` / `[amount omitted]`; consecutive replacements merge into one.
   - **Delete** date and time expressions (ISO, `9月7日`, `Sep 7`, `22:30`, etc.); delete with no replacement. **Do not emit `note_date`**; time semantics only as relative words, mapped from the difference of `note_date` vs `as_of` **into a lexicon** (`近一周内`/`近一月内`/`更早`; en `within the last week`/`month`/`earlier`); lexicon in language tables; Python writes no Chinese.
   - Chinese numerals (`三粒`, `两次`) also deleted; lexicon likewise in language tables.
5. **Posterior**: feed the de-numerized brief to **the same number extractor the audit uses** (the tokenization function in `numerics_manifest` for replies; if not exposed, expose a read-only function with minimal change, do not change audit policy); assert no leftover S-level citable number tokens; if leftover, **drop the whole line** and count telemetry `bg_brief_line_dropped`. Insurance so we “do not bet on regex luck”.
6. **Render**: subsection per category, each line `- <content>（<relative time word>）`; return `(text, meta)`, `meta = {"notes_used": n, "lines_dropped": k, "digest": sha256(text)}`.

`chat_turn_slots.py`: build and put into `ctx.slot_contents` only when `"USER_BACKGROUND_BRIEF" in plan.slots_tier1 and flag`; `fact_card_interpret` branch still keeps `background_block=""`, `recalled_snippets=""`, `episodic_bridge_block=""` (P13 already explicit).

### 5.5 Minimal TASK and soul change

- `_FACT_CARD_INTERPRET_TASK` (`pha/harness_plan.py`) adds **one item** (as item 5 or appended to the end of item 2; one each zh/en template):  
  `USER_BACKGROUND_BRIEF, if present, only shapes cautions and wording of advice. Never cite it as data, never restate or infer doses, and skip it when unrelated to the rows the assessment named.`
- `PHA_FACT_CARD_SOUL_MINIMAL` **unchanged**.
- TASK change automatically invalidates old cache (key includes TASK hash); expected.

### 5.6 Cache key and response metadata

- `interpret_cache_key` adds input `bg_brief_digest` (empty string when flag off). User adds a supplement self-report in chat → digest changes → old interpretation misses. FR-6.5 key definition adds one item in sync.
- `_decorate_interpretation` / API response add `background_used: bool`, `background_notes_used: int`.
- `/proactive/fact-card/view` interpretation block adds a small line next to the model name (`fact_card_copy` language table): zh `已参考你在对话中自述的 N 条背景（不作为数值来源）` / en equivalent; `N=0` not shown.

### 5.7 Selfcheck (fold into `scripts/pha_fact_card_selfcheck.py`, temp DB + mock stream capturing the system prompt)

1. Preload notes `每晚补镁 400mg，最近两周都 1 点后睡` (supplement/sleep), `在吃维生素D3 和 Omega-3` (supplement), `2026-09-01 开始每天两次鱼油` (supplement) → brief **contains** `镁`, `维生素D3`, `Omega-3`, `鱼油`, **does not contain** `400`, `1 点`, `2026`, `两次`, any `note_date`; contains relative time words.
2. Posterior extractor returns 0 S-level tokens on the brief.
3. Captured system prompt: Tier1 shows `USER_BACKGROUND_BRIEF` title; `SUPPLEMENT_BG` / `RECALL` / `EPISODIC_BRIDGE` / `WEARABLE_90D_SUMMARY` all absent; four Tier0 slots complete.
4. Budget: stuff 40 notes → output ≤ cap, last line complete (does not end mid-sentence or on `〔`).
5. Flag `0` → slot absent, `background_used=false`, cache key **different** from flag `1`.
6. Notes change → `interpret_cache_key` changes; notes unchanged → key unchanged (idempotent).
7. **Audit not relaxed**: mock reply writes `你每晚补镁 400mg` → audit still rejects (`400` not in manifest). This prevents someone casually adding brief numbers into the manifest.
8. One `unstructured_vision` / `[vision_parse_failed]` note → not in the brief.

### 5.8 Runtime acceptance (real card, real prefs, `qwen3:14b`)

In `/tmp` in-process (see v4 handoff §1.3: call `run_interpretation` directly, no HTTP, do not touch the cache directory) 3 rounds each zh/en:

| Check | Pass line |
|---|---|
| Numerics audit | 6/6 pass |
| Brief cited as a number / a dose appears | 0/6 |
| Literal `〔数值略〕` restated by the model | 0/6 (if it appears, change lead-in wording, not the audit) |
| Training advice carries background cautions **related** to named card metrics | ≥4/6 (qualitative; record original text) |
| Extra paragraph for unnamed rows (v4 §5 contract) | ≤1/6 |
| Chinese reply has leftover English lead-in / English reply has Chinese | 0/6 |

If any item misses: look first at brief content, TASK wording, or quota; follow v4 handoff §6 “do not tune audit, do not add label filtering”. Paste the acceptance table into the change-log. After the test **restore the prefs original**.

### 5.9 Commit

`fact-card: USER_BACKGROUND_BRIEF tier1 slot for interpret (M1-P14)`; PRD FR-6.8 note + FR-6.12 → landed; §8 P14 → DONE; change-log.

---

## 6. M1-P15 · CHB unified supply (layer C · closed loop)

### 6.1 Goal

Turn “precious data from long-term use” from 13k raw messages into a **compiled, denoised, auditable** long-term portrait, and let both chat and interpretation take background from that one portrait. P14 slot name and contract unchanged; only the supply changes.

### 6.2 Today

`pha/chb_compiler.py` already has: T0 §Facts compile (lab + wearable), optional LLM `§Interpretation`, `recompile_chb_if_stale`, artifacts `reports/chb/<uid>/brief_<hash>.json`, Tier1 slot `USER_CONTEXT_BRIEF` (only `lifestyle` / `combined_review`). **But it has never been triggered** (`chb_briefs` 0 rows, artifact directory empty).

### 6.3 Design

**(a) Compile-input expansion**

- Add `§Background`: source = **the same function** as the P14 builder (de-numerize, quota, posterior), `prov_type=user_statement`; **does not enter §Facts** (`t0_gated_adopter` default veto on `user_statement` stays).
- Add `§Interpretation lineage`: read `data/fact_card_interpret/*.json` entries with `status=done`, audit passed, last 30 days; take `calendar_day` + body; after the same de-numerizer **keep only cautions/advice tendencies that recur** (implementation can be simple: sentence dedupe + keep only frequency ≥2; no LLM). This is the “proactive interpretation history → long-term portrait” loop.
- Change `ledger_hash` to a combo of `ledger_hash + background_hash + lineage_hash` (or add `input_hash`); `chb_stale_status` uses the combo to judge stale; otherwise a new self-report would not trigger recompile.

**(b) Trigger**

- Once a day: after `GET /proactive/fact-card` returns (Shortcuts hit it daily), a background thread calls `recompile_chb_if_stale(uid)`; env `PHA_CHB_AUTOCOMPILE` (default `1`); same day only once (marker file `reports/chb/<uid>/.last_compile_day`); failure only logs, **never** affects the card response.
- Do not add a cron / launchd extra process (startup-consensus scope; do not touch).

**(c) Projection**

- `build_user_context_brief_block(uid, profile=…)` projects by profile:
  - `lifestyle` / `combined_review`: existing behavior (§Facts + §Interpretation).
  - `fact_card_interpret`: **only** §Background + §Interpretation lineage, **never** §Facts (§Facts has off-card numbers; model citing them is rejected — burying a landmine).
- `USER_BACKGROUND_BRIEF` builder becomes: CHB artifact fresh (same day or `is_stale=False`) → use projection; else fall back to live notes (P14 logic). `meta.brief_source ∈ {"chb","live_notes"}` into response metadata and telemetry.
- `USER_CONTEXT_BRIEF_PROFILES` **does not** add `fact_card_interpret` — interpretation uses the `USER_BACKGROUND_BRIEF` slot; do not have both slots at once.

### 6.4 Selfcheck (extend `scripts/pha_chb_compiler_selfcheck.py` + `pha_fact_card_selfcheck.py`)

1. Temp DB + temp `reports/chb`: compiled artifact contains `§Background`, and §Background has 0 S-level tokens via the posterior extractor.
2. Add one self-report → `chb_stale_status.is_stale=True`; after recompile `False`.
3. `fact_card_interpret` projection **contains no** §Facts row; `lifestyle` projection does.
4. Artifact missing → `brief_source=live_notes`; artifact fresh → `chb`; briefs from both sources pass P14’s 7 assertions.
5. Lineage: make 3 interpretation cache jsons (2 contain the same advice sentence) → that sentence enters lineage; appearing once does not.
6. Auto-compile marker: two triggers same day compile once.

### 6.5 Acceptance and commit

- After one day of running, `reports/chb/default/` has an artifact; `GET /proactive/fact-card` P95 latency unchanged (compile in background).
- Interpretation response `brief_source=chb`; P14 §5.8 table rerun 3+3 still passes.
- Commit: `chb: background + interpret lineage; interpret brief served from CHB projection (M1-P15)`; PRD §8 P15 → DONE; change-log.

---

## 7. Explicitly not this round

- Layer B (RECALL / turn_focus / EPISODIC_BRIDGE / previous-turn summary) into interpretation: **no**, and P13 makes it an explicit ban.
- Adding brief numbers into Numerics Manifest / a new `user_statement` audit domain: **no**.
- Changing `fact_card` audit policy, FR-6.10 grading, `PHA_FACT_CARD_SOUL_MINIMAL`: **no**.
- Writing interpretation results back into a chat session “so the user sees them in chat”: **no** (P15 lineage is compiled into the portrait, not original text re-injected).
- Root cause of vision-fail strings stored, origin of 6 empty sessions, `OLLAMA_KEEP_ALIVE`: register, not this document.

---

## 8. Risks and counters

| Risk | Counter |
|---|---|
| De-numerizer leak → model cites → audit reject → user sees “not generated” | Posterior extractor drops the whole line (§5.4 step 5); not relaxing audit is the floor; rather one fewer background line |
| Model restates literal `〔数值略〕` | Lead-in already requires “do not restate”; §5.8 has a dedicated check; if miss, change lead-in wording |
| On 14b, brief worsens focus drift (discusses unnamed metrics) | TASK item 5 limits “only affects wording and cautions”; acceptance reuses v4 contract ≤1/6 |
| Tier0 budget already over (sys≈6170) + brief → Tier0 cut | Acceptance asserts four Tier0 slots not one character missing; if needed, first compact `FACT_CARD_CONTEXT` JSON `indent=2` (separate discussion, not this document) |
| Hygiene script deletes a real user session | Judge is “**all** user messages ∈ synthetic set”; class C default not deleted; backup + maintainer confirm before apply |
| CHB background compile hits SQLite write lock | Compile reads DB, writes json artifacts; marker file once per day |

---

## 9. Delivery checklist (per card)

| Card | Code landing | Doc landing |
|---|---|---|
| P13 | `harness_profile_registry.py` + `rules/*.generated.json`; `chat_turn_orchestrator.py`; `chat_background.py`; new `scripts/pha_memory_hygiene.py`; `pha_fact_card_selfcheck.py`, `pha_harness_profile_registry_selfcheck.py` | PRD §8 P13 DONE, §11 two incidental finds; `pha-ios-proactive-change-log.md`; `harness-change-log.md` (registry attribute) |
| P14 | new `pha/fact_card_background_brief.py`; `harness_plan.py` (one TASK item + Tier1); `chat_turn_slots.py`; `harness_tier0_assembly.py` (title); `fact_card_interpret.py` (cache key, meta); `fact_card_api.py` / `fact_card_copy` / view template; language tables (relative time words, unit words, lead-in) | PRD FR-6.8 note, FR-6.12 land, FR-6.5 key definition; §8 P14 DONE; two change-logs; acceptance table |
| P15 | `chb_compiler.py` (§Background / lineage / combo hash / projection); `fact_card_api.py` (background trigger); `fact_card_background_brief.py` (supply switch); two selfchecks | PRD §8 P15 DONE; change-log |

After each card’s commit `git status` clean; push is the maintainer’s (PRD §9 item 7).

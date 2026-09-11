# PHA iOS Proactive Change Log

> **Language / 语言**：English (this document) · [中文](pha-ios-proactive-change-log.md)

## 2026-09-11 (CHB lineage stub regex flags · chat HTTP 0)

- **Class**: P0 / chat SSE. Wearable+supplement turns mount `USER_CONTEXT_BRIEF` and import `chb_compiler`, which crashed.
- **Change**: `_LINEAGE_WINDOW_STUB_RE` uses compile-time `re.I`. build `pha-v2.3.47-lineage-stub-re-flags`.
- **Evidence**: venv Python 3.12 `re.error` reproduced; `pha_chb_compiler_selfcheck`.
- **Rollback**: revert to v2.3.46.

## 2026-09-11 (named-day enumerate + wearable CHB background)

- **Class**: P1 / chat evidence · FR-6.14.
- **Change**: Enumerate named point days; keep 90d summary on a true 90-day window; mount `USER_CONTEXT_BRIEF` from schema positive score (§Background only). build `pha-v2.3.46-named-days-chb-brief`.
- **Evidence**: `pha_healthkit_ingest_selfcheck`; `pha_chb_compiler_selfcheck`.
- **Rollback**: revert to v2.3.45.

## 2026-09-11 (Loop Path B: approve → local aliases)

- **Class**: P1 / Loop × product. Path B: approve applies aliases on this Mac; still no repo catalog edit.
- **Change**: `pha/loop_local_aliases.py`; `catalog_metric_aliases` merges local override; `approve_and_execute` writes `data/loop_local_aliases.json`; fact-card copy “Approve · apply on this Mac”; full-veto / Draft PR optional.
- **Evidence**: `pha_loop_weekly_selfcheck` PASS (incl. `infer_metrics_from_message`).
- **Rollback**: drop local merge + approve write.

## 2026-09-11 (active energy / steps cross-source double-count fix)

- **Class**: P1 / daily rollup. After zip import, Shortcut rewrote same-day `healthkit|` daily totals; active energy **summed** all sources → fact card ~699 vs Health ~372; steps Shortcut multi-device list was summed ≈ Watch+iPhone, then won via max.
- **Change**: `active_energy` is per-source then max (same family as steps); drop `healthkit` daily when it ≈ sum of device sources; Shortcut `_combine_step_numbers` uses max (not sum) when no covering Sum. Rebuilt `default` recent days.
- **Evidence**: `pha_wearable_daily_aggregator_selfcheck` PASS. Today card: active energy 355.6 kcal, steps 6963 (was 699.3 / 12812).
- **Rollback**: restore `active_energy_sum` and combine sum branch.


- **Class**: P1 / Loop × Fact Card. Maintainer: put notify + approve on the fact card.
- **Change**: `load_fact_card` attaches `loop_approvals`; lock-screen teaser; full-card `#loop-approvals` approve/reject (`next` back to card). Approve still = full-veto, no catalog merge.
- **Evidence**: `pha_loop_weekly_selfcheck` (fact-card segment) PASS.
- **Rollback**: drop attach + HTML block.

## 2026-09-11 (weekly Loop: harvest + multi-channel notify + human approve)

- **Class**: P1 / Loop ops. Maintainer: weekly auto harvest, multi-channel notify, approvable execute; **no catalog write**.
- **Change**: `pha/loop_weekly.py` · `pha/loop_approval_api.py` · weekly harvest/approve scripts · launchd example · SOP path W. Channels: PHA inbox / Mac / email / webhook. Approve = full-veto (+ optional Draft PR); **never** auto-edits catalog.
- **Evidence**: `pha_loop_weekly_selfcheck` PASS.
- **Rollback**: drop router mount + scripts.

## 2026-09-11 (zip sleep day key = HealthKit wake day)

- **Class**: P0 / FR-1.6 · FR-2.6. Maintainer: zip and HealthKit should match (same source).
- **Root cause**: zip keyed `wearable_sleep_segments.day` by segment **start calendar date**; pre-midnight Core/Deep landed on the prior day (~59min asleep gap vs HealthKit).
- **Change**: (1) `pha/sleep_wake_day.py` noon-window wake day; (2) importer writes wake day; (3) `rebucket_zip_sleep_segments_to_wake_days` for legacy rows; (4) zip-only daily uses T2 `healthkit_sleep_fields` (incl. Core). Live rebucket `updated=1423` / 590 nights + rebuild.
- **Acceptance**: 9/11 |zip−hk| ≤1min; 9/10 zip vs Health screenshot Δ≲5min with Core present; aggregator selfcheck PASS.
- **Rollback**: drop wake-day write + rebucket; restore zip sum deep/REM daily path.

## 2026-09-11 (sleep daily: prefer healthkit| on dual-source nights)

- **Class**: P0 / FR-1.6. Maintainer screenshot Sep 10–11: Health app deep 55m / core 5h5m / REM 1h22m / awake 1h5m; daily previously undercounted asleep ~58m, deep ~37m, Core null.
- **Root cause**: when `healthkit|` Shortcut segments and incomplete zip/`HKCategory` rows coexisted, `build_wearable_daily_summary` took the zip branch (`hk_rows and not other_rows`).
- **Change**: if any `healthkit|` rows exist, use `healthkit_sleep_fields_from_segments`; zip only when Shortcut absent. Zip path clears stale `sleep_core` / `in_bed` / `sleep_period`. Rebuilt 9/8–9/11.
- **Acceptance**: 9/11 vs Health app Δ≤1min; `pha_wearable_daily_aggregator_selfcheck` PASS (incl. `test_mixed_segments_prefer_healthkit`).
- **Rollback**: restore “hk only when no other” branch.

## 2026-09-11 (P20 iPhone same-network → DONE)

- **Category**: P1 / §8 M1-P20. Maintainer provided Safari screenshot and accepts the body.
- **Evidence**: same-LAN `*.local:8788` Private; prefs exclusive “only today’s resting HR…” → disk inject `resting_heart_rate_bpm` only (full card still multi-select); screenshot numbers ⊆ card/Manifest; brief names concrete slot items (synthetic fixture labels only). Mac also ran deep-sleep exclusive: `reports/p20_eval/runs_p20_iphone_lan_exclusive_deep.json` status=done.
- **Soft leak (accepted)**: closing HRV mention. PRD **v1.23** · M1 rollup drops `*`.
- **No git in this chat**.

## 2026-09-11 (P15 → DONE · maintainer stamp)

- **Category**: P1 / §8 M1-P15. Maintainer: fixture-med unfit for training gold; `slot_named_ge2` **5/10** acceptable.
- **Change**: PRD **v1.22** · §8 **M1-P15 → DONE**. M1 rollup `*` only P20 iPhone same-network left.
- **Deferred (non-blocking)**: audit decimals/some ints, `slot_named_ge2` rate, prefs checkbox drift, think perf, fixture-med naming semantic mismatch.
- **No git in this chat** (other agent / task list commits).

## 2026-09-11 (P15 population_commons + gold-gate retarget)

- **Category**: P1 / FR-6.10 · FR-6.12. Maintainer: (1) gold no longer requires fixture-med∧fixture-supp; (2) training commons ints on Manifest whitelist; (3) think optional; (4) run ×10.
- **Change**: schema `fact_card_population_commons.training_ints` → Manifest `domain=population_commons`; audit passes whitelist ints when clause has no card label (% unit alone does not veto); not merged into personal `allowed_values`. DONE gate: gold `slot_named_ge2`; fixture-med∧fixture-supp only for meds-HRV. PRD v1.21. build `pha-v2.3.45-p15-commons-gate`.
- **Acceptance**: `runs_v244_commons_gold10.jsonl` (think=true trial): `slot_named_ge2` **5/10**; hard Markdown 1; no-training-advice 0; audit reject 5. Prefs checkboxes drifted; batch sliced to gold six in-memory, **no prefs write**. Later stamped DONE — see row above.
- **Rollback**: remove commons domain and gate retarget; policy_rev back to v1.1.

## 2026-09-11 (P15 ctx-min + TASK drop % bait + think control)

- **Category**: P1 / FR-6.12. Maintainer: execute review recommendations.
- **Change**: (1) `env-8788.sh` `LLM_TIMEOUT_SECONDS=300` (was 120 → false `model_unavailable`). (2) `fact_card_interpret` `slot_start.FACT_CARD_CONTEXT=min` (drop duplicate full JSON). (3) schema capture negatives 「进行建议/给出建议」; `item_seps` add `) `/`） `; post-compile text dedupe. (4) TASK item 3 drops 70–80% population-percent bait. build `pha-v2.3.43-p15-ctxmin-think`.
- **Control**: `OLLAMA_THINK=true` gold ×5 (`runs_v243_ctxmin_think_gold5.jsonl`): hard Markdown **0/5**; `no_training_advice` **0/5**; fixture-supp named 3/5; dual-named still **0/5**; audit reject 3. timeout=300 confirmed. **Do not** mark P15 DONE.
- **Rollback**: restore slot_start / TASK / schema to v2.3.42; timeout 120.

## 2026-09-11 (P15 CHB one-item rows · gold × 10)

- **Category**: P1 / FR-6.12 acceptance. `qwen3:14b`; `brief_source=chb`; prefs untouched; build `pha-v2.3.42-p15-chb-itemrows`.
- **Result** (n=1..10): dual-named **0/10**; fixture-med/fixture-supp in text both 0; hard Markdown (post-strip) common; audit rejects frequent. **Do not** mark P15 DONE; **no full 20** (maintainer: stop at 10).
- **Evidence**: `reports/p15_eval/runs_v242_chb_itemrows_gold10.jsonl`.

## 2026-09-11 (P15 CHB one-item rows + slot adjacency + accept via CHB)

- **Category**: P1 / FR-6.12. Maintainer: leave DONE gates; row caps + separators live in copy/schema, not Python hardcoding.
- **Change**: (1) Batch runs `recompile_chb_if_stale` and asserts `brief_source=chb`. (2) `background_rows` split one-item-per-row via schema/copy `item_seps`; drop unmarked preamble when schedule marks present; tab notes keep the details column only; `row_caps`/`note_caps` from schema+copy; interleave ends inside schedule buckets so truncation does not drop late items. (3) Assemble `USER_BACKGROUND_BRIEF` right after `USER_ASSESSMENT_PROMPT` (still the sole Tier1 slot). (4) Format gate measured after Markdown strip. build `pha-v2.3.42-p15-chb-itemrows`.
- **Smoke ×5 (`qwen3:14b` · CHB)**: `brief_source=chb`×5; brief contains fixture-med+fixture-supp; dual-named **0/5**; hard Markdown (post-strip) 4/5; several audit rejects. **Path fixed, no naming signal → do not run full 20 yet**. **Do not** mark P15 DONE.
- **Evidence**: `pha_fact_card_selfcheck` / `pha_chb_compiler_selfcheck`; `reports/p15_eval/runs_v242_chb_itemrows_gold5.jsonl`.
- **Rollback**: restore v2.3.41 split/assembly; drop CHB assert in batch.

## 2026-09-11 (named-prose gold × 20: P15 still not DONE)

- **Category**: P1 / FR-6.12 acceptance. `qwen3:14b`; prefs untouched; build `pha-v2.3.41-p15-named-prose`.
- **Setup**: brief `live_notes`×6 with fixture-med+fixture-supp; TASK items 4/5 landed.
- **Result**: dual-named **0/20**; fixture-med 0, fixture-supp 8; audit fail 6 (`unauthorized_value`); hard Markdown/lists **19/20**. Prefs unchanged.
- **Failure families**: still uses 「一、」/`-`/`###`; zero fixture-med naming; fixture-supp occasional; invent-number fuse still works. **Do not** mark P15 DONE; **no** drug-name table / 注意事项 section / gold-sentence if.
- **Evidence**: `reports/p15_eval/runs_v241_named_prose_gold20.jsonl` · `summary_v241_named_prose_gold20.json`.

## 2026-09-11 (P15 named-prose: slot wording into advice + continuous prose)

- **Category**: P1 / FR-6.8 · FR-6.12. Maintainer: land clean contract (no medications/supplements reverse priming; no exhaustive naming).
- **Change**: TASK item 4 continuous narrative + ban bullet/hyphen/1. 2./一、二、; item 5 fold slot wording into advice, forbid vague category labels alone; EN/ZH lead aligned. build `pha-v2.3.41-p15-named-prose`. **No** audit relax / drug-name table / 注意事项 section / gold-sentence if. P15 stays IN_PROGRESS pending gold × 20.
- **Evidence**: `pha_fact_card_selfcheck`; then `reports/p15_eval/runs_v241_named_prose_gold20.jsonl`.
- **Rollback**: TASK / lead back to v2.3.40 noskip wording.

## 2026-09-11 (gold × 20 after no-skip: P15 still not DONE)

- **Category**: P1 / FR-6.12 acceptance. `qwen3:14b` only; prefs untouched; path `run_interpretation`.
- **Setup**: brief `live_notes` notes_used=6 with fixture-med+fixture-supp; TASK/lead already no-skip.
- **Result** (last unique n=1..20): dual-named **2/20** (gate ≥16); fixture-med 2, fixture-supp 9; audit fail 1 (`unauthorized_value`); hard Markdown **17/20**. Prefs unchanged after the run.
- **Failure families**: generic “supplements/meds” instead of named self-reports; fixture-med rarely enters advice sentences; list/Markdown headings still common. **Do not** mark P15 DONE; **no** drug-name table / 注意事项 section / gold-sentence Python if.
- **Evidence**: `reports/p15_eval/runs_v119_gold20.jsonl` · `summary_v119_gold20.json`.

## 2026-09-11 (disk-land v1.19: no skip + fold into advice + weak causal; HRV today mean)

- **Category**: P1 / FR-6.8 · FR-6.12 v1.19 · FR-1.5. Maintainer: land approved v1.19; reject Gemini “MUST 注意事项 section”; HRV follows the Health app today mean.
- **Change**: TASK item 5 + `bg_brief_lead`: present brief stays in-scope, fold into advice sentences, no numbered precautions list; forbid causes / leads to. HRV `temporal.kind=accrual`, Shortcut Find `is today` + Average. pack `2026.09.11.hrv-today`. **Do not** mark P15 DONE pending gold × 20.
- **Evidence**: `pha_fact_card_selfcheck` / `pha_chb_compiler_selfcheck`. build `pha-v2.3.40-p15-noskip`.
- **Rollback**: TASK / lead back to skip; HRV back to overnight last-2-days.

## 2026-09-10 (P15 lineage drops metric-field leftovers)

- **Category**: P1 / FR-6.12 v1.20. Gold-sentence inject’s §Interpretation lineage treated de-numerized “today’s value / percentile / last-12-month mean” stubs as cautions, nudging 14b to fill tables and invert 85%.
- **Change**: lineage keeps only recurring caution sentences; field leftovers are dropped; empty section is omitted. No drug-name table; audit not relaxed.
- **Evidence**: `pha_chb_compiler_selfcheck` fixture: repeated “today’s value/percentile” stays out of lineage; “take it easy” still enters. build `pha-v2.3.39-p15-lineage-stub`. **Do not** mark P15 DONE.
- **Rollback**: remove `_is_lineage_field_stub`.

## 2026-09-10 (P15 TASK slot contract: no invented numbers + present brief must not skip)

- **Category**: P1 / FR-6.8 · FR-6.12 v1.19. Audit fused 21.5/85/95, proving fail-closed works; do not relax audit; no drug-name table.
- **Change**: TASK item 2 forbids derived percents; item 3 drops the `95%` population example; item 5 keeps a present brief in-scope. `bg_brief_lead` no longer says “ignore if unrelated”. CHB projection re-renders the lead from `background_rows` + current copy. Numeric truth remains Manifest / FACT_CARD_CONTEXT.
- **Evidence**: `pha_fact_card_selfcheck` / `pha_chb_compiler_selfcheck` PASS. 8788 `pha-v2.3.38-p15-task-slot`. After maintainer-authorized restore of gold prefs (deep sleep / sleep duration / HRV / RHR / active energy / SpO2 + frozen gold sentence), in-process `qwen3:14b`: `brief_source=chb`, audit rejected `unauthorized_value:85` (derived complement of deep-sleep percentile 15.2, not a dose). Body not landed; fixture-med/fixture-supp not produced. Prefs left as restored. **Do not** mark P15 DONE.
- **Rollback**: TASK / lead back to v1.18 wording; projection back to pre-rendered markdown.

## 2026-09-10 (P15 cut 2: background_rows + USER_CONTEXT_BRIEF projects §Background)

- **Category**: P1 / FR-6.12 v1.18. Maintainer chose the compiler layer; rejected a “training ⇒ supplement-related” TASK patch.
- **Change**: CHB compiles notes into `background_rows[]` (`category` + de-numerized short clause + `rel_key` + `prov_type=user_statement`; no drug-name table, no value/unit). `build_user_context_brief_block` (lifestyle / combined) projects §Background instead of physically dropping it. Interpretation round still uses only `USER_BACKGROUND_BRIEF`; `USER_CONTEXT_BRIEF_PROFILES` **does not add** `fact_card_interpret`. TASK unchanged. Zero leakage into §Facts / Manifest.
- **Evidence**: `pha_chb_compiler_selfcheck`: artifact contains rows; lifestyle slot contains §Background and fixture-med; interpret projection has no §Facts. Artifact `reports/chb/default/brief_5d00dba7bd142656.json` (6 self-statement rows). build `pha-v2.3.37-p15-bg-rows`. P15 gold-sentence caveats remain the acceptance gate; this card is not marked DONE.
- **Rollback**: strip the background section from `USER_CONTEXT_BRIEF`; strip `background_rows` from the artifact.

## 2026-09-10 (P15: hygiene Q=9 delete · split long notes by time-of-day · gold-sentence caveats still not passed)

- **Category**: P1 / FR-6.12 · FR-6.11. Maintainer order: ① dry-run 9 question/imperative notes `--apply`; ② continue P15.
- **Change**: `python3 scripts/pha_memory_hygiene.py --apply` deleted Q=9 (C=6 empty sessions kept); backup `data/backups/pha_storage.20260910T090958Z.db`. `fact_card_copy.bg_brief_split_marks` (morning / noon / evening / before sleep) splits long self-statements after de-numerizing; quota still counts original note rows. Forced recompile `reports/chb/default/brief_cc9fd56284f1aa98.json`. selfcheck: `pha_fact_card_selfcheck`, `pha_chb_compiler_selfcheck` PASS. build `pha-v2.3.36-p15-portrait-split`.
- **Evidence**: gold sentence in-process `qwen3:14b`: prefs unchanged; `brief_source=chb`, notes_used=7 (acceptance run still had a leftover table-header row; after dropping the tab header it is 6), contains fixture-med/fixture-supp; audit passed; did not restate 〔数值略〕; body still has no fixture-med/fixture-supp/supplement caveats (14b skipped them as unrelated per TASK item 5). **Do not** mark P15 DONE, **do not** change audit, **do not** add an if for one gold sentence.
- **Rollback**: remove `bg_brief_split_marks` from copy; remove split-line from the brief builder; CHB uses the previous artifact; restore hygiene from the backup above.

## 2026-09-10 (P15 start: imperative questions stay out of CHB · gold sentence not passed)

- **Category**: P1 / FR-6.12 · FR-6.11. Maintainer order to open remaining P15 acceptance.
- **Change**: `supplement_bg.schema.json` capture-negative added `请分析` / `请核实` / `请核对` / `请再次` / `是否正常` / `是否合理` (same family as existing `请列出`; not a Python blacklist). Read side and CHB §Background drop analysis imperatives. Recompiled `reports/chb/default/brief_5545b3f1c23f2933.json` (only supplement-plan self-statements, no §Facts). selfcheck: `pha_fact_card_selfcheck`, `pha_chb_compiler_selfcheck` PASS.
- **Evidence**: gold sentence in-process `qwen3:14b`: `brief_source=chb`, notes_used=1, contains fixture-med/fixture-supp; audit rejected `unauthorized_value:80` / `92` (in-text “above 80 bpm” / “below 92%”, not brief doses); body had no supplement caveats; Markdown sections. prefs unchanged. **Do not** mark P15 DONE.
- **Rollback**: remove the new tokens from schema; CHB uses the previous artifact.

## 2026-09-10 (P12 wrist temp deferred · P7 share-reference off · open P15 acceptance)

- **Category**: P1 / FR-2.8 · FR-1.5 · FR-6.12. Maintainer order.
- **Change**: wrist-temp permission no longer hangs on P12; deferred to the second checkbox batch. Deep/REM share does not enter registry `reference_range` (user can compute it). P15 moved from DONE* back to IN_PROGRESS, to accept compiled portrait into gold-sentence caveats.
- **Evidence**: this entry.
- **Rollback**: document revert.

## 2026-09-10 (M1-P6 T9 passed · marked DONE)

- **Category**: P1 / FR-1.6. Maintainer verbal confirm: 9/8–9/10 Health app vs daily table is “basically all matching”; can count as pass.
- **Change**: §8 M1-P6 → `DONE`. Task card / review T9 closed. In-bed not in this comparison. Did not open M2, did not change prefs, did not change ingest code.
- **Evidence**: maintainer verbal confirm; daily-table three nights asleep/awake/core/deep/REM in the task-card T9 table; anchor A + T0–T8 already passed.
- **Rollback**: document puts P6 back to IN_PROGRESS (no code to roll back).

## 2026-09-10 (in-bed exits T9 · delete orphan sleep_in_bed)

- **Category**: P1 / FR-1.6. Maintainer order: Health app already deleted in-bed; PHA need not keep it and may delete.
- **Change**: T9 no longer accepts in-bed. Daily `in_bed_hours` was already all empty. Deleted 2 non-`healthkit\|` orphan daily keys: `default|sleep_in_bed|2026-09-06…|0.73`, `default|sleep_in_bed|2026-09-07…|8.93`. Did not split the ingest whitelist (In Bed samples can still write; none → empty); prefs unchanged.
- **Evidence**: after delete, `metric_type=sleep_in_bed` count 0; daily in_bed non-empty 0.
- **Rollback**: restore from `data/backups/pha_storage.20260910T082534Z.db`. **Do not** mark P6 DONE.

## 2026-09-10 (M1-P6 T8 doc closeout · T9 store-side write-up)

- **Category**: P1 / FR-1.6 · FR-1.7. No ingest code change.
- **Change**: PRD §8 P6 row dropped the stale “owes T7”; task-card drift table zeroed, leftover is T9 only; review §6.2 synced. In-store 9/8–9/10: asleep+awake=session span, stage sum=total union, `in_bed` empty, no orphan `sleep_*` daily keys; latest sleep ingest 200 + receipt. `pha_healthkit_ingest_selfcheck` PASS.
- **Evidence**: daily three nights; `GET /ingest/healthkit/last` `ok=true` wake_day=2026-09-10; deep-sleep below check sentence with no judgment words.
- **Rollback**: document revert. **Do not** mark P6 DONE (missing Health app screenshots).

## 2026-09-10 (Mac live card: P20 exclusive + P15 brief_source=chb)

- **Category**: P1 run acceptance (prefs untouched).
- **On site**: `qwen3:14b` in-process `run_interpretation`. exclusive “only look at today’s deep sleep”: inject only `sleep_deep` 1.1h; audit passed; body has no HRV/resting/SpO2/energy topical sections. Gold-sentence emphasis: audit passed, `brief_source=chb` (2 rows); model still used Markdown sections and wrote the baseline mean 2h as “today’s deep sleep” (number is in Manifest so audit does not reject). Training / opening-line still not product P0.
- **Rollback**: no code.

## 2026-09-10 (M1-P20 exclusive inject + M1-P15 CHB + read-side question filter)

- **Category**: P1 / FR-6.8 · FR-6.12 v1.16.
- **Change**: ① Drop capture-negative questions before brief quota (same lexicon as P18). ② exclusive interpretation-round LLM inject ⊆ catalog named rows; HTML visible card is still the full card; empty inject fail-closed. ③ Opening-line / training judged at the rule layer; eval gold exits product P0. ④ P15: CHB §Background + interpretation thread + combined hash; `GET /proactive/fact-card` background-compiles once the same day; interpret brief prefers CHB projection (no §Facts). Item 4 model swap not done.
- **Evidence**: `pha_p20_selfcheck`; `pha_chb_compiler_selfcheck` P15; `pha_fact_card_selfcheck` P14 question fixture; hygiene script Q-class dry-run lists, `--apply` deletes (C still kept by default).
- **Rollback**: `PHA_EXCLUSIVE_INJECT_NAMED=0` (exclusive back to full-card inject); `PHA_CHB_AUTOCOMPILE=0` (no background compile, brief falls back to live_notes); read-side filter via git revert.

## 2026-09-10 (M1-P19 eval-audit landed · encoded)

- **Category**: P1 / FR-6.8 · FR-6.13 v1.15.
- **Change**: emphasis structure sentence; Tier0 does not tail-cut Manifest/card rows; chat card-issue ⊆ FACT_CARD_CONTEXT; workout hints unbound from daily_readiness training words. Handoff [`handoff-2026-09-10-eval-audit-solution.md`](handoff-2026-09-10-eval-audit-solution.md). P15 not opened.
- **Evidence**: offline `pha_p19_selfcheck` + `pha_p17_p18_selfcheck` + `pha_fact_card_selfcheck`. On-device separately scheduled.
- **Rollback**: same as handoff §3.

## 2026-09-09 20:08 (M1-P17 / P18 on-device 8788)

- **Category**: P1 run acceptance. pid 65097, `qwen3:14b`, after launchd kickstart.
- **On site**: `pha_restart_accept.sh` PASS. Gold sentence went `/proactive/fact-card/interpret` + `/api/chat` (new session).
- **Evidence**:

| id | Path | Result |
|---|---|---|
| O2 | interpret, assessment prompt unchanged (overall + focus RHR/HRV/sleep + training) | `daily_readiness` + `emphasis`; audit `passed=true`; discussed deep 0.5h / HRV / resting; active energy wrote “still in progress (as of 20:04)” |
| O3 | same round + card `active_energy` partial | interpret/card assessment sentence has no “not on Mac yet / still on phone” |
| C1 | new session “what medications am I taking now?” | `context_lookup`; **no** `fact_card`; listed fixture-med-C/fixture-med; did not invent “you are taking” a category with no file |
| C2 | “how has HRV trended over the last 90 days?” | not lookup; HRV mean card 35.59ms (2026-06-12~2026-09-09) |
| C3 | same session follow-up “meds vs HRV and resting HR” | did not skip into a 90d energy card; card ⊆ HRV mean + resting HR mean |
| C4 | around C1 | notes 70→70 |

- **Known copy gaps (do not block closeout)**: ① emphasis allows a passing mention; the model still opened extra “activity / respiratory rate and SpO2” sections and did not directly answer “can I strength-train”. ② C3 took the Data lane; `wearable_only` has no `USER_BACKGROUND_BRIEF`; body is window fail-closed (audit false) and did not carry the meds C1 already listed — this is the agreed cost of Data > Context, not another energy-card bounce.
- **Rollback**: same as the encoding entry.

## 2026-09-09 18:45 (M1-P17 / P18 encoded · DONE*)

- **Category**: P1 / FR-6.8 · FR-6.14 · FR-2.10 copy · FR-6.13 card-issue scope.
- **Change**: catalog v1.9; TASK three bands; copy split by domain; `context_lookup` Arbiter + skip veto + card-issue ⊆ scope + questions not captured + chat inject quota dedupe. Flags default on. P15 not opened.
- **Evidence**: offline `pha_p17_p18_selfcheck` O1–O3 / C1–C4 PASS. On-device O2+O3 / C1–C4 pending.
- **Rollback**: `PHA_ASSESSMENT_OUTLINE=0` (fall back to P9.5b named-row exclusive); `PHA_CONTEXT_LOOKUP=0` (card-issue falls back to “issue if entries exist”).

## 2026-09-09 18:21 (v1.14 docs: outline bands + dossier lookup · not encoded)

- **Category**: P1 / FR-6.8 · FR-6.14 · FR-2.10 copy · FR-6.13 card-issue scope.
- **Change**: PRD v1.14; 3F §15; handoff [`handoff-2026-09-09-outline-and-context-lookup.md`](handoff-2026-09-09-outline-and-context-lookup.md). Open **M1-P17 / M1-P18** (TODO). Ban scanning the whole card, ban medication phrases winning Data, ban length heuristics fishing for plans, ban replacing `/api/chat` with a LibreChat full stack.
- **Evidence**: same-day on-device interpret / ask-meds chats; after audit rejected the original scheme the maintainer agreed to land docs.
- **Rollback**: document revert; no runtime flag.

## 2026-09-09 16:51 (FR-6.13 on-device acceptance · close DONE*)

- **Category**: P1 / FR-6.13 run acceptance.
- **On site**: `pha_restart_accept.sh` launchd kickstart, pid 41270 (16:24); earlier 14:17 process mixed-module (`episodic=` TypeError / `infer_wearable_metric_ids` ImportError) gone.
- **Evidence** (`qwen3:14b` · user=default · live ledger 2026-09-09; audit `passed=true`):

| id | Path | Result |
|---|---|---|
| H9-zh same class | Mac `/api/chat` + web chat | Two training-advice stretches; RHR 62 / HRV 32.8 / sleep 8.2h; strength training OK but control volume. Passed after mixed-module failure then restart |
| interpret | `POST /proactive/fact-card/interpret` + full-card Chinese page | `status=done`, 16:31; no longer “local model did not respond”. Easy-day copy; did not directly answer strength training |
| H10 / H10E | skip-LLM | Point-day five items 8.22 / 0.47 / 2.45 / 5.3 / 0.78 (2026-09-09), no 90d mean |
| H11 | same session H10 then undated follow-up | deep 0.47 / core 5.3 / awake 0.78, anchor still 2026-09-09 |
| H12 | skip-LLM | same H10 five items |
| H13 / H13E | skip-LLM fail-closed | “库内没有 2026-09-09 的静息心率” / `No verified resting HR … 2026-09-09`; body has no 62 |
| H9E | `/api/chat` en | audit passed; English; no Trend review three-section titles; high-intensity strength training needs sleep recovery. Did not name 32.8/62 (qualitative range cite) |

- **Known copy gaps (do not block closeout)**: chat may call 8 Sep RHR=62 “today”; fact card labeled “8 Sep, most recent”. Whether strength training is OK: chat says yes with volume control; card interpretation writes easy day.
- **Rollback**: same as the 15:20 entry.

## 2026-09-09 15:20 (FR-6.13: chat-box interpretation shares source with the fact card)

- **Category**: P1 / FR-6.13.
- **Change**: chat-side Registry as single source of truth; `wearable_daily_review` reuses fact-card T0; point-day grain can inherit; fail-closed does not swap day or metric. No iOS card UI change, no interpret cache-key change.
- **Evidence**: offline `pha_chat_fact_card_parity_selfcheck` H9–H13 / H9E–H13E. On-device see the 16:51 entry above.
- **Rollback**: `PHA_DAILY_READINESS_PROFILE=0`; `PHA_EPISODIC_GRAIN_ANCHOR=0`.

## 2026-09-09 14:20 (M1-P14: USER_BACKGROUND_BRIEF into interpretation)

- **Category**: P1 / FR-6.12.
- **Change**: de-numerize builder + posterior extractor; Tier1 sole slot; TASK item 5; cache key includes brief digest; HTML “referenced N background notes”. Audit policy unchanged. System-prompt default cap 10k→12k (otherwise a 9-metric card soul+T0 already exceeds 10k and T1 brief never reaches the model).
- **Evidence**: `pha_fact_card_selfcheck` P14 PASS; registry `--write` PASS. Live card, live prefs, `qwen3:14b`, in-process `run_interpretation` zh/en 3 rounds each (prefs unchanged after the run):

| id | Audit | Dose / 〔数值略〕 | Unnamed row starts a new section | Language mix | Background caveats |
|---|---|---|---|---|---|
| zhT1 | pass | none | none | none | unnamed supplements (latest notes are questions; model skipped per TASK item 5) |
| zhT2 | pass | none | none | none | same |
| zhT3 | pass | none | **yes** (SpO2/respiratory rate/VO2max) | none | same |
| enT1 | pass | none | none | card T1 source Chinese names | same |
| enT2 | pass | none | none | same | same |
| enT3 | pass | none | none | same | same |

  Pass line: audit 6/6; dose/elision 0/6; unnamed ≤1/6; brief lead-in leak 0/6. **Related background caveats 0/6** (did not reach ≥4/6): live notes “latest N per class” fetched supplement Q&A, not “I take X” self-statements; model skipped unrelated background per TASK. Do not retune audit. Real supplement/schedule notes remain in store; wait for P15 CHB compile then project.
- **Rollback**: `PHA_FACT_CARD_BG_BRIEF=0`; system cap back to 10000.

## 2026-09-09 13:10 (M1-P13: interpretation round zero-writes chat memory)

- **Category**: P0 / FR-6.11.
- **Change**: `memory_write_policy`; `TurnMemorySink`; `maybe_capture_chat_background` rejects `[snake_case_tag]`; `scripts/pha_memory_hygiene.py` (dry-run by default).
- **Evidence**: `pha_fact_card_selfcheck` PASS; registry `--write` + selfcheck PASS. After maintainer confirm, apply: A 57 sessions + B 24 notes deleted, C 6 empty sessions kept; backup `data/backups/pha_storage.20260909T051013Z.db`.
- **Rollback**: restore `data/pha_storage.db` from that backup; Sink always writes=True.

## 2026-09-09 12:20 (PRD v1.12: proactive Agent and chat-memory sharing plan · open M1-P13 / P14 / P15)

- **Category**: product / docs. No code.
- **Finding** (query `data/pha_storage.db`): interpretation round `session_id=None` borrows the chat pipeline → each button creates a new session (56) and writes `chat_messages`; old Chinese synthetic prompt captured as 7 `medication` background notes; 17 `unstructured_vision` notes are `[vision_parse_failed]` error strings; `chb_briefs` 0 rows. Reverse: user self-statement background (supplement 124 / medication 12 / sleep 4) and CHB are invisible to interpretation (FR-6.8 design).
- **Decision**: memory must be shared. Three layers: A structured self-statement → non-numeric-source Tier1 `USER_BACKGROUND_BRIEF`; B episodic memory stays out; C CHB unified supply. Interpretation round zero-writes chat memory (registry attribute `memory_write_policy`).
- **Docs**: PRD §1.3a second meaning, FR-6.11 / FR-6.12, §8 three cards, §11 two rows; handoff [`handoff-2026-09-09-proactive-memory-sharing.md`](handoff-2026-09-09-proactive-memory-sharing.md).
- **Order**: P13 → P14 → P15, accept card by card; hygiene script apply needs maintainer confirm.

## 2026-09-09 12:00 (model cut to qwen3:14b + `OLLAMA_THINK`)

- **Category**: runtime / provider. commit `0ed4898`, not pushed.
- **Change**: `pha/ollama_payload.py` `apply_think_option` / `apply_ollama_options`; `OllamaProvider` four `/api/chat` bodies go through the new functions. If `OLLAMA_THINK` is unset, do not send `think` (qwen2.5 rejects explicit think); `false` → `think=false`. env-8788.sh / `.env`: `OLLAMA_MODEL` / `OLLAMA_MEDICAL_MODEL=qwen3:14b`, `OLLAMA_THINK=false`.
- **Evidence**: live card live prefs in-process 1 round each: zh audit passed 0 violations 72.5 s; en audit passed 0 violations 77.0 s; no `<think>` leak; did not invent sleep rows not on the card. Soft issue: RHR row is `prior_day`, Chinese wrote “today’s resting HR” (existing class; do not retune audit).
- **Pending**: `OLLAMA_KEEP_ALIVE=0` cold-loads 9.3 GB every interpretation; changing to `10m` is the maintainer’s call.
- **Rollback**: put the three env lines back to `qwen2.5:7b-instruct` and delete `OLLAMA_THINK`; code may stay.

## 2026-09-09 08:55 (M1-P9.5b: TASK forbids starting a new paragraph for unnamed rows)

- **Category**: P1 (interpretation outline). After soul dropped the three-step titles, occasional still writes unnamed sleep/respiratory-rate rows (enT3).
- **Change**: `_FACT_CARD_INTERPRET_TASK` item 1 adds: `Do not start a new paragraph or sentence for rows the assessment did not name.` (no metric names). Cache key invalidates automatically with TASK hash. build `pha-v2.3.34-fact-card-task-p95b`.
- **Evidence** (assessment temporarily “only talk RHR/HRV/VO2max”; restored user prefs “resting HR+HRV+sleep” after the run):

| id | Audit | Three-step titles | SpO2/resp rate | Sleep drift | RHR | HRV | VO2 |
|---|---|---|---|---|---|---|---|
| enT1–3 | 3/3 | 0/3 | **1/3** | 1/3 | 3/3 | 3/3 | 1/3 |
| zhT1–3 | 3/3 | 0/3 | **0/3** | 1/3 | 3/3 | 3/3 | 0/3 |

  SpO2/respiratory rate hit handoff §5 pass line. Residual sleep/VO2 misses are 7b occasional; handoff §6: upgrade only at ≥2/3; this round does not retune audit or add label filters.
- **Rollback**: delete that sentence.

## 2026-09-09 08:35 (M1-P9.3: stop Ollama + cross-day cache real acceptance)

- **Category**: acceptance / FR-6.5 / FR-6.6.
- **Cross-day**: today’s key differs from `calendar_day-1`; planting yesterday’s fake `done` does not leak into today’s `load_interpretation_for_user`; same-key second POST `started=False`.
- **Model unavailable**: temporary PHA `:8799` + `OLLAMA_BASE_URL=http://127.0.0.1:9` → interpretation `failed` / `model_unavailable` / `Connection refused`; SSR `humanize` → “local model did not respond” + button “Retry”. Rule-layer metrics still present. Note: killing local Ollama is pulled back up by Electron/launchd; a dead port is a more stable real test.
- **Change**: docs only (PRD §8 P9.3 → DONE). No code.
- **Rollback**: none.

## 2026-09-08 22:50 (M1-P9.5: interpretation-only soul, kill three-step consult focus drift)

- **Category**: P1 (interpretation outline). English interpretation forced `Trend review / Related markers / Recommendations`, reading card SpO2/respiratory rate as “related markers”.
- **Root cause**: `fact_card_interpret` used the full `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` three-step consult method step 2.
- **Change**: `PHA_FACT_CARD_SOUL_MINIMAL`; `select_soul_base`; cache-key hash includes soul; `harness_report` dry-run path not merged (interpretation does not enter that door; noted as TODO).
- **Evidence**: selfcheck PASS. Run acceptance (build `pha-v2.3.33-fact-card-soul-p95`) zh/en 3 rounds each:

| id | Audit | Three-step titles | SpO2/resp rate | RHR | HRV | VO2 |
|---|---|---|---|---|---|---|
| enP1–3 | 3/3 pass | 0/3 | 0/3 | 3/3 | 3/3 | 2/3 |
| zhP1–3 | 3/3 pass | 0/3 | 0/3 | 3/3 | 3/3 | 0/3 |

  VO2 miss is a known model occasional, not this round’s gate. prefs restored to zh-CN.
- **Rollback**: delete the fact_card branch in `select_soul_base`; cache key invalidates automatically.

## 2026-09-08 22:20 (M1-P9.4.1: English yearless date mask)

- **Category**: P1 (audit). `September 3` with no year was not treated as a date; day digit `3` was rejected.
- **Change**: fact_card audit uses `_extract_fact_card_dates` to align yearless EN/CN month-day to card `allowed_dates`; mask generates surface forms such as `September 3` / `9月3日`. Policy rev `v1.1`.
- **Evidence**: `FC-en-yearless-ok/bad` selfcheck PASS.
- **Rollback**: restore `_extract_fact_card_dates` call and `FACT_CARD_AUDIT_POLICY_REV`.

## 2026-09-08 20:40 (M1-P9.4 landed: fact_card numeric graded audit)

- **Category**: P1 (audit) / fact-card interpretation.
- **Change**: `numerics_manifest` adds `fact_card` policy (clause-level S/E/T1); card-side `_audit_interpretation_text` delegates to the same function; `rejected_text`; TASK split + `{T1_TEMPLATE}` by locale; Tier0 `slot_floor` + min keep values; failure copy merged.
- **Evidence**: `pha_numerics_manifest_selfcheck.py` / `pha_fact_card_selfcheck.py` / `pha_chat_turn_fsm_selfcheck.py` PASS; §2.4 eighteen cases reproduced locally and aligned.
- **Rollback**: restore `numerics_manifest` fact_card branch and `fact_card_interpret` delegation; cache key invalidates with TASK/policy hash.

## 2026-09-08 20:11 (M1-P9.4 card opened: extra-card numeric graded loosen + single audit · docs only)

- **Category**: product consensus / audit contract. **No code change.**
- **Finding**: live interpretation repeatedly rejected `2、95、2、3、95`. `2` came from `SpO2`/`VO2max` labels (card-side `\d+` with no boundary); `96.0` because the context block gave the original value while the whitelist only had `96`; `95`/`70–80`/`2–3` are popular-science integers; 7b cannot write the T1 template; card-side T1 regex only recognized Chinese. harness audit on the same text `passed=True`.
- **Decision**: PRD v1.10 FR-6.10 from “T1 only” to three context grades (S must reconcile / E pass + telemetry / T1 zh/en equal weight); FR-6.3 audit is one pass only. Scale and 18 cases in handoff v3 §2.
- **To execute**: [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) §9 order; 8462695 not pushed, amend first.

## 2026-09-08 (M1-P9.3: interpretation outline lives in TASK; withdraw the metric parser)

- **Category**: fact-card interpretation / anti-hardcode. Previous cut used assessment-prompt alias matching to narrow the manifest and rejected off-focus numbers — routing for “only look at RHR/HRV/SpO2”, violating constitution Article 4 and FR-6.8 (the whole card is the evidence source).
- **Evidence**: handoff §4.3: TASK lives on the profile; assessment prompt is an outline not a numeric source. selfcheck: TASK contains the outline sentence, no concrete metric names, no `FACT_CARD_CONTEXT.focus`; context still keeps every card row.
- **Change**: `fact_card_interpret` TASK: USER_ASSESSMENT_PROMPT is the outline; if named, talk only those rows; non-empty `value` must not be called missing. Slot order remains TASK → assessment prompt → card → manifest (attention order, not a metric whitelist). Removed alias/deny list/focus filter and `focus_missing_but_present`. Cache key `task_outline_v2`.
- **Rollback**: restore `harness_plan._FACT_CARD_INTERPRET_TASK`.
- **Maintainer next**: refresh the full card then tap “Generate interpretation” again. Still owes stop-Ollama and a real cross-day look.

## 2026-09-08 (i18n: dashboard golden metrics + proactive card git-default English)

- **Category**: Dashboard / fact-card display. Maintainer: English UI still showed Chinese golden-metric bar; proactive agent needs zh and en; repo default English.
- **Evidence**: `GOLDEN_WEARABLE` used to hardcode “每日步数” etc.; `label_zh` did not follow the top-bar language. iPhone Safari 16:21 interpretation already out (same text as Mac).
- **Change**: golden metrics / groups git-default English + `label_zh`/`label_en`; `GET /available_metrics?locale=` folds `label`/`unit`/`hint` into the current language; after language switch, redraw from in-memory bilingual fields then re-fetch catalog. Static cache bust `i18n1`. Fact card `DEFAULT_LOCALE=en-US`; `fact_card_copy.py` zh/en chrome/rules/notification copy. Existing `data/fact_card_prefs.json` is still zh-CN, so live Chinese is unchanged. T1 disclosure-block shell remains `【参考标准】…（来源：…请自行查证）` (audit regex depends on it). Lab item names still come from SQLite originals; not Anglicized this round.
- **Rollback**: restore `metric_catalog_ui.py` / `metrics_api.py` / `app.js` / `fact_card_copy.py` / `DEFAULT_LOCALE`.
- **Maintainer next**: dashboard English should show Daily steps / Resting HR; Chinese should show 「每日步数」. Switching the fact-card footer to English changes the interpretation cache. Still owes stop-Ollama and a real cross-day cache look.

## 2026-09-08 (M1-P9.3: on-card reference range may enter interpretation body)

- **Category**: fact-card interpretation audit. Mac Safari “Generate interpretation” was discarded whole by the card-side second audit with `unauthorized_value:60/100`.
- **Evidence**: harness `numerics_audit.passed=true` and cited 60/100 (manifest `domain=reference`); card T1 already wrote “60–100 bpm”. Card-side had stripped reference low/high from the body whitelist, inconsistent with FR-6.3 “⊆ facts ∪ baseline ∪ reference range” and harness. Failure copy “numbers not on the card” does not hold for these two. selfcheck PASS; `pha_restart_accept.sh` PASS (pid 863). Mac Safari third-round “Retry” succeeded at 16:21 (first two rounds: 60/100 card-side too strict, then model invented 1.2 and harness rejected).
- **Change**: `_body_numeric_atoms` keeps card `reference.low/high`. selfcheck: body “60–100” passes; extra-card “80” still rejected; T1 wrapping 120–140 still rejected.
- **Rollback**: restore `_body_numeric_atoms` stripping of reference tokens.
- **Maintainer next**: still owes iPhone Safari full flow, stop-Ollama real test (confirm a time window). Cross-day cache needs past midnight or a real `calendar_day` change.

## 2026-09-08 (M1-P9.3: cross-day cache + English date audit; on-device gate incomplete)

- **Category**: fact-card interpretation boundary. Continues after P9.2.
- **Evidence**: `pha_fact_card_selfcheck.py` PASS: `Sep 7, 2026` / `9月7日` treated as as_of; `Jun 10, 2026` rejected; `calendar_day` in cache key; failed-state HTML “local model did not respond” + “Retry”. 16:03 live quantity Shortcut already carried `pack_version=2026.09.08.priority-1e`.
- **Change**: interpretation cache key adds `calendar_day` (invalidates across days even if as_of is unchanged). `_extract_normalized_dates` accepts English month names with year; card-side also accepts yearless “9月7日 / Sep 7”. §6 decision 5: notification body dates **still ISO** (Shortcut and selfcheck depend on it), not localized.
- **Rollback**: restore `fact_card_interpret.py` cache key and date extract; restore `numerics_manifest.py` `_DATE_EN_RE`.
- **Maintainer next**: on the same Wi-Fi open the full card in iPhone Safari and run interpretation; to accept “model unavailable”, confirm a time window then stop Ollama and tap “Generate interpretation” (do not stop PHA). en-US can be switched at the full-card footer then refresh.

---

## 2026-09-08 (Find catalog + skip wrist-temp Shortcut + M1-P9.2 presentation)

- **Category**: Shortcut Find source of truth / fact-card presentation. After another maintainer run, wrist temp still had no permission toggle; fact card could already sync.
- **Evidence**: 9/8 daily has steps 6219, energy 144.6, RHR 65, HRV 32.9, SpO2 96.0, respiratory 13.0, asleep 6.2h; VO2max 51.48 @ 9/3; `wrist_temp_c` still empty. A wrong Find label means the permission toggle never appears.
- **Change**: added `storage/registry/shortcut_health_find_catalog.json`; only `device_verified` writes into the Shortcut. Wrist temp `shortcut_skip_reason=shortcuts_find_unverified`. Quantity Shortcut 7 Finds. `shortcut_pack_version` → `2026.09.08.priority-1e`. VO2 `latest` no longer counts as “prior-day value”. P9.2: prefs `locale`, HTML dates by language, interpretation strips Markdown, band labels use value direction (above/flat/below), cache key includes locale.
- **Rollback**: restore Find catalog / registry pack / `healthkit_sync_plan` / `fact_card_html` / `fact_card_locale.py`.
- **Maintainer next**: desktop `PHA同步健康.shortcut` **replace once** (wrist-temp Find already removed). Same Wi-Fi open the full card and check Chinese dates. P9.3 then does iPhone Safari / stop Ollama / en-US on-device.

---

## 2026-09-08 (wrist-temp Find label: Wrist Temperature)

- **Category**: Shortcut Find. 15:16 run finished 7/8 ingest; wrist temp had no POST. Device reported no permission and the panel had no toggle.
- **Evidence**: `Apple Sleeping Wrist Temperature` is the SDK name; Find selector and permission panel use `Wrist Temperature` (same pit as Blood Oxygen / Oxygen Saturation).
- **Change**: registry wrist-temp Find → `Wrist Temperature`. `shortcut_pack_version` → `2026.09.08.priority-1d`.
- **Maintainer next**: replace “PHA sync health” once more; tap Allow Access on the wrist-temp Find.

---

## 2026-09-08 (Find label: SpO2 is Oxygen Saturation)

- **Category**: Shortcut Find selector label. On-device: permission panel has no Blood Oxygen; Find Type=`Blood Oxygen` reports No Samples Found; VO2 reports no Cardio Fitness permission.
- **Evidence**: iOS 26.2 ActionKit selector true names are `Oxygen Saturation` / `Apple Sleeping Wrist Temperature` / `VO2 Max`. Health app English UI “Blood Oxygen” cannot be a Find label (same pit as Active Calories). Ledger SpO2 last day 2026-06-09, so last 2 days were empty anyway.
- **Change**: registry Find → those true names; VO2 `freshness_days` 90→180 (last reading 6/3 already >90 days). `shortcut_pack_version` → `2026.09.08.priority-1c`.
- **Maintainer next**: replace “PHA sync health”; tap **Allow Access** on SpO2 / wrist-temp / VO2 Finds (the toggle only appears in the panel after authorize).

---

## 2026-09-08 (Shortcut Get Details Unit concatenates every row’s unit)

- **Category**: ingest units / Shortcut pack. On-device: fact-card top `unknown_unit:count count count…`; “PHA sync health” *There's a problem* at the respiratory-rate Find.
- **Evidence**: 14:52 POST steps 5985 / energy 130.339 rejected, `unit` was each sample unit joined with newlines; respiratory last-2-days had no Limit, Get Details stalled the Shortcut. Selfcheck PASS.
- **Change**: JSON `unit` becomes the registry literal, no longer Get Details Unit; overnight-metric Find Limit 150 (same cap as sleep) + First Item by Start Date; server takes only the first word of a concatenated unit. `shortcut_pack_version` → `2026.09.08.priority-1b`.
- **Rollback**: restore `build_pha_ingest_shortcuts.py` / `healthkit_units.py` / registry pack version.
- **Maintainer next**: desktop `PHA同步健康.shortcut` **replace once more**. Fact-card Shortcut need not be swapped for this. On 5G, `.local` times out; must be the same Wi-Fi.

---

## 2026-09-08 (M1-P12: priority pack phase 1 + zip as final truth)

- **Category**: registry / ingest units / Shortcut pack / zip overlays increment / fact-card coverage.
- **Evidence**: `pha_wearable_registry_selfcheck.py`, `pha_fact_card_selfcheck.py`, `pha_healthkit_ingest_selfcheck.py` PASS.
- **Change**: SpO2/respiratory/VO2max/wrist temp become eligible and wire into the Shortcut; POST carries `unit` and `pack_version`; unknown unit / out of range 400; VO2max `temporal.kind=latest` not counted in coverage; zip import deletes healthkit rows on and before the `xml_max` day and writes a reconciliation JSON. PRD v1.8. Do not start Pulso.
- **Rollback**: restore registry `shortcut_pack_version`, ingest whitelist, Shortcut generator, `zip_healthkit_overlay.py`.
- **Maintainer next**: on-device check Find labels (SpO2 / respiratory / VO2 Max / wrist temp) then replace “PHA sync health”; backfill export.zip quarterly.

---

## 2026-09-08 (Shortcut If empty Condition: WFInput must Type=Variable)

- **Category**: Shortcut generator.
- **Evidence**: on-device “PHA sync health” opened with *Please choose a value for each parameter*; If Condition blank. In the plist `WFInput` was a bare `WFTextTokenAttachment`; the editor treated it as an empty parameter. `python3 scripts/pha_healthkit_ingest_selfcheck.py` PASS (If `WFCondition=100` has any value + `Type=Variable`).
- **Change**: empty-set skip becomes “Find result has any value”; wrap `WFInput` in `Type=Variable`. Re-sign `pha-sync-health.shortcut`.
- **Rollback**: restore `_if_has_any` / `_variable_input`.
- **Maintainer next**: desktop `PHA同步健康.shortcut` to iPhone **replace once**.

---

## 2026-09-08 (M1-P9.1: interpretation-only profile + date-normalized audit)

- **Category**: fact-card button interpretation stacked on harness (not the proactive path).
- **Evidence**: `python3 scripts/pha_fact_card_selfcheck.py` PASS (365d card rejects “last 90 days”; rejects extra-card dates; Chinese as_of passes; T1 reference range passes; harness `future_date` rejects; extra-block 120–140 rejects / T1 ACSM passes; extra-block “reference range 60–100” rejects; changing checkboxes changes cache key); `pha_chat_turn_fsm_selfcheck.py` / `pha_numerics_manifest_selfcheck.py` PASS.
- **Change**: `fact_card_interpret` profile; user_message is a fixed short sentence, assessment prompt goes in `USER_ASSESSMENT_PROMPT` slot; withdraw the 9/7 evening “if harness already passed, only intercept ≥100 extra large numbers”; failed state shows the rejected token to the user. PRD FR-6.8/6.9/6.10, §4.2, §8 P9.1 DONE.
- **Rollback**: restore `fact_card_interpret.py` audit and chat `profile_override` wiring; registry `--write` drop that profile.

---

## 2026-09-08 (M1-P10 + M1-P11: temporal semantics + checkbox = what you see + Shortcut full set)

- **Category**: registry / fact-card prefs / Shortcut generator / ingest quantity path.
- **Evidence**: `python3 scripts/pha_fact_card_selfcheck.py` PASS (card = checkboxes, checking only deep does not pull in-bed, sync plan independent of prefs, RHR D-1 has band, D-3 empty, accrual at 08:00 in-progress not banded, notification contains “prior day”); `python3 scripts/pha_healthkit_ingest_selfcheck.py` PASS (`empty_sample`, quantity Shortcut 4 Finds, RHR last-2-days + Limit 1 + Start Date, count=0 If skip).
- **Change**: delete `reveal_when_selected`; `shortcut_sync_specs` becomes the registry full set; `temporal.kind` drives value pick; quantity Shortcut empty set does not POST; ingest empty-value receipt `empty_sample`. PRD §4.1 / FR-2.10 / §8 P10 P11 DONE.
- **Rollback**: restore registry, `fact_card.py` / `fact_card_prefs.py` / `healthkit_sync_plan.py` / Shortcut generator / ingest quantity path; regenerate Shortcuts.
- **Maintainer next**: export on Mac and on iPhone **replace once** “PHA sync health”. After that, changing checkboxes does not reinstall.

---

## 2026-09-08 (PRD v1.7: Shortcut full-set sync + checkbox = what you see + open P9.1 / P10 / P11 / P9.2 / P9.3; docs only)

- **Category**: PRD consensus change (FR-1.5 / FR-2.7) + handoff docs. **No code.**
- **Evidence**: 9/8 08:12 on-device screenshot checked 5 items, card listed 9 (registry `reveal_when_selected` implicit expand); page required reinstalling the Shortcut after changing checkboxes; 08:00 resting HR empty POST 400, energy crumbs judged below, interpretation rejected by harness with `unauthorized_wearable_count:100`. Possibility analysis: Mac cannot reach HealthKit; iOS “Find Health Samples” types cannot be parameterized; therefore “refresh and new data appears” and “dynamic Find from a server list” are impossible; feasible A (Shortcut full set + card filters by checkbox) / B (full-set Find + runtime If gate). **Maintainer 08:27 chose A.**
- **Change**: PRD v1.7: FR-1.5 becomes “Shortcut syncs the registry `eligible ∧ shortcut_health_type` full set, independent of checkboxes; accrual one number, once-a-day types carry a date, empty set skipped”; FR-2.7 adds “card = checkboxes, no implicit expand, denominator = checkbox count”; §8 registers M1-P9.1 / P10 / P11 / P9.2 / P9.3; §11 three rows. `handoff-2026-09-08-fact-card-interpret-v2.md` finalized (including §5c.5 execution list); `pha-fact-card.md` sync section rewritten; roadmap 1e.
- **Rollback**: restore those docs to v1.6.

---

## 2026-09-07 (M1-P9 browser acceptance + audit tighten)

- **Category**: full-card on-device/browser acceptance.
- **Evidence**: browser opened `/proactive/fact-card/view`: assessment prompt saved and echoed; “Generate interpretation” first showed “generating”; failed state showed “not generated (audit failed)” and retryable; finally `status=done`, page rendered model name and time. Root cause: supplemental atom audit treated harness T0 “last 90 days / range anchor” as foreign numbers; and `failed` cache had blocked retry.
- **Change**: date-fragment whitelist; `failed` can POST again; when harness `numerics_audit.passed`, intercept only ≥100 foreign large numbers; interpretation instruction stresses do not invent dates. selfcheck PASS; official restart PASS.
- **Rollback**: restore `fact_card_interpret.py` audit logic.

---

## 2026-09-07 (M1-P9 my assessment prompt + button interpretation)

- **Category**: full-card user-triggered interpretation (not the proactive path; stacked on harness).
- **Evidence**: `python3 scripts/pha_fact_card_selfcheck.py` PASS (prefs echo / over-long 400; fake stream: foreign numbers `audit_rejected`, T1 block `done`, exception `model_unavailable`; no button tap `interpretation is None`; same-key second POST `started=False` no second call). Notification and `assessment` contain no interpretation.
- **Change**: `fact_card_prefs.assessment_prompt` (≤2000); `pha/fact_card_interpret.py` cache `data/fact_card_interpret/{sha256}.json`, generated via `stream_pha_chat_events`; `POST/GET /proactive/fact-card/interpret`; `load_fact_card` top-level `interpretation`; HTML “my assessment prompt” + “AI interpretation (experimental)” polling. Ban bare Ollama, ban pre-generation, ban putting it in the notification.
- **Rollback**: remove interpret module and routes; restore prefs/HTML/load_fact_card/selfcheck; delete cache directory.

---

## 2026-09-07 (M1-P8 HRV column semantics: RMSSD column → SDNN)

- **Category**: ledger semantics / wearable read path (stacked on harness ACK).
- **Evidence**: before migrate, `wearable_data` 11652 rows `metric_type=hrv`, of which 9714 `sample_id` contain `HeartRateVariabilitySDNN`, the rest mostly `default|hrv|` daily mirrors; no true RMSSD in store. `python3 scripts/pha_migrate_hrv_rmssd_to_sdnn.py`: daily table copied 1937 rows → `hrv_sdnn_ms` (now 1938), samples relabeled 11651→`hrv_sdnn`. 9/6 card: `hrv_sdnn_ms=40.97`, `baseline_window=365d` n=275 band=above. Selfcheck: fact_card / healthkit_ingest / compare_table / chat_turn_fsm / numerics / aggregator PASS.
- **Change**: scheme A. Migration script idempotent; aggregator writes leftover `hrv` samples into the SDNN bucket; zip import and ingest alias `hrv`→`hrv_sdnn`; registry primary metric becomes `hrv_sdnn_ms` (label HRV), `hrv_rmssd_ms` marked deprecated/not eligible; prefs auto remap; `health_data`/patient_state/compare/OCR snapshot compatible with old id. Deep/REM share reference still TODO.
- **Rollback**: restore code and registry; daily table can use backup or recompute from `wearable_data` (migration does not delete `hrv_rmssd_ms` history).

---

## 2026-09-07 (M1-P7 progressive personal baseline + generic reference layer)

- **Category**: fact-card rule assessment (no LLM).
- **Evidence**: `python3 scripts/pha_fact_card_selfcheck.py` PASS (including 90d empty→365d, no history `/7`, T1 reference three-state, HRV no reference, card-level synthesize / do-not-synthesize). Live `default`: sleep total `baseline_window=365d` n=267 band=typical, reference within; REM/awake band=below; `sleep_core` no history unknown; HRV/RHR that day no value missing (no backfill).
- **Change**: `fact_card.py` per-metric progressive 90d→365d→all; JSON writes `baseline_window` / `baseline_earliest`; copy “relative to your last 12 months N nights/days”; unknown writes “personal history n/7”; card-level synthesize requires sleep+HRV+RHR all selected and banded, else “do not synthesize”. Registry `reference_range` into sleep total / RHR / steps; T1 disclosure sentence; deep/REM share reference not this round (TODO). `load_fact_card` pulls full history. Share-type reference and HRV column merge still M1-P8.
- **Rollback**: restore `pha/fact_card.py` / `fact_card_prefs.py` / `fact_card_html.py` / registry three `reference_range` / selfcheck; official restart.

---

## 2026-09-07 (PRD v1.6: progressive baseline + generic reference layer + my assessment prompt + button interpretation; HRV column semantics; docs only)

- **Category**: product consensus / docs (no code).
- **Evidence**: full-card assessment layer only wrote “baseline insufficient”. Query `data/pha_storage.db` (`default`): `wearable_daily` 2016-09-26～2026-09-07 total 3504 rows; `sleep_hours` 642 nights (last 365 days 268, last 90 days **1**), `hrv_rmssd_ms` 1936 days (last 90 days **0**), `resting_heart_rate_bpm` 2255, `active_energy_kcal` 2286. `fact_card.py` `BASELINE_DAYS=90` looks back from as_of; zip data ends 2026-06-09, so everything falls outside the window. Also: `wearable_data` 11650 `metric_type=hrv` `sample_id`s are all `HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…|<Watch-name> Apple Watch` — the RMSSD column was Apple SDNN from the start. Maintainer: proactive agent and Mac PHA are not split; “baseline insufficient” does not hold; agreed “my assessment prompt (free text, for the LLM)”; M3 does not conflict with button interpretation.
- **Change**: PRD v1.6: §1.3 defines “proactive path”, §1.3a no split; FR-2.1 / FR-2.6 baseline window progressive 90d→365d→all + card discloses window and n, card-level synthesize three bands / “do not synthesize”; FR-2.8 generic reference layer (`manifest-tier-v1` T1 disclosure sentence, ranges in registry `fact_card.reference_range`, HRV absolute value gets no population range); FR-2.9 `assessment_prompt` save and echo; FR-6 user-triggered LLM interpretation (reuse `chat_service` harness + Numerics audit, async + cache by `(user, as_of, sha256(prompt))`, independent block, fail-closed, ban pre-generation/bare run); §3/§8 M3 becomes App wiring; open **M1-P7** (baseline+reference layer), **M1-P8** (HRV column semantics, stacked on harness ACK), **M1-P9** (assessment prompt+interpretation). Sync `pha-fact-card.md`, `pha-ios-proactive-roadmap.md`, `pha-healthkit-sleep-hrv.md` RMSSD row. New handoff `handoff-2026-09-07-fact-card-assessment.md`.
- **Rollback**: restore those docs to v1.5 copy; delete the handoff. No runtime impact.

---

## 2026-09-07 (T7 FR-1.7 sync receipt)

- **Category**: operability / ingest contract.
- **Evidence**: `python3 scripts/pha_healthkit_ingest_selfcheck.py` (including fail→success receipt + `GET /ingest/healthkit/last`); `python3 scripts/pha_fact_card_selfcheck.py`.
- **Change**: `pha/healthkit_ingest_receipt.py` writes `data/healthkit_ingest_last.json` (success/fail time, kind, error, compact audit, no body/token); both POST success and fail-closed write; `GET /ingest/healthkit/last?user_id=`; fact-card JSON `facts.ingest_last` + full-card top “last sync”.
- **Rollback**: remove the route and receipt write; restore fact_card HTML row.

---

## 2026-09-07 (M1-P6 gate: compare if present, empty if not; source of truth = Health app presentation)

- **Category**: product copy / docs (PRD v1.5).
- **Evidence**: after deleting recent-two-day Pillow, 15:41 POST 200; 9/7 asleep 7.60 / awake 3.45 / stages displayable, vs Health app ≤8 minutes; in-bed none on both Health app and PHA. Screenshots prove the earlier inflation came from Pillow+Watch dual track. “Show All Data” + Data Sources include Pillow / multiple Watches / iPhone.
- **Change**: FR-1.6, task-card gate, review §6: accept only items the Health app has and the user checked; ban hardcoding required sleep items (echoes FR-2.7); source of truth = Health app presentation; M1 single-source transition, multi-source priority alignment is M2. Update anchor A and drift table. No code.
- **Rollback**: restore PRD / task card / review / this entry to v1.4 copy.

---

## 2026-09-07 (T6.1 sleep D1 must carry a date predicate)

- **Category**: Shortcut capture window.
- **Evidence**: on-device two `pha-sync-sleep` runs (15:02 / 15:03, `<LAN-IP>`) both `POST 400 sleep_stage_list_mismatch`, body `---VALUES---` empty; maintainer confirmed the new Shortcut Health permission was on. A local Downloads `healthkit.json` is that 400. Conclusion: Health Find with only Type Sleep + Limit and no date condition returns an empty set (and still POSTs). `python3 scripts/pha_healthkit_ingest_selfcheck.py`. Quantity Shortcut unchanged.
- **Change**: D1 Find adds `Start Date is in the last 2 days` (Operator 1001 / Number 2 / Unit 16384), keeps Latest First + Limit 150. last 1 day with no Limit once crashed Get Details, so Limit cap stays. Source/Device untouched this round (change one place at a time).
- **Rollback**: remove the last-2-days predicate, or generate `variant=is_today`.

---

## 2026-09-07 (T6 sleep Shortcut D1: descending + Limit 150)

- **Category**: Shortcut capture window.
- **Evidence**: `python3 scripts/pha_healthkit_ingest_selfcheck.py` (including D1 plist: Limit 150, Latest First, no is today, no 9/6 anchor copy; `is today` alternate still has the original filter). Quantity Shortcut `_find_health` / `_get_detail` unchanged.
- **Change**: main Shortcut “PHA sync sleep” Find Sleep now Start Date latest first, Limit 150 (T0 one night 64 segments, 150 leaves headroom); Get Details tries Source/Device, writes optional `---SOURCES---` / `---DEVICES---` (length mismatch ignored, do not reject the whole night); Show Result dropped the hardcoded 9/6 anchor. Also generate `pha-sync-sleep-is-today.shortcut` as alternate. ingest parser extra segments so ENDS is not polluted.
- **Rollback**: generate back to `is today` edition (`variant=is_today`); restore `build_sleep` and `parse_sleep_bundle_text`.

---

## 2026-09-07 (T3 baseline-deviation check copy; T4 in-bed/session span; T5 same-day sleep daily-key cleanup)

- **Category**: fact-card copy + ingest in-bed rule + data hygiene.
- **Evidence**: `python3 scripts/pha_fact_card_selfcheck.py`; `python3 scripts/pha_healthkit_ingest_selfcheck.py`. Live 9/7 already asleep 7.483 / stages empty / awake 2.683 / in-bed empty (T1+T2).
- **Change**: when a sleep metric deviates from last-90-day quantile, notification and full card append the fixed “please check in the Health app” sentence (judgment words banned); `in_bed_hours` only from In Bed samples; derived `sleep_period_hours` not written into in-bed; efficiency written to audit only when in-bed exists; `in_bed<1h` and no stages → fact card shows “none”. After a sleep bundle succeeds, delete that wake day’s entire `healthkit|…|sleep_*` daily-key rows then recompute; maintainer script `scripts/pha_sleep_cleanup_day.py`.
- **Rollback**: restore `pha/fact_card.py`, `pha/models.py`, `pha/sqlite_storage.py`, `pha/wearable_daily_aggregator.py`, `pha/healthkit_ingest.py` then official restart; delete the cleanup script.

---

## 2026-09-07 (T1+T2 segment ledger + asleep total union + wake-day noon window)

- **Category**: ingest correctness.
- **Evidence**: selfcheck `python3 scripts/pha_healthkit_ingest_selfcheck.py` (including 9/6-style 6 segments ±0.02, audit line, segment-table idempotent, cross-stage `stage_overlap` blanks stage columns, 23:00–07:00 assigned to wake day, 23:30 tonight not mixed into last night, `stale_sleep_bundle`).
- **Change**: `PHA_SLEEP_V1` / `sleep_*` lists write `wearable_sleep_segments` (delete that wake day’s `healthkit|` segments first then insert); daily table recomputed from segments; asleep = one union of Core∪Deep∪REM∪Asleep; if Σ-stage union drifts >5% then `stage_overlap=true` and core/deep/REM written empty; wake day D = last sleep-segment end day, window `[D-1 12:00, D 12:00)`; D more than 1 day before receive day → 400 `stale_sleep_bundle`. zip segments still use original SUM deep/rem. Quantity Shortcut path unchanged.
- **Rollback**: restore `pha/healthkit_ingest.py`, `pha/sqlite_storage.py`, `pha/wearable_daily_aggregator.py`, `pha/sleep_aggregator.py` then official restart.

---

## 2026-09-07 (T0 replay closeout: cross-stage overlap caused 10.6h)

- **Category**: forensics.
- **Evidence**: 14:00:59 `<LAN-IP>` POST **200**, body landed in `data/local_shortcuts/sleep_body_2026-09-07.txt`. Daily table bit-identical to the previous two. Replay: asleep one-union 7.483h (Health app 7.717h, ~14m window gap); ingest 10.6h = summing per-stage unions. Cross-stage overlap 38 pairs / 2.1h; same-stage interleave over-counted core 1.633h; complete duplicates 0; deep union=sum=1.633 matches Health app.
- **Change**: review §2 records the T0 conclusion. No new code.
- **Rollback**: N/A.

---

## 2026-09-07 (T0 replay script; body on disk waiting for next POST)

- **Category**: ingest forensics (do not touch daily-table numbers).
- **Evidence**: 11:59 / 12:34 two 200 bodies were not fully logged (400 preview cut at `---STARTS---` first line; 200 did not log body). VALUES 64 segments: Core 27 / Awake 17 / REM 13 / Deep 7. Without STARTS/ENDS cannot locate the extra ≥1.3h on 13.28h.
- **Change**: `scripts/pha_sleep_bundle_replay.py` offline prints segments, same/cross-stage overlap, complete duplicates, per-stage sum vs union, asleep total union, session span. After `parse_sleep_bundle_text` succeeds, write the full text to gitignored `data/local_shortcuts/sleep_body_{day,latest,timestamp}.txt` (no token).
- **Rollback**: delete the script; remove `_persist_sleep_bundle_for_replay`.

---

## 2026-09-07 (12:34 second on-device 200, bit-identical result; awake definition frozen; docs only)

- **Category**: on-device acceptance + docs (no code).
- **Evidence**: `<LAN-IP>` 12:34:35 POST **200**, daily 9/7 bit-identical to 11:59:58 (asleep 10.6 / core 6.033 / deep 1.633 / REM 2.933 / awake 2.683 / in-bed empty). Double-count reproducible. Maintainer freeze: Health app has no “pre-asleep” concept; sleep starts at fall-asleep; core/REM/deep count as asleep; awake does not; 9/7 pre-asleep stretch treated as a capture special case.
- **Change**: withdraw the “awake three-way split” product-column proposal; `awake_duration_hours` = Health app raw value. 12:37 maintainer addendum: 9/7 session opened with a 4-minute Deep at 20:30 then ≈2.2h awake; App and Apple rules are both correct. 12:42 freeze: **PHA does not judge whether a night is a capture mistake, does not tag `collection_anomaly`-class labels, does not correct, does not exclude** (both tagging proposals voided); T3 becomes “sleep items enter the fact card’s existing personal 90-day baseline banding; on deviation add the fixed template ‘…clearly above/below your last-90-day level; please check this night in the Health app’”; copy bans judgment words. review §3/§4-E/§6/§7, task card, PRD FR-1.6 and §11/§12 synced.
- **Rollback**: restore docs.

---

## 2026-09-07 (Health app 9/7 ground truth in; T0–T9 task table; docs only)

- **Category**: docs / consensus (no code).
- **Evidence**: maintainer screenshot (12:23) Health app 9/7: in bed 8h57m, asleep 7h43m, awake 3h35m (about 20:30–22:45 one block ≈2.2h before fall-asleep), REM 1h6m, core 4h59m, deep 1h38m. Store same night: deep 1.633 exact match; REM 2.933 vs 1.10; core 6.033 vs 4.983; awake 2.683 (post-midnight true value ~1.4). Asleep+awake 11.30 ≠ in-bed 8.95.
- **Change**: review §2 records ground-truth comparison and inference (not uniform amplification → not simple dual-source; deep match → parse chain correct, problem is duplicate/overlap-segment dedupe); reject D3 “in-bed = session span”; review §7 becomes T0–T9 task table (forensics replay → segment ledger → total union/window → awake three-way split → in-bed rule → cleanup → Shortcut D1 → receipt → docs → three-night acceptance). Task-card anchor A=9/7, B=9/6, ban deriving in-bed. PRD §11 one more row.
- **Rollback**: restore the three docs.

---

## 2026-09-07 (12:13 rerun no POST; M1-P6 mid-course review, docs only)

- **Category**: docs / consensus (no code).
- **Evidence**: 12:13 maintainer rerun; after log line 2029128 no `POST /ingest/healthkit` at all; store still the 11:59:58 run. 9/7 asleep 10.6 + awake 2.68 = 13.3h > 12h window; stage overlap double-counted. Maintainer confirmed Health app 9/7 awake 3.35h includes ~2h before fall-asleep (Apple Awake definition).
- **Change**: added [`pha-sleep-ingest-review-2026-09-07.md`](pha-sleep-ingest-review-2026-09-07.md) (error list A–I, plan, done gate, encoding order). Task card [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md): wake day derived from data, noon window, asleep = one union + `stage_overlap`, awake three-way split, segment ledger + audit line, validation grain, current implementation drift table, Shortcut candidates D1/D3, leftover cleanup, done gate. PRD v1.4: FR-1.6 acceptance refined, new FR-1.7 sync receipt, M1-P6 row, §11 three rows, §12.
- **Rollback**: restore those three docs; no runtime impact.

---

## 2026-09-07 (sleep on-device 200; daily has numbers, not yet matched to Health app)

- **Category**: on-device acceptance.
- **Evidence**: `<LAN-IP>` `POST /ingest/healthkit` **200**, `received_at=2026-09-07T11:59:58`. Daily 9/7: `sleep_hours=10.6`, `sleep_core=6.033`, `sleep_deep=1.633`, `sleep_rem=2.933`, `awake=2.683`, `in_bed` empty. Core+deep+REM=asleep holds. `in_bed` empty matches `is today` dropping pre-midnight In Bed. 10.6h asleep is long, possibly multi-source stage overlap; **not** reconciled to Health app 9/7 wake day; M1-P6 not marked DONE.
- **Change**: no new code; record this 200.
- **Rollback**: N/A.

---

## 2026-09-07 (sleep POST through; zero-duration segments reject the batch)

- **Category**: ingest parse.
- **Evidence**: second on-device POST dates parsed, 400 `implausible_sleep_hours` (reject at list pairing, not seconds→hours). Daily still no 9/7. When Shortcuts dates are minute-precise, short segments become end==start; old logic fail-closed the whole night.
- **Change**: skip 0–2 minute reverse/zero-duration segments; same-stage overlap interval-unioned; reverse >2 minutes still 400. Selfcheck `test_sleep_zero_duration_skipped_and_overlap_unioned` PASS.
- **Rollback**: restore `pha/healthkit_ingest.py` `sleep_stage_hour_samples_from_lists`, then official restart.

---

## 2026-09-07 (sleep POST through; date narrow space)

- **Category**: ingest parse.
- **Evidence**: 11:5x `PHA_SLEEP_V1` reached Mac, 400 `unreadable_timestamp:7 Sep 2026 at 12:01 AM` (`\\u202f`). Stage labels are `Core/Deep/REM/Awake`. Daily not written for 9/7.
- **Change**: `safe_parse_datetime` first folds narrow space into ordinary space, then parses locale-independent Shortcuts `d Mon YYYY at h:mm AM`. Selfcheck `test_shortcut_sleep_date_format` PASS; `bash scripts/pha_restart_accept.sh` PASS.
- **Rollback**: restore `pha/date_parser.py`, then official restart.

---

## 2026-09-07 (sleep upload interrupted again; revert to is today)

- **Category**: Shortcut.
- **Evidence**: probe edition `is today` 6 samples ran; adding last 1 day + Get Details + POST again *problem running*, no new POST. When Sleep samples pile up, Get Details / Quick Look crash (known Shortcuts issue).
- **Change**: Find back to the already-working `Start Date is today`. After taking Value/Start/End, only Show text. Get Details writes both `WFInput` and `Input`.
- **Rollback**: restore `build_sleep` Find row.

---

## 2026-09-07 (sleep probe passed, attach upload)

- **Category**: Shortcut.
- **Evidence**: on-device Find `Type is Sleep` + `is today` ran, popped at least 6 Health samples. No `"ok": true` because the probe edition deliberately does not POST; Show of Health objects becomes a list picker, not JSON.
- **Change**: Find → last 1 day (cover last night’s pre-midnight fall-asleep). Take Value / Start Date / End Date into `PHA_SLEEP_V1` text then File POST. Show Result only text and server JSON.
- **Rollback**: restore `build_sleep` to two-step probe.

---

## 2026-09-06 (sleep Shortcut shrunk to probe)

- **Category**: Shortcut.
- **Evidence**: File text-body edition still no POST, same *problem running*. Comment / Get Details / JSON body can all be unconnected parameters.
- **Change**: keep only the same Find XML as the quantity Shortcut (`Type is Sleep` + `Start Date is today`) and Show Result. First confirm Find can run.
- **Rollback**: next step add Get Details and POST again.

---

## 2026-09-06 (sleep back to File text body)

- **Category**: ingest + Shortcut.
- **Evidence**: list-edition JSON body no new POST, still *problem running*. Same class as Count: homemade JSON fields not wired.
- **Change**: POST back to the already-working Text → File. Body `PHA_SLEEP_V1` + VALUES/STARTS/ENDS. Editor top has comment “PHA睡眠列表版”.
- **Rollback**: restore `build_sleep` and `parse_sleep_bundle_text`.

---

## 2026-09-06 (sleep switched to list ingest)

- **Category**: ingest + Shortcut.
- **Evidence**: 19:41 first `sleep_in_bed=0.727` then the Shortcut aborted. Editor Value still `anything`; homemade stage filters report *problem running* immediately.
- **Change**: Shortcut only Find `Type is Sleep` + last 2 days, take Value / Start Date / End Date each as a list POST. Server pairs, keeps only segments overlapping the last 24 hours, sums by stage. Ban generating Value enum rows or Count again.
- **Rollback**: restore `build_sleep` and `parse_ingest_payload` sleep_* list branch.

---

## 2026-09-06 (sleep Shortcut cannot run)

- **Category**: Telemetry → Shortcut.
- **Evidence**: new Shortcut popped *There was a problem running the shortcut*; Mac no new POST. Editor: `Start Date is in the last 1` already in effect, but Count showed `Count Items in Input`, Value showed `anything`.
- **Change**: drop homemade Count (unconnected required Input aborts immediately). Value enum add `Unit: 4` so import does not become anything.
- **Rollback**: restore `_find_sleep` Value row; do not put Count back.

---

## 2026-09-06 (sleep three empty values; date Unit)

- **Category**: Telemetry → Shortcut.
- **Evidence**: 19:29 five `sleep_*` still `value=""` 400. Daily 9/6 sleep columns all empty. Health app: in bed 8.6 / asleep 6.75 / core 4.6 / deep 0.55 / REM 1.6 / awake 1.85. In Bed / Awake labels already correct still empty; main cause `Operator 2` + homemade Date token.
- **Change**: Find date → `Operator 1001` + `Number 1` + `Unit 16384` (is in the last 1 day). Stage labels stay ActionKit: `Asleep Core/Deep/REM`.
- **Rollback**: restore `_find_sleep` date row.

---

## 2026-09-06 (sleep Shortcut empty value)

- **Category**: Telemetry → Shortcut.
- **Evidence**: five `sleep_*` POST `value=""` 400; Health app 9/6 in bed 8h36m / asleep 6h45m not ingested.
- **Change**: window → Start Date after now-24h; Duration Sum then ÷3600. ingest folds seconds in (16, 57600] into hours.
- **Rollback**: restore `_find_sleep` / `_sync_one_sleep_stage` / `_as_sleep_hours`.

---

## 2026-09-06 (M1-P6 sleep-stage Shortcut)

- **Category**: ingest / registry / Shortcut.
- **Change**: daily columns `sleep_core_hours` / `in_bed_hours`; ingest `sleep_core|deep|rem|in_bed|awake`; asleep hours = core+deep+REM. Independent Shortcut “PHA sync sleep”, Find Sleep stage Duration÷3600, window yesterday-noon–today-noon. Quantity Shortcut unchanged.
- **Rollback**: remove the sleep Shortcut task and new ingest keys; daily columns may stay empty.

---

## 2026-09-06 (on-device HRV SDNN ingest)

- **Category**: Telemetry.
- **Evidence**: 19:09–19:10 three `POST /ingest/healthkit` 200; `healthkit|default|hrv_sdnn|2026-09-06` = **40.968**; daily `hrv_sdnn_ms=40.968`, `hrv_rmssd_ms` empty; active energy updated to 703.626, rhr=60.
- **Change**: no code. HRV then-current daily-mean on-device cut done; sleep still not.
- **Rollback**: none.

---

## 2026-09-06 (M1-P6 first cut: HRV SDNN then-current daily mean)

- **Category**: ingest / registry / fact card / Shortcut.
- **Change**: new daily column `hrv_sdnn_ms`; `POST hrv_sdnn` and HK SDNN aliases write only that column. If `hrv_rmssd_ms` is checked, Shortcut Find `Heart Rate Variability` Average. Fact card shows HRV (SDNN) when RMSSD is empty; baselines are not mixed. Sleep Shortcut still not this cut.
- **Rollback**: remove registry `hrv_sdnn_ms` row and ingest `hrv_sdnn`; daily column may stay empty.

---

## 2026-09-06 (on-device active energy ingest)

- **Category**: Telemetry.
- **Evidence**: 18:58 two `POST /ingest/healthkit` 200; `healthkit|default|active_energy|2026-09-06` = **701.69**; same-day rhr=60. Daily `2026-09-06`: `active_energy_kcal=701.69`, `resting_heart_rate_bpm=60`.
- **Change**: no code. M1-P5 quantity types marked DONE on this.
- **Rollback**: none.

---

## 2026-09-06 (active energy Find label wrong: Active Energy ≠ Active Calories)

- **Category**: Telemetry → registry / Shortcut.
- **Evidence**: Health→Shortcuts only Resting Heart Rate, Steps; running the Shortcut reported No Samples Found / Active Energy; same run RHR 60 ingested 200. Permission lists never show a type that was never correctly requested.
- **Change**: `shortcut_health_type` → Find selector label `Active Calories`. M1-P6 records “then-current daily mean” semantics (run after waking = Average of SDNN already present that day).
- **Rollback**: put the registry field back to `Active Energy`.

---

## 2026-09-06 (active energy empty value; sleep/HRV open M1-P6)

- **Category**: Telemetry → Shortcut / new task card.
- **Evidence**: 18:29 active energy POST `value=""` three times 400; same run RHR 59 ingested.
- **Change**: Find no longer adds kcal unit to Active Energy; after Statistics, Detect Number then write JSON. Sleep/HRV full-item analysis moved to [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md) (M1-P6).
- **Rollback**: restore `_find_health` / `_sync_one_metric`.

---

## 2026-09-06 (sync never entered the store: Health app ≠ PHA ledger)

- **Category**: Telemetry / Shortcut robustness.
- **Evidence**: full card 5 items all none; `default` healthkit rows only 9/4, 9/5 steps; while the full card was open the log had only GET view/prefs, **zero** `POST /ingest/healthkit`.
- **Change**: full card discloses the latest HealthKit ingest. Shortcut back to the already-working Find→sum→POST (drop the bad Count/If); Find writes `WFHealthActionUnit` (kcal / count/min).
- **Rollback**: restore Shortcut generator and `facts.healthkit` disclosure.

---

## 2026-09-06 (M1-P5 multi-metric ingest: steps / energy / resting HR)

- **Category**: ingest Shortcut / registry / PRD FR-1.5.
- **Root cause**: full card can be checked, but production Shortcut only POSTed steps; assessment coverage honestly low.
- **Change**: `fact_card.shortcut_health_type` + user-selected → generate “PHA sync health”; each item Find today’s quantity → Sum/Average → **POST only one number**. `daily_key` ingest UPSERT by calendar day. Sleep (category) and HRV (SDNN≠RMSSD) write `shortcut_skip_reason`, do not sync, do not invent numbers.
- **Rollback**: restore Shortcut generator and `healthkit_ingest.daily_key_stored_types`; remove registry shortcut fields.

---

## 2026-09-06 (M1-P3/P4 full card tappable + user-selected metrics)

- **Category**: PRD v1.3 / fact-card reach / anti-hardcode.
- **Root cause**: iOS “Show Notification” lock-screen truncates long body, and Shortcut notifications have no custom tap deep link; five items hardcoded in `pha/fact_card.py`, violating constitution “no defensive hardcoding”.
- **Change**: lock screen keeps only a short lead-in + `open_path`; `GET /proactive/fact-card/view` renders the full list and assessment; Shortcut does “URL” then “Open URL” (writing `WFURL` directly is ignored; iPhone reports “no URL”). Allowed metric set moves to `wearable_metric_registry.json` `fact_card`; user checkboxes land in `data/fact_card_prefs.json`. Multi-metric ingest opened as **M1-P5** (see roadmap); this cut does not invent numbers not yet ingested.
- **Rollback**: restore `fact_card.py` / `fact_card_api.py` / Shortcut generator; remove `fact_card_prefs.py` / `fact_card_html.py`.

---

## 2026-09-06 (M1-P2 notification content contract: five items + card-level assessment)

- **Category**: fact-card template / PRD v1.2.
- **Root cause**: first-edition notification only concatenated “first 3 items that have a value”; when the store only had steps the user saw one number; the assessment layer was not delivered.
- **Change**: body always enumerates FR-1.4 five items (write “none” if no value); `assessment.summary` (coverage / stale / baseline band) + one advice sentence. Analysis is not LLM.
- **Rollback**: restore `pha/fact_card.py` notification assembly.

---

## 2026-09-06 (M1-P1 on-device: iPhone received the fact-card notification)

- **Category**: proactive-channel acceptance.
- **Evidence**: `pha-8788.log` showed `<LAN-IP> GET /proactive/fact-card?user_id=default 200` (not 127.0.0.1); maintainer confirmed the phone popped a notification.
- **Card at the time**: calendar 2026-09-06, `as_of=2026-09-05`, `stale=true`, steps 14872, baseline n&lt;7 no banding. No code change.

---

## 2026-09-06 (M1 start · fact card two layers + iPhone local notification channel)

- **Category**: PRD v1.1 + no-LLM fact-card engine + GET.
- **Product**: proactive channel frozen as **iPhone Shortcut local notification** (not Mac notification, not APNs, not LLM assessment). Card splits `facts` / `assessment`. From v1.2 the notification must have five items + card-level assessment.
- **Code**: `pha/fact_card.py` (point-day missing row not backfilled; `as_of=MAX(day)` + stale); `GET /proactive/fact-card` (same ingest token); Shortcut “PHA fact-card notification”.
- **Rollback**: remove `fact_card.py` / `fact_card_api.py` and the `main.py` include_router.

---

## 2026-09-05 (today slot bound to daily table · Hero no longer tops today with last-with-data)

- **Category**: time-slot → daily-table bind (chat and dashboard share one rule).
- **Root cause**: Hero “today’s steps” read `rows[-1]` of a last-7-day window, labeling “the last day in the window that had a number” as today. Same class of error as Q&A once ignoring the time slot; not a missing `if day == today`.
- **Change**: `pha/wearable_daily_bind.py` — point-day grain takes only that calendar day, missing row → empty; 7-day mean averages only rows inside the grain. `dashboard_api.hero_stats` and Patient State “today’s steps” share the same bind.
- **Rollback**: remove `wearable_daily_bind.py`, restore `dashboard_api.py` / `patient_state.py`.

---

## 2026-09-04 (WIP snapshot · already merged into this PR)

- **Git**: maintainer decided **one local commit + push after everything is done**. Current workspace uncommitted vs `origin/main` (including M0 ingest, daily UPSERT, time slot, skip empty-window reject). **Do not** read this snapshot as `packages/harness_core` already changed; core is still the Plan → Compose → Post-Audit set gate.
- **Already running locally (not pushed)**
  - M0-P0/P1: `POST /ingest/healthkit`; on-device today’s steps ingested **11259** (`healthkit|default|steps|2026-09-04|healthkit`).
  - M0-P2 daily: same-day UPSERT; zip preserves `healthkit|` rows.
  - skip-LLM: “today’s steps” → **today’s steps 11259**, no longer the 90-day mean.
  - Time slot: `pha/wearable_time_grain.py` (point-day / week / month / `过去N天`); empty window skip says no record, does not hand the pen to the LLM.
- **Known on-device gaps (data, not code)**
  - `wearable_daily` has no 2026-09-03: yesterday had no HealthKit row. Before the fix the LLM had written **2019-09-26’s 14808** as last night.
  - Last-7-day window often has only the 9/4 row, so the mean equals today (n=1) unless those days are synced too.
- **Code not finished (next cut, commit after done)**
  - ~~If the LLM bypasses skip: C layer still almost only audits lab decimals~~ **already patched (local, uncommitted)**: under non-default time grain, integer step counts ≥100 in the draft must ∈ this window’s T0; else `unauthorized_wearable_count`; warn mode also replaced with “no record, do not top with another date”. `packages/harness_core` still unchanged.
  - Awaiting your acceptance: yesterday-with-no-row no longer shows 14808; today’s 11259 still citable. After pass, one commit + push.
- **Do not**: M1 proactive push; change public README narrative; `git commit` / `git push` before “please commit”.

---

## 2026-09-04 (time anchor bound to the evidence window)

- **Category**: Q&A number-reading (Harness time slot, not a “today” special case).
- **Root cause**: 1E-a requires `TIME_ANCHOR_TOKENS` (today/yesterday/this week/last 7 days…) must not enter catalog aliases; they are only a Tier-C time slot. Catalog correctly stripped “today” leaving “how many steps” → steps; **no layer bound that time slot to a wearable window**. skip-LLM / Numerics default last-90-day mean, so “today” vanished from the answer.
- **Change**: `pha/wearable_time_grain.py` parses the window with the same time-anchor set (point-day / week / month / rolling days); `default_wearable_window` shared with HealthTurnResolver; skip-LLM rebuilds the manifest on non-default grain, forbids reusing the 90-day mean. Broad “what about steps”, screenshot “vs last week” still take default 90 days.
- **Rolling days**: `过去N天` / `近N天` / `last N days` are the same duration class, not another “last 7 days” special case. Empty-window skip-LLM says no record directly; the LLM must not fill numbers from another date.
- **Rollback**: remove `wearable_time_grain.py`, restore `date_range_parser` / `health_turn_resolver` / `grounded_answer_composer`.

---

## 2026-09-04 (M0-P2 daily-table align + skip-LLM readable)

- **Category**: ingest daily key, zip conflict, Q&A number-reading.
- **Steps**: one `sample_id` per calendar day; same-day repeat sync UPSERT, do not sum multiple POSTs. Before write, drop same-day old timestamp-key healthkit rows.
- **zip full import**: `clear_wearable_storage(..., preserve_healthkit=True)`, then `rebuild_wearable_daily_for_days` including healthkit days (max-by-source).
- **skip-LLM**: selfcheck “recent steps” must show the healthkit daily number.
- **Shortcut**: Find → Get Details Value → Get Numbers → Statistics Sum; JSON **carries only the summed number**. If steps accidentally carry “sum + per-sample newlines”, server first folds newlines into legal JSON then uses the leading sum (avoid adding twice).
- **Rollback**: restore `healthkit_ingest.py` / `sqlite_storage.py` / `data_importer.py` / `store.py` and the Shortcut generator script.

---

## 2026-09-04 (M0-P1 ingest value coerce + shortcut number)

- **Category**: ingest parse + local Shortcut artifact.
- **Reason**: iPhone `POST /ingest/healthkit` already through (not 401/422), but `value` was still a Health Quantity / empty-object placeholder, 400 `unreadable_value`, store had no `healthkit|default|`.
- **Server**: `_finite_number` accepts `16 count`, Magnitude dict; 400 response carries `got`; log prints body preview. Empty value still fail-closed, does not invent steps. `GET /ingest/healthkit` returns an explanation JSON (browser open is no longer a blunt 405).
- **Shortcut**: today’s steps **Statistics Sum** then POST only one number (avoid iOS “share 329 health data items”).
- **Rollback**: restore `pha/healthkit_ingest.py` and `scripts/macos/build_pha_ingest_shortcuts.py`, then `bash scripts/pha_restart_accept.sh`.

---

## 2026-09-02 (M0-P1 local bind + shortcut files)

- **Category**: local run config (`.env` gitignored) + Shortcut artifacts (`data/local_shortcuts/` gitignored).
- **PHA_HOST**: local changed to `0.0.0.0`, via `pha_restart_accept.sh` / launchd kickstart; repo default remains `127.0.0.1`.
- **Acceptance**: LAN `http://<LAN-IP>:8788/ingest/healthkit` fixture 200; no token 401.
- **Shortcut**: `scripts/macos/build_pha_ingest_shortcuts.py` default writes `$(scutil --get LocalHostName).local`, avoiding timeout after DHCP changes the IP. Health Shortcut **only** `Find Health Samples` type `Steps`. value quoted in JSON; server folds `"16 count"` into a number.
- **Rollback**: `.env` back to `PHA_HOST=127.0.0.1` then `bash scripts/pha_restart_accept.sh`.

---

## 2026-08-31 (M0-P0 ingest)

- **Category**: production code (HealthKit JSON → SQLite).
- **Route**: `POST /ingest/healthkit` (`pha/healthkit_ingest.py`).
- **Auth**: `PHA_INGEST_TOKEN`; Header `X-PHA-Ingest-Token` or body `token`; unconfigured 503, wrong token 401.
- **Timezone**: `PHA_INGEST_TZ` default `Asia/Shanghai`; timestamp converted to naive local time; daily table uses `substr(timestamp,1,10)`.
- **Whitelist**: `hrv` / `rhr` / `steps` / `sleep_hours` / `active_energy` (`sleep_hours` stored as `metric_type=sleep`). Unknown metrics drop the sample, do not invent; unparsable timestamp/value → whole batch 400, no write.
- **Idempotency**: `sample_id = healthkit|{user}|{metric}|{local_iso}|healthkit` (v1 has no source column; source is encoded in sample_id).
- **Daily table**: after write `rebuild_wearable_daily_for_days`. rebuild skips noon daily-mirror rows, avoiding same-day multiple ingest adding `active_energy` twice.
- **Selfcheck**: `scripts/pha_healthkit_ingest_selfcheck.py` (temp DB, does not touch `data/pha_storage.db`).
- **Rollback**: remove the ingest router from `main.py`; delete `pha/healthkit_ingest.py`.

---

## 2026-08-31 (PRD v1.0 ratified)

- **Category**: product consensus (no production code yet).
- **Source of truth**: `docs/prd-pha-ios-proactive-agent-v1.md`.
- **First cut**: HealthKit → Mac `wearable_daily` (M0-P0/P1).
- **Iron rules**: proactive path has no LLM filling numbers; not medical advice; data does not leave the user’s device circle.

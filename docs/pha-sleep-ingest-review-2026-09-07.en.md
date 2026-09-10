# Sleep ingest review · 2026-09-07 (M1-P6 mid-course recap)

> **Language / 语言**：English (this document) · [中文](pha-sleep-ingest-review-2026-09-07.md)

> Kind: recap + design, **no code changes**. For other reviewers to check against.  
> Upstream: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) §FR-1.6 / M1-P6; task card [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md)  
> Evidence: `data/pha_storage.db`, `~/Library/Logs/pha/pha-8788.log`, maintainer oral (Health app 9/7 awake 3.35h)  
> **Closeout (2026-09-10)**: T9 maintainer orally confirmed 9/8–9/10 largely matches; M1-P6 → DONE. §0 below still keeps the recap as written then.

---

## 0. One-sentence conclusion

The sleep pipe **runs but does not match**: the Shortcut can finish and POST; the server can parse and write the daily table; but the numbers written are “union each stage separately then add”, which in the 9/7 12-hour window produced **asleep 10.6h + awake 2.68h = 13.3h**, physically impossible — stage segments overlap and were double-counted. Apple’s “Awake” also includes in-bed time before sleep onset (maintainer confirmed ~2h on 9/7); we did not split that, so once the fact card shows it, “lying awake before sleep” becomes “awake during the night”. **M1-P6 cannot be marked DONE.**

---

## 1. Today’s on-device timeline (evidence)

| Time (local) | Event | Server result |
|---|---|---|
| 11:5x | 1st `PHA_SLEEP_V1` POST | **400** `unreadable_timestamp:7 Sep 2026 at 12:01 AM` (narrow space `\u202f` before AM) |
| ~11:57 | 2nd | **400** `implausible_sleep_hours` (a segment end==start; Shortcuts dates only to the minute; old logic rejected the whole night) |
| 11:59:58 | 3rd | **200**, 4 daily-key rows written for 9/7 |
| ~12:13 | Maintainer said “ran it again” | **Mac saw no new POST** (after log line 2029128 only local GETs). Phone either errored out, never reached “Get Contents of URL”, or was not on the same network |

The 12:13 run never reached the server; 9/7 in the DB is still the 11:59:58 result. If the phone’s “server:” line is empty or an error, that is why.

## 2. 9/7 daily table vs Health app (screenshot 12:23, wake day Sep 7)

Health app truth (screenshot): in bed **8h57m**, asleep **7h43m**, awake **3h35m**, REM **1h6m**, core **4h59m**, deep **1h38m**. Timeline 7 PM → 7 AM+: **about 20:30–22:45 one awake block (≈2.2h, in bed before sleep)**, sleep onset 22:45, last awake about 08:30–08:45.

| Item | Health app 9/7 | Ledger (9/7, Shortcut window 00:00–11:59) | Diff | Judgment |
|---|---|---|---|---|
| Core | 4.983h | 6.033h | **+1.05h** | Ledger window narrower yet larger → double-count |
| Deep | 1.633h | 1.633h | 0 | Exact match (stage parse itself is fine) |
| REM | 1.100h | 2.933h | **+1.83h** | Nearly 3× → double-count |
| Asleep (core+deep+REM) | 7.717h | 10.600h | **+2.88h** | ~1.2h of pre-midnight sleep not even in yet, so actual inflation is larger |
| Awake | 3.583h (includes pre-sleep ≈2.2h) | 2.683h | −0.90h | True post-midnight awake ~1.4h; ledger also inflated ~1.3h |
| In bed | 8.950h | empty | — | `is today` cannot get In Bed |

Health app identity: core+deep+REM = 7.716 = asleep ✓. **Asleep + awake = 11.30h ≠ in bed 8.95h**, gap 2.35h ≈ the pre-sleep awake block + post-wake tail. That is: Apple’s **Time in Bed does not include that pre-sleep block, but Awake does**. In-bed = asleep + awake on the 9/6 anchor was coincidence (short sleep latency that night). **Do not treat “in bed = session span” as a rule** (this document’s v1 D3 was corrected for that).

**Hard contradiction**: ledger asleep 10.60 + awake 2.68 = **13.28h** > 12h window; vs truth, inflation concentrates in REM (×2.7) and core (+20%); deep is exact; awake also inflated. **Non-uniform scale-up → not simply “two sources each wrote a copy”** (that would ×2 every stage). Candidate sources (need segment-level evidence to decide):

1. A source/period’s stage segments were fetched twice with a slight time offset (same-stage union cannot drop them);
2. A third-party app or second device wrote some stages (only some periods, some labels);
3. Shortcuts `Get Details` three lists have occasional element misalignment (same Find same order, low probability, not excluded).

The server currently writes only totals, not segments, and does not emit an audit line on success, so **there is no evidence to distinguish those three**. That is this review’s largest design gap (§4-B). Good news: **deep is exact**, so date parse, stage-label fold, and window clip are themselves correct; the problem converges on “deduping duplicate/overlapping segments”.

**T0 conclusion (2026-09-07 14:00 body replay, one sentence)**: daily-table asleep 10.6h = sum of per-stage unions (core 6.033 + deep 1.633 + REM 2.933); the same instant labeled as two stages (38 cross-stage overlap pairs, totaling 2.1h) plus same-stage staggered overlap (core extra 1.633h, REM 0.200h, awake 0.383h). **Asleep one-shot total union is only 7.483h**, ~14 minutes off Health app 7.717h (`is today` dropped pre-midnight). Fully duplicate segments 0; deep has no same-stage overlap, so 1.633 matches Health app digit-for-digit.

Replay detail (`scripts/pha_sleep_bundle_replay.py`, `--now 2026-09-07T14:00:59`, 24h window):

| | Segments | Sum | This-stage union | Union − Health app |
|---|---|---|---|---|
| Core | 27 | 7.667 | **6.033** (ingested) | +1.05 |
| Deep | 7 | 1.633 | **1.633** (ingested) | 0 |
| REM | 12 | 3.133 | **2.933** (ingested) | +1.83 |
| Awake | 14 | 3.067 | **2.683** (ingested) | −0.90 (~2.2h pre-midnight not in window) |
| Asleep Σ unions | | | **10.600** (ingested) | +2.88 |
| Asleep one-shot total union | | | **7.483** | **−0.23** (~14m, window gap) |

64 segments, skip 4 zero-duration (minute rounding), no In Bed. Session span 00:01–08:05 = 8.067h = asleep∪awake union. Largest cross-stage overlap: 04:53 Core vs REM 41 minutes (idx 42+43).

Side evidence: zip era (2026-06) this user’s daily asleep 6.7–10.0h, awake 0.8–4.1h, same magnitude as 9/7 truth.

## 3. How “2 hours before sleep counted as awake” happens

This is not a PHA bug and not a Health app bug; it is **Apple’s definition of Awake**:

- Watch sleep session starts at “Sleep Focus on / scheduled bedtime reached / in-bed detected”;
- Time in the session not classified as any sleep stage = **Awake**;
- So “in bed 20:30, actually asleep 22:45” → 20:30–22:45 recorded as awake ≈2.2h. The 9/7 screenshot is exactly that: of Awake 3h35m a whole block is before sleep onset, while Time in Bed 8h57m **did not** include it (asleep 7.72 + awake 3.58 = 11.30 ≠ 8.95).

Maintainer-side check: Health → Sleep → full schedule bedtime earlier than actual onset; or Sleep Focus turned on early (phone/book in bed). This does not change PHA’s correctness requirement: PHA must accept Apple’s awake total as-is, but must split the naming.

**Maintainer contract (2026-09-07 12:34 / 12:37, overrides this document’s v1 “three-way split” proposal)**: Health app has no “pre-sleep” concept or data; sleep starts at sleep onset; core/REM/deep count as asleep; awake does not. The 9/7 session started from **a ~4-minute Deep around 20:30** (thin line at the left of the Deep row in the screenshot), then ≈2.2h awake, real onset 22:45. Under Apple’s rule “after session start, not asleep = awake”, **the App is correct and the rule is correct**; what is wrong is those 4 minutes of deep itself (watch misclassify) — a **collection error**; do not invent a product field for it.

**Maintainer addendum (12:42)**: PHA need not find collection mistakes and correct them; the user can correct them. Human sleep data is wildly variable; **PHA cannot judge whether a given night is anomalous**, and must not tag a night as “collection error” or exclude it from baseline. What PHA can and should do: **when data diverges from the user’s history, proactively remind “data differs from usual, please check”** — the user may not know the data is odd or what it means; that is why a proactive health-reminder agent exists.

PHA-side rules from that:

- All sleep columns = Health app original values (asleep = core ∪ deep ∪ REM one-shot total union; awake as-is; in bed only from In Bed samples); no split, no delete, no rewrite, no exclude.
- No new derived product columns; **no `collection_anomaly`-style judgment tags** (earlier two versions of this proposal are void).
- Fact card treats sleep items with the same existing mechanism as steps/HRV: vs personal last-90-day baseline (band only if n ≥ 7). **When off baseline, notification copy adds one fixed template**: “Awake 3.6h, clearly above your last 90 days; please check this night in the Health app”. Reminder to check, not an assertion of error; if the user edits in Health, the next sync naturally overwrites (daily-key UPSERT).
- A night like 9/7 will fire that reminder; PHA stops there and does not judge further.

## 4. Error list and solutions (by severity)

### A. Cross-stage overlap double-counted (data correctness · highest)

- **Today**: `sleep_stage_hour_samples_from_lists` unions each stage then adds. Overlap between stages is not deduped.
- **Correct rule**: total asleep = **one-shot total union of all sleep-stage segments (Core/Deep/REM/Asleep)**; per-stage hours are only meaningful under “single source, mutually exclusive”.
- **Plan**:
  1. After segment persist (§B), asleep total union reuses zip path’s existing `compute_sleep_hours_union` (including Watch > iPhone > other source priority).
  2. If `Σ stages` vs `total union` differ by > 5%, response and log `stage_overlap=true`; per-stage columns **not written** (NULL); only write asleep total union; fact card shows “stages overlap, not trusted” for stages. Prefer missing over wrong.
  3. Shortcut also fetches `Source`/`Device` (whether Get Details provides them needs on-device confirm); if source exists, keep only one source’s stages by priority.
- **Acceptance**: every ingest, `asleep + awake ≤ session span ≤ collection window length`; selfcheck adds a “two-source overlapping stages” case.

### B. Totals only, no segments, success leaves no audit (traceability · high)

- **Today**: `PHA_SLEEP_V1` parses then sums straight into daily-key rows; success logs only four “empty timestamp; using received_at” lines; reject preview 400 characters (today widened to 8000, still unstructured). Answering “where did 13.3h come from” currently has **no data**.
- **Plan**:
  1. Write segments into existing `wearable_sleep_segments` (columns: `day,start_time,end_time,source_name,sample_id,is_awake`); `sample_id` = `healthkit|{user}|{stage}|{start}|{end}|{source}`, idempotent; stage name in `sample_id` segment 4 so `sleep_stage_kind_from_sample_id` reuses.
  2. Daily table fully recomputed from segments (zip path already has `sleep_metrics_from_segment_rows`); no longer write “stage hours” daily-key rows directly. Old `sleep_core/…` daily-key POST path kept for compat, but same day with segments prefers segments.
  3. Success response and log one structured audit line: `kept / skipped_zero / dropped_unknown_label / per_stage_h / union_asleep_h / session_span / window / stage_overlap`. Phone “Show Result” displays that line as-is so the maintainer can compare to Health on the spot.
- **Rollback**: segment table already exists; no new schema; disable by not writing the table.

### C. Window-rule contract drift (contract drift · high)

Three places, three wordings:

| Location | Contract |
|---|---|
| Task card “overnight rule” | Wake-day D sleep = segments intersecting `[D-1 12:00, D 12:00)`; **forbid** using only `is today` |
| Server | Segments overlapping `received_at` minus 24h; daily key = `received_at` calendar day |
| Shortcut | `Start Date is today` (everything before midnight dropped) |
| PRD M1-P6 row | “yesterday-noon–today-noon window” “pending on-device Allow Access” (both stale) |

- **Plan**: task-card contract is the only spec; change the two implementation contracts (next encode step):
  - Server: **wake day D derived from data** (= calendar day of last sleep-stage end); keep only segments in `[D-1 12:00, D 12:00)`; if derived D is more than 1 calendar day earlier than `received_at` calendar day, return `stale_sleep_bundle` so the user knows they got an old night.
  - Shortcut: see §D.
- This round already made PRD/task card consistent (see change list at end).

### D. Collection window: `is today` drops pre-midnight; `last 1 day` crashes (collection reliability · high)

- **Today**: `last 1 day` + Get Details *problem running* on device (known Shortcuts large-list issue); `is today` runs but drops pre-midnight In Bed and stages; 9/7 awake short by 0.67h.
- **Candidates (try one at a time; write into the card only after on-device verify)**:

| Option | How | Pros | Risk |
|---|---|---|---|
| **D1 (try first)** | Find Sleep, Start Date **descending**, **Limit ≈ 150** | Bounded size will not crash; last night is first | One night 60–100 stage segments + Awake; 150 may clip night start; tune to on-device segment count |
| **D2** | Two Finds: `Start Date is yesterday` + `is today`, each Get Details, merge bodies | Reuses working XML | yesterday includes previous night’s tail + In Bed; list may again be large enough to crash |
| ~~D3~~ **rejected** | Derive in bed = session span | — | 9/7 truth: in bed 8.95 ≠ asleep+awake 11.30. Apple In Bed excludes the pre-sleep block. **In bed can only come from In Bed samples**; if missing, write empty; add derived column `sleep_period_h` (first sleep start → last sleep end), not written into in bed |
| D4 | `Start Date is in the last N hours` | Unit only | Crash is volume not unit; expected no improvement |
| D5 | M2 App uses `HKSampleQuery` directly | Root fix | Not in M1 |

- **Suggested combo**: D1 + §C server window; In Bed fetched with D1 (naturally inside Limit). If D1 fails, fall back to D2.

### E. Off-baseline does not remind the user to check (product value · medium; finalized per maintainer contract)

See §3. Plan: do not split awake, do not add product columns, do not tag anomaly, do not exclude any night. Sleep items enter the fact card’s existing personal baseline banding; when off, notification adds the fixed template “…clearly above/below your last 90 days; please check this night in the Health app”. PHA only reminds to check; does not judge right/wrong; does not correct. All columns always equal Health app values.

### F. Validation grain too coarse (fail-closed used in the wrong place · medium)

- **Today**: a 20-second stage rounded by Shortcuts to end==start, whole night 400; today changed to skip 0–2 minute zero-duration.
- **Rule**: **structural errors** (three list lengths differ, missing markers, unreadable timestamps, reverse order > 2 minutes) → reject the batch; **cosmetic defects** (zero duration, unknown label) → skip per segment and count; counts enter the audit line. Fail-closed is “do not invent numbers”, not “one bad segment throws the whole night”.

### G. Partial POST residue has no cleanup path (data hygiene · medium)

- **Today**: 9/6 daily `in_bed_hours=0.728` from a 19:41 partial POST, not truth, will enter the 90-day baseline.
- **Plan**:
  1. Rule: when a sleep bundle successfully writes wake day D, **clear all of D’s `healthkit|…|sleep_*` old daily-key rows** then recompute (existing per-metric replace expanded to the whole sleep family).
  2. One-shot cleanup: maintainer deletes `healthkit|default|sleep_in_bed|2026-09-06|healthkit` and recomputes 9/6 (steps written on the task card; not a code change).
  3. Fact card: `in_bed_hours < 1h` and no stages → show “none” rather than 0.7.

### H. Phone has no receipt (operability · medium)

- **Today**: 12:13 rerun, Mac no POST, maintainer did not know; PRD §10 already requires “UI must show last success time” but no API.
- **Plan**: `GET /ingest/healthkit/last?user_id=` returns last success/fail time, metric, summary; full-card top shows “last sync hh:mm · sleep / quantity”. Shortcut end Show Result unchanged. Filed as FR-1.7.

### I. Docs and hard-coding stale (low)

- PRD M1-P6 row “pending on-device Allow Access” “yesterday-noon–today-noon window” stale; task-card status row stale; this round already changed.
- Shortcut “Show Result” hard-codes “Health app anchor (9/6)…”; anchors expire; delete (do it on next Shortcut regenerate).
- Acceptance anchor is still 9/6, while first real ingest is 9/7; maintainer needs to add 9/7 six-item screenshots and switch the anchor to “same night as ingest”.

## 5. What was done right (do not revert)

- Iron law not broken: Watch → iPhone HealthKit → ingest → Mac; no LLM filling numbers; missing writes empty not 0; efficiency not POSTed.
- HRV SDNN on-device 40.97 vs Health 41; RMSSD column not polluted.
- Quantity Shortcut “PHA 同步健康” active energy / RHR already matched; this round did not break them.
- Shortcuts pits found by the sleep Shortcut are all in the change-log (Find labels, Value enums, If/Count/JSON dict always crash, File body, `is today` XML, large-list crash, `÷`, narrow space).
- Stage-label truth `Core/Deep/REM/Awake` already in the fold table.

## 6. M1-P6 done gate (freeze here before writing into PRD)

All must hold to mark DONE:

1. Same night: Health app wake-day D screenshot vs daily table. **Only accept items Health has that day and the user has checked**, each ≤ ±10 minutes; items Health does not have PHA must be empty; both empty counts as pass. Stages or `stage_overlap` rule same as task card. **First-night evidence = §6.2 (after deleting Pillow).**
2. Any ingest satisfies `asleep + awake ≤ session span ≤ window length` (when those items exist).
3. When awake exists: `awake_duration_hours` vs Health ±10 minutes; when off personal baseline the fact card emits the “please check” reminder sentence, no judgment words.
4. Consecutive 3 days Shortcut finishes 200, no *problem running*; each response contains the audit line.
5. 9/6 residue cleared; no orphan `healthkit|…|sleep_*` daily-key rows.
6. Selfcheck covers: noon window, wake-day derivation, cross-stage overlap, off-baseline reminder sentence, zero-duration skip, no In Bed → null.

**Source-of-truth contract (2026-09-07 maintainer)**: Health app **display** is truth, not multi-source raw union. M1 transition allows a single write source (Watch); aligning multi-source to system priority is M2. Metric set follows FR-2.7 checkboxes; forbid hard-coding “sleep must have all six”.

## 6.1 Second on-device rerun (12:34:35)

`<LAN-IP>` POST **200**, 9/7 daily table **digit-for-digit identical** to the 11:59:58 run (asleep 10.6 / core 6.033 / deep 1.633 / REM 2.933 / awake 2.683). Double-count is reproducible, not random; T0 replay will locate it.

## 6.2 First-night alignment after deleting Pillow (15:41)

“Show All Data” proved dual track: Watch and Pillow each have a Core/Deep/REM/Awake set; In Bed is Pillow only. Turning off write ≠ deleting history. After deleting last two days of Pillow sleep and rerunning:

| Item | Health app (after delete) | Ledger 15:41 | Diff |
|---|---|---|---|
| Asleep | ≈7.72 (Watch display) | 7.60 | −7 minutes |
| Awake | ≈3.58 | 3.45 | −8 minutes |
| Core / deep / REM | present | 4.90 / 1.65 / 1.05 | each ≤5 minutes |
| In bed | **none** | **empty** | pass |
| `stage_overlap` | — | false | — |

Cross-stage overlap 0; segment count 40. First night passes the new gate; T7 receipt shipped. **T9 (2026-09-10)**: maintainer orally confirmed 9/8–9/10 Health vs daily table largely match (asleep/awake/core/deep/REM; excluding in bed) → M1-P6 DONE.

## 7. Execution task list (for the coding agent, in order, each independently rollbackable)

Common constraints (every item):

- First reply outputs `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`; touching `pha/main.py` / restart also stacks `CONSENSUS_ACK: stability-plan-v2026-06-10 read`.
- Restart only with `bash scripts/pha_restart_accept.sh`. **Do not** change `packages/harness_core`. **Do not commit / do not push**.
- Each item same PR appends a [`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md) entry (class / evidence / change / rollback), and `scripts/pha_healthkit_ingest_selfcheck.py` all green.
- Iron law: no LLM filling numbers; missing writes empty not 0; ingest structural error rejects the batch, cosmetic defects skip per segment and count; forbid hand-editing numbers to match truth.
- **Do not** break quantity Shortcut `_find_health` / `_get_detail` while fixing sleep (active energy / RHR / HRV already match).
- Shortcut changes: one place at a time, Mac regenerate → AirDrop → phone delete old install new → Allow Access → run → look at server JSON.

| # | Task | Scope / landing | Acceptance | Rollback |
|---|---|---|---|---|
| **T0** | **Forensic replay**: get the raw `PHA_SLEEP_V1` body of the 9/7 200 (phone “Show Result” full copy/share to Mac, save `data/local_shortcuts/sleep_body_2026-09-07.txt`; data dir already gitignored). Write offline replay script `scripts/pha_sleep_bundle_replay.py`: print stage/start/end/duration per segment; find **overlapping pairs**, fully duplicate segments, per-stage sum vs per-stage union vs cross-stage total union, session span | Read-only, do not touch DB | Can explain in one sentence which segments make up the extra ≥1.3h of 13.28h; conclusion written into this document §2 | Delete the script |
| **T1** | **Segment persist + audit line**: each `PHA_SLEEP_V1` segment writes `wearable_sleep_segments` (`sample_id=healthkit\|{user}\|{stage}\|{start}\|{end}\|{source?}`, `is_awake`, idempotent); daily table recomputed from segments (reuse `sleep_metrics_from_segment_rows` / `compute_sleep_hours_union`); no longer write stage-hours daily-key rows directly; success response and log one audit line `kept/skipped_zero/dropped_unknown_label/per_stage_h/union_asleep_h/session_span/window/stage_overlap`; success full body to log (INFO, token redacted) | `pha/healthkit_ingest.py`, `pha/sqlite_storage.py`, `pha/wearable_daily_aggregator.py`, selfcheck | selfcheck: 9/6 anchor 6 segments → daily six items ±0.02; response has audit line; segment table has rows; repeat POST idempotent | Stop writing segment table; restore daily-key path |
| **T2** | **Total union + `stage_overlap`; wake-day derivation + noon window**: asleep = sleep-stage one-shot total union; `Σ stages` off >5% → `stage_overlap=true`, stage columns empty; wake day D = calendar day of last sleep-stage end; keep only `[D-1 12:00, D 12:00)`; D earlier than received day >1 day → `stale_sleep_bundle` | Same T1 files | selfcheck: two-source overlapping segments → asleep = union, stages empty, flag true; 23:00 onset overnight segments all belong to wake day; 23:30 run does not mix tonight into last night | Restore window to received_at−24h |
| **T3** | **Off-baseline check reminder** (no split awake, no product column, no anomaly tag, no exclude any night): sleep items (asleep/core/deep/REM/awake/in bed) enter fact card’s existing personal 90-day baseline banding (n ≥ 7); when an item is outside baseline percentile, notification and full card append fixed template “{metric} {value}, clearly {above/below} your last 90 days; please check this night in the Health app”; numbers kept as-is; user edits in Health overwrite on next sync | `pha/fact_card.py`, template strings, selfcheck | 9/7 awake 3.58 vs baseline → reminder sentence; inside baseline → none; n < 7 → no band no remind; copy has no “error/anomaly/collection mistake” judgment words | Remove the template sentence |
| **T4** | **In-bed rule**: `in_bed_hours` only from In Bed samples; missing → NULL; add derived `sleep_period_h` (first sleep start → last sleep end), **not** written into in bed; efficiency only computed when in_bed has a value; fact card `in_bed<1h` and no stages → “none” | Same T1/T3 | 9/7 construct: no In Bed → in_bed NULL, sleep_period ≈ 9.9; with In Bed → 8.95 | — |
| **T5** | **Same-day sleep-family cleanup + 9/6 residue**: on successful bundle write of wake day D, delete all of D’s `healthkit\|…\|sleep_*` old daily-key rows then recompute; maintainer script `scripts/pha_sleep_cleanup_day.py --day 2026-09-06 --dry-run` for one-shot clear of `in_bed=0.728` | ingest + script | dry-run lists rows to delete; after apply 9/6 six items all empty | Script deletes no non-`healthkit\|` rows |
| **T6** | **Shortcut D1**: `build_sleep` Find Start Date descending + Limit (start 150); add last-N-days date predicate (no date predicate → on-device empty set); Get Details try Source/Device (if empty, keep, do not force); delete 9/6 anchor copy; keep `is today` as fallback | `scripts/macos/build_pha_ingest_shortcuts.py` | On-device multiple 200s; pre-midnight segments in window; **do not require** body to have In Bed (none if Health has none) | Generate back to `is today` version |
| **T7** | **FR-1.7 receipt**: `GET /ingest/healthkit/last?user_id=` returns last success/fail time, metric, audit summary; full-card top “last sync” | `pha/healthkit_ingest.py`, `pha/fact_card_api.py`, HTML | 12:13-class “ran but never arrived” visible on the page | Remove the route |
| **T8** | **Doc closeout**: task-card “current implementation drift” table zeroed; PRD M1-P6 row filled with gate evidence item by item; change-log | docs | Three docs’ contracts agree | — |
| **T9** | **Acceptance**: consecutive 3 nights, maintainer Health sleep page vs daily table per §6 gate (asleep/awake/core/deep/REM); **do not accept in bed** | — | **Passed** (2026-09-10 maintainer oral: 9/8–9/10 largely all match) → M1-P6 DONE | — |

Why order cannot shuffle: without T0/T1 segment evidence, T2’s dedupe rule is a guess; without T2, T4 numbers are still inflated; T6 Shortcut window widen after server window is correct, else last night and the night before mix. T3 only touches fact-card copy and may parallel T2.

## 8. Documents changed this round

- New: this document.
- [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md): status row; overnight rule changed to “data-derived wake day + noon window”; added “awake contract + off-baseline check reminder”, “cross-stage union”, “segment persist”, “collection candidates”, “residue cleanup”, “done gate”; old “Shortcut” section marked transitional; 9/7 truth anchor; reject “in bed = session span”; withdraw “awake three-way split”.
- [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md): FR-1.6 acceptance completed; new FR-1.7 sync receipt; M1-P6 row updated; §11 additional findings; §12 v1.4.
- [`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md): this round’s entry appended.

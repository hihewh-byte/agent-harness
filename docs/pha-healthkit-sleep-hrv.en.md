# Task card · Sleep / HRV full ingest (M1-P6)

> **Language / 语言**：English (this document) · [中文](pha-healthkit-sleep-hrv.md)

> Status: `DONE` · 2026-09-10 T9 maintainer verbal confirm that 9/8–9/10 Health app vs daily table is “basically all matching” (asleep / awake / core / deep / REM; in-bed not in this acceptance). HRV already matched on-device. T0–T8 landed. Anchor A passed the gate.  
> Review and plan: [`pha-sleep-ingest-review-2026-09-07.md`](pha-sleep-ingest-review-2026-09-07.md) (required reading before coding)  
> Governing: PRD FR-1.6 / M1-P6; constitution: fail-closed, never write numbers that do not reconcile into the same column  
> Driver: on-device active energy already matched; sleep/HRV still showing “none” after being checked is this card’s scope

Analysis must use “each item”. Do not take a single sleep-hours number, and do not pass SDNN off as RMSSD.

---

## What the iPhone Health app / HealthKit actually provides

Canon is **Apple Watch + iPhone Health** (without a Watch, stages / overnight HRV are usually missing).

### Sleep (Health app “Sleep” page)

| What the Health app shows | HealthKit source of truth | Can a Shortcut treat it like steps (“one quantity for today”)? |
|-------------------|----------------|--------------------------------------|
| Time in bed | `Sleep Analysis` = In Bed segment start/end | No — sum the segments |
| Total time asleep | Asleep / Asleep Unspecified segments | No |
| Core sleep | Asleep Core (watchOS 9+ staging) | No |
| Deep sleep | Asleep Deep | No |
| REM | Asleep REM | No |
| Awake (inside the sleep window) | Awake segments | No |
| Sleep efficiency | Health app **computes** it; not an independent sample | Must compute from asleep / in-bed; do not invent an efficiency sample |
| Sleep heart rate / respiratory rate | Quantity types, often falling in the sleep window | Separate card; not Sleep Analysis |
| Wrist temperature (some devices) | `Apple Sleeping Wrist Temperature` | Quantity, separate column |

There is **no** official quantity type named “sleep hours”. The Health app’s “slept 7 hours” is the summed Asleep segments, displayed.

### HRV (Health app “Heart Rate Variability”)

| What the Health app shows | HealthKit source of truth | Notes |
|-------------------|----------------|------|
| HRV points, daily mean line | Find label `Heart Rate Variability` = **SDNN (milliseconds)** | Watch samples at night / during breathing; many points per day |
| RMSSD | **Apple does not provide it** | Third parties may write it. **M1-P8 DONE**: historically mislabeled column migrated to `hrv_sdnn_ms`; registry `hrv_rmssd_ms` marked deprecated and not fact_card eligible; new writes are always SDNN |

What can be derived from SDNN points and used in analysis: **count, then-current daily mean, min, max, overnight-window mean**. These are aggregations, not another raw Health type.

#### Then-current daily mean (already encoded this cut)

When the Shortcut runs, Average over **SDNN points already written that calendar day** is the “live mean”. It equals the day’s mean at that moment, not a different Health type.

- Run after waking in the morning: daytime usually has no new points yet, so the number is essentially last night’s sleep-window mean — high analytic value.
- Run again in the evening: the same column is updated by any new daytime points; carry the ingest timestamp; do not pretend it is the “official end-of-day mean”.
- Ingest: `POST metric_type=hrv_sdnn` → daily column `hrv_sdnn_ms`. **Do not** write `hrv_rmssd_ms`.
- Fact card: when “HRV” is checked and RMSSD is empty, display **HRV (SDNN)** and use only the SDNN column for baseline.
- Capture: Find `Heart Rate Variability` → Average → one number. First run must tap Allow Access in the Shortcut.

---

## Overnight rules (frozen before sleep encoding)

The Health app shows **one whole night** as one sleep, dated on the **wake day**, not the fall-asleep day. On-device 2026-09-06: the page says Sep 6, fall-asleep 9/5 23:03, in bed 8h36m, asleep 6h45m. It does not add two nights together unless the person actually slept two nights in a row.

**Day key**: same as the Health app — record on the wake day. **Wake day D is derived from data** = calendar day of the last sleep-stage segment’s end; do not use `received_at`. If derived D is more than 1 day earlier than receive time, return `stale_sleep_bundle` so the user knows they got an old night.

**One-night window**: sleep for wake day D = segments that intersect `[D-1 12:00, D 12:00)` (covers “last night 23:00 through this morning” as one night; excludes the night before that, and excludes a stub that just started tonight).

**Product source of truth**: user judgment follows **Health app presentation**, not the HealthKit multi-source raw union. The Health app shows one set by data-source priority; PHA should align to that presentation. M1 transition: maintainer-side simplification to a single write source (delete third-party history such as Pillow, Watch only). Shortcuts cannot get a reliable Source; multi-source system-priority alignment is left to **M2** (HealthKit API / `sourceRevision`). Do not hand-edit samples to make numbers match.

**Acceptance anchor A (2026-09-07 · same night)**:

| Time | Health app / notes | PHA store |
|---|---|---|
| 12:23 (with Pillow) | In bed 8.95, asleep 7.717, awake 3.583, core 4.983, deep 1.633, REM 1.100 | Early inflation (dual-track union) |
| 15:41 (Pillow deleted for recent two days) | In bed **none**; asleep/awake/stages ≈ Watch rows | Asleep 7.60, awake 3.45, core 4.90, deep 1.65, REM 1.05, in bed **empty**; vs Health app ≤8 minutes; `stage_overlap=false` |

The original anchor A in-bed 8.95 came from Pillow; after deletion both Health app and PHA have no in-bed, which passes the gate “both empty counts as pass”.

**Acceptance anchor B (2026-09-06 · Health app Stages)**: in bed 8.6, asleep 6.75, awake 1.85, REM 1.6, core 4.6, deep 0.55. That night asleep+awake = in bed is a coincidence of short sleep latency, **not a rule**.

**In-bed may only come from In Bed samples**. If the Health app has none or they cannot be fetched → PHA writes empty, fact card writes “none”; do not derive from session span. Derived column `sleep_period_h` (first sleep start → last sleep end) is stored separately and is not written into in-bed. In-bed is not a required capture: registry `sleep_in_bed` has `enabled_default: false`; whether to display/care is the user’s checkbox (FR-2.7).

Forbidden:

- Using only `Start Date is today` (drops fall-asleep before midnight)
- Summing all segments from the last two calendar days without cutting a session (an evening run would add two nights)
- Counting In Bed + Awake as “how long I slept”
- **Unioning each stage separately then adding them as total time asleep** (cross-stage overlap double-counts)
- POSTing a “sleep efficiency” sample
- Deleting the pre-asleep in-bed stretch to make awake “look nicer” (that is fabricating data)
- Deriving in-bed from “asleep + awake” or session span
- Requiring PHA to have in-bed when the Health app has none, or hardcoding “all six sleep items must be present”

**Stage totals**: In Bed / Core / Deep / REM / Awake / Asleep Unspecified each count only their own class. **Total time asleep = one union of all sleep-stage segments** (Core ∪ Deep ∪ REM ∪ Asleep), excluding In Bed, excluding Awake. Per-stage hours are trusted only when “single source, mutually exclusive”; if `Σ stages` vs the total union differs by > 5%, mark `stage_overlap`, blank the stage columns, keep only the total union. Efficiency = asleep/in-bed, computed only on the server.

**Awake definition (maintainer freeze 2026-09-07)**: the Health app has no “pre-asleep” concept; sleep starts at fall-asleep; core/REM/deep count as asleep; awake does not. `awake_duration_hours` = Health app awake raw value — do not split, delete, or add a derived product column. The 9/7 session started with a **4-minute Deep** at 20:30, then ≈2.2h awake, true fall-asleep at 22:45: the App correctly treats “after sleep started, not asleep = awake”; the rule is correct. **PHA does not judge whether this is a capture error, does not tag, does not correct, does not exclude** — human sleep varies widely and PHA cannot decide. PHA only: compare each sleep item to the personal last-90-day baseline; on deviation, add one fixed template on notification / full card: “{metric} {value}, clearly {above/below} your last-90-day level; please check this night in the Health app”. If the user then edits in the Health app, the next sync overwrites. Copy must not use judgment words such as “error / anomaly / capture mistake”.

**Segment ledger**: every segment from the Shortcut is written to existing `wearable_sleep_segments` (`sample_id = healthkit|{user}|{stage}|{start}|{end}|{source}`, idempotent); the daily table is fully recomputed from segments; no longer drop “stage hours” daily-key rows directly. Success response and logs emit one audit line: `kept / skipped_zero / dropped_unknown_label / per_stage_h / union_asleep_h / session_span / window / stage_overlap`, shown as-is in the phone “Show Result”.

**Validation grain**: structural errors (three-list length mismatch, missing markers, unreadable timestamps, reverse order > 2 minutes) reject the whole batch; decorative flaws (zero duration, unknown labels) skip per segment and count.

**Current implementation drift (2026-09-10)**: none. T0–T9 all landed. T9 = maintainer verbal confirm 9/8–9/10 basically matched (excluding in-bed).

| Item | Spec | Current |
|---|---|---|
| Wake day / noon window / total union / segments+audit | See above | **Landed** (T1–T2) |
| Awake + baseline-deviation reminder | See above | **Landed** (T3); 9/10 deep sleep below → check sentence, no judgment words |
| In-bed from In Bed only; empty if none | See above | **Landed** (T4); daily `in_bed` all empty. 2026-09-10: maintainer deleted in-bed from Health app; T9 does not accept it; 2 orphan `sleep_in_bed` daily-key rows deleted |
| Same-day sleep_* daily-key cleanup | See above | **Landed** (T5); no `healthkit|…|sleep_*` orphan rows |
| Shortcut window | Cover last night; take In Bed if present | D1: last 2 days + Limit 150; Source/Device empty (Shortcuts does not emit source for Sleep) |
| Source of truth = Health app presentation | Keep only the displayed source by system priority | **M1 transition**: after maintainer deleted Pillow, single source ≈ presentation; T9 9/8–9/10 verbal pass; automatic multi-source alignment is M2 |
| FR-1.7 receipt | Last sync visible | **Landed** (T7): `GET /ingest/healthkit/last` + full-card top |

**Shortcut (transitional)**: “PHA sync sleep” = Find `Type is Sleep` + `Start Date is in the last 2 days` + Start Date latest first + Limit 150; take Value / Start / End (and empty Source/Device) into `PHA_SLEEP_V1` one POST. Without a date predicate, Health Find returns an empty set (already hit). An `is today` alternate Shortcut is still generated. Quantity Shortcut `_find_health` is unchanged.

**T9 evidence (2026-09-10)**: maintainer checked wake days 9/8, 9/9, 9/10 in the Health app and verbally confirmed the daily table is “basically all matching” — counts as pass. Compared items: asleep / awake / core / deep / REM. In-bed not accepted. Store correspondence:

| Wake day | Asleep | Awake | Core | Deep | REM |
|---|---|---|---|---|---|
| 9/8 | 6h12m | 8m | 3h41m | 54m | 1h37m |
| 9/9 | 8h13m | 47m | 5h18m | 28m | 2h27m |
| 9/10 | 7h58m | 41m | 5h02m | 1h04m | 1h52m |

This card has no coding leftover. Multi-source alignment by system priority remains M2.

---

## This card’s goals

1. **Sleep segments**: ingest items the user checked and for which the Health app has samples; `in_bed_hours` (In Bed only), `sleep_hours` (core ∪ deep ∪ REM total union), `sleep_core_hours`, `sleep_deep_hours`, `sleep_rem_hours`, `awake_duration_hours`. If there are no segments for a field, leave it empty; do not backfill yesterday; **do not fail for missing in-bed**.  
2. **HRV** (already matched): `hrv_sdnn_ms` = then-current daily mean. Do not write `hrv_rmssd_ms`.  
3. The Shortcut may POST one night of segment text (one request, dozens of segments), but **must not** dump hundreds of Health objects onto a URL or trigger “share a large amount of health data”.  
4. HRV acceptance (already passed): Health app has HRV points that day → store `hrv_sdnn_ms` is a reasonable magnitude; `hrv_rmssd_ms` is not rewritten.

## M1-P6 done gate (all must hold before marking DONE)

1. Same night: Health app wake day D vs daily table. **Accept only items the Health app has that day and the user has checked**, each ≤ ±10 minutes; items the Health app does not have must be empty in PHA; both empty counts as pass. Write stage columns when stages are mutually exclusive; on `stage_overlap` blank stage columns and keep only the asleep total union. First-night evidence = the 15:41 row of anchor A. **T9 three nights do not compare in-bed** (maintainer 2026-09-10: Health app already deleted In Bed).  
2. Any ingest satisfies `asleep + awake ≤ session span ≤ window length` (when awake/asleep are present).  
3. When awake is present: `awake_duration_hours` vs Health app ±10 minutes; on personal-baseline deviation the fact card emits a “please check” reminder sentence, no judgment words.  
4. Three consecutive days the Shortcut finishes 200, no *problem running*; each response includes the audit line.  
5. No `healthkit|…|sleep_*` orphan daily-key rows (9/6 leftovers already cleared).  
6. Selfcheck coverage: noon window, wake-day derivation, cross-stage overlap, baseline-deviation reminder sentence, skip zero-duration, no In Bed → in_bed null.

## Encoding order

Per review §7 task table **T0 → T9**, all landed. T9 = 2026-09-10 maintainer verbal confirm. M1-P6 = `DONE`.

---

## Explicitly out of scope (this card)

- Filling RMSSD with SDNN  
- Adding In Bed + Awake as “how long I slept”  
- Diagnostic titles, LLM filling numbers  
- A standalone Watch app  

# Handoff · Fact-card button interpretation v2 + metric freshness + checkboxes as seen (M1-P9.1 / P10 / P11 / P9.2 / P9.3)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-08-fact-card-interpret-v2.md)

> For the successor coding agent · drafted 2026-09-08 08:00, locked 08:30 · based on 9/7 23:20–23:30 browser acceptance + 9/8 08:00 / 08:12 on-device retest  
> First reply must output both lines:  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.7** (§1.3 / §4.2 / FR-1.5 / FR-2.7 / FR-2.9 / FR-6 / §8 / §11) · [`harness-consensus-opus48-2026-06-08.md`](harness-consensus-opus48-2026-06-08.md) §2 / §5 / §6  
> **Maintainer locked** (2026-09-08 08:27): §6 decision 11 = option A, decision 12 = drop implicit expand; FR-1.5 / FR-2.7 v1.7 already in the PRD. Decisions 7–10 execute as defaults.  
> Previous handoff: [`handoff-2026-09-07-fact-card-assessment.md`](handoff-2026-09-07-fact-card-assessment.md) (P7 / P8 DONE; P9 first version landed but not committed)

---

## 0. Required reading and live state before starting

Read order: `pha-mandatory-reads.mdc` global two → PRD v1.6 → harness consensus → last three of `pha-ios-proactive-change-log.md` → last three of `harness-change-log.md` → `rules/harness_profile_registry.generated.json` (how `wearable_only` / `supplement_manifest` declare slots).

**The workspace is not clean.** `git status` should show: `pha/fact_card.py`, `fact_card_api.py`, `fact_card_html.py`, `fact_card_prefs.py`, `scripts/pha_fact_card_selfcheck.py`, four docs (PRD / change-log / roadmap / pha-fact-card) modified; `pha/fact_card_interpret.py` and this file untracked. Code changes are M1-P9 first version + three temporary patches from last night’s acceptance; docs include 9/8 PRD v1.7 (decisions 11/12 locked). **Do not stash, do not checkout-discard, do not commit.** Commit only when the maintainer says “commit”; after this handoff’s P9.1, commit together with the first version so transitional audit logic does not enter history.

Three temporary patches (all in `fact_card_interpret.py`; P9.1 replaces two of them):

1. Date-fragment allowlist: split as_of year/month/day into `2026` `09` `07` stuffed into the atom set — treats the symptom; P9.1 replaces with date normalize.
2. When harness `numerics_audit.passed=True`, only block foreign numbers ≥100 — **this relaxes audit, violates PRD §4.2 and harness consensus §5.3, must be withdrawn.**
3. `failed` cache allows another POST to retry — keep.

`data/fact_card_interpret/` has one `done` cache whose body is “近 90 天…睡眠均值 7.6h（2026-06-10~2026-09-07）”, passed under the relaxed audit. **Clear that directory** after P9.1 lands.

---

## 1. What last night’s acceptance found (evidence)

Browser end-to-end: fill “My assessment requirements” → save echo OK → tap “Generate interpretation” → <1s “generating” → first `audit_rejected` (fragments `09` `07` `90` `06` `10`) → after patch `done`. The pipe works, but content and contract have four problems:

| # | Observed | Root cause | Violates |
|---|----------|------------|----------|
| A | Interpretation is one line “last 90 days sleep mean 7.6h”; user-named **deep sleep** never mentioned; baseline meaning unexplained | Routed `supplement_manifest` (log `qtype=lifestyle`, WARN `matrix_gap_supplement_text_matches_wearable_regex`); harness T0 manifest has one KV `wearable\|2026-06-10~2026-09-07\|睡眠均值\|7.6\|h`; fact-card JSON goes through `extra_system_context` side channel; the model, required to cite matching KV, only dares cite that one | FR-6.2 (input should be facts + progressive baseline + reference layer + assessment prompt) |
| B | Same page rule layer writes “last 12 months 267 nights”; AI block writes “last 90 days”; and the 6/10–9/7 window has only one or two HealthKit sleep nights, so the so-called “mean” is tonight | `wearable_only` / neighboring profiles’ Tier0 slot `WEARABLE_90D_SUMMARY` is a fixed 90-day window, no n | §1.3a do not split, FR-2.6 progressive window + disclose n, n<7 is not a baseline |
| C | Card-side extra audit grabs fragments with `\d+`, false-rejects month/day and window days as foreign; after relax it can let through invented `n=45` or `deep 2.3h` | Dates, window days, sample counts, measurements mixed into one compare class | harness §2.3 C-layer audit must be traceable; must not weaken for surface fluency |
| D | Page shows `2026-09-07T15:29:08.651238+00:00` (local actually 23:29), `上次同步成功：2026-09-07T16:26:19`, `**睡眠均值**` asterisks as-is | Render layer dumps storage format; textContent does not parse Markdown | Not a red line, but 2.3 success “honest” requires the user can read it |

Secondary: cache key `(user, as_of, prompt)` does not include metric selection, so old interpretation survives checkbox change; “model unavailable” only verified in selfcheck with a fake stream, Ollama never actually stopped; not run on iPhone Safari; cross-day cache expiry not tested; English locale not tested.

### 1.1 2026-09-08 08:00 maintainer on-device retest exposed three more

| # | Observed | Evidence | Root cause |
|---|----------|----------|------------|
| E | **Resting HR checked but “none”**; card top “last sync failed: 08:00:46 · quantity · unreadable_value” | Log 08:00:41–46 four `POST /ingest/healthkit`: energy, HRV, (third) 200, fourth `rhr` body `value:"" timestamp:""` → ingest fail-closed 400. `wearable_daily` 9/7 and 9/8 RHR both NULL, 9/6 = 60 | Two layers: ① Apple resting HR is a **once-daily, lagged** derived value; at 08:00 the Health app has no 9/8 RHR yet; Shortcut filters “today”, empty set still POSTs, correctly rejected; ② 9/7 RHR exists in Health, but 9/7 did not run the quantity Shortcut, and the Shortcut **carries no sample date** (log “empty timestamp; using received_at”), so values can only land on “today”; yesterday has no path in. Fact card per PRD “missing same-day row stays empty, do not backfill” honestly shows “none” |
| F | 08:00 card judged **active energy 13.5 kcal below**, **HRV 19.3 ms (one or two samples overnight) below**, and gave “consider an easier plan” | Card JSON `active_energy value 13.5 band below n=274` | **In-progress day**: accrual metrics (steps, energy) in the morning are a stub, compared to 274 **full-day** baselines; HRV daily mean also changes as daytime samples arrive. This is “partial day posing as full day”, the other face of E: the card has no “metric freshness semantics” |
| G | User changed assessment to “focus resting HR and HRV and deep sleep… what training advice for today, e.g. workout type and intensity” → tap interpretation → **“not generated (audit failed)”** | Cache `f1bdff52…` `violations: ['unauthorized_wearable_count:100']`; that turn log `route=wearable_only`, manifest only `wearable\|2026-09-08\|今日HRV\|19.3\|ms`, `numerics=FAIL` | This time **harness’s own C-layer audit** rejected (not card-side extra); correctly: the model wrote `100` (likely RHR reference 60–100 or exercise HR zone), and 100 is neither in the manifest nor in a T1 disclosure block. Deeper cause still A: reference ranges only in the side channel, not T1 manifest entries; TASK never told the model “off-card numbers only in T1 blocks”; the user’s “intensity” essentially needs numbers not on the card; the product needs an explicit exit |

E/F are not interpretation; they are a product gap in the fact-card number layer; separate card **M1-P10** (§5b). G is covered by P9.1, with three additions in 4.3 / 4.4 / 4.6.

### 1.2 2026-09-08 08:12 screenshot: checkboxes ≠ card list; changing checkboxes requires reinstalling the Shortcut

| # | Observed | Evidence | Root cause |
|---|----------|----------|------------|
| H | “Which metrics I want” checked 5 (sleep total / HRV / resting HR / deep / active energy); “facts” listed 9, extra REM / core / in bed / awake; assessment wrote “7 of 9 selected have values” | Registry five sleep-stage rows all have `fact_card.reveal_when_selected: [sleep_time_asleep, sleep_deep, sleep_rem]`; `fact_card_prefs.resolve_metric_specs` **appends** all stages when the user checks any of them | M1-P6 implicit expand so “sleep can compare if present”. It makes the card’s metric set ≠ user checkboxes, directly violating FR-2.7 “metric set specified by the user”, and lifts coverage denominator from 5 to 9, so assessment writes “no composite” / “missing items”. Change-log has no maintainer decision for this; it is an implementation choice |
| I | Page hints “after changing checkboxes, regenerate the Shortcut on Mac”; maintainer wants change → **rerun Shortcut takes effect**, or **refresh browser takes effect** | `build_pha_ingest_shortcuts.py` calls `shortcut_sync_specs("default")`, generates fixed Find actions from **current prefs**; PRD FR-1.5 original “Shortcut POSTs one same-day number for each user-selected item that has `shortcut_health_type`” | Shortcut is a static snapshot of checkboxes; iOS “Find Health Samples” type is a static editor parameter, not a variable, so the Shortcut cannot at runtime “Find whatever list the server sent”. Either Shortcut covers the full set and the card filters by checkboxes, or Shortcut carries full-set Find gated at runtime by If from a server plan |

H can be changed inside consensus (§5c); option A for I was locked by the maintainer 08:27; FR-1.5 v1.7 is in the PRD (§6 decision 11).

Two more notes (P9.2): band labels are **quality direction** (awake 3.5h showing `below` means worse than baseline) while copy is **numeric direction** (“clearly higher”) — two directions on one row confuse the reader; top “last sync failed · unreadable_value” calls “Health has no resting HR yet today” a sync failure.

---

## 2. Non-negotiable constraints this round (two consensuses mapped here)

- **TurnEvidencePlan before LLM** (harness §2.1): interpretation must have its own profile declaring slots/forbidden/tools; must not rely on `user_message` text bumping the router.
- **Tier0 budget** (harness §2.2): fact-card manifest and user assessment prompt are both Tier0 critical slots; must not be squeezed by tail truncation; assessment prompt cap 2000 already set, over → 400.
- **C-layer audit must not weaken** (harness §2.3 / §5.3; PRD §4.2): only tighten, add dimensions (dates become an independent word class); no threshold-to-allow.
- **No bare run** (PRD §4.2): still `stream_pha_chat_events` → `orchestrate_chat_turn_events`; do not import the Ollama client.
- **No LLM on the proactive path** (PRD §1.3): notification body, `assessment`, cron contain no interpretation; no pre-generate; `interpretation` only at top level, non-null only after the user tapped.
- **Anti-hardcode** (constitution; `pha-mandatory-reads.mdc` forbids): new profile via registry declare and `--write` regenerate; no phrase rules to pass review; reference ranges stay in the registry.
- **fail-closed**: audit fail → drop the whole segment, show “not generated (audit failed)”; never use template text posing as AI.
- **Change process**: P9.1 same PR updates `harness-change-log.md` (declare P0/P1/P2 class, rollback, at least one harness selfcheck) **and** `pha-ios-proactive-change-log.md`; P9.2 / P9.3 only the latter. Restart only `bash scripts/pha_restart_accept.sh`.
- **Do not change** `packages/harness_core`, public README, `pha/healthkit_ingest.py` sleep path.

---

## 3. Work order

| # | Card | Nature | Done when |
|---|------|--------|-----------|
| 1 | **M1-P9.1** Dedicated profile + fact-card manifest + date-normalize audit + off-card numbers T1 exit | Touches harness (P2: Profile/Registry extension; main route stays deterministic; audit only tightens) | Rerun two on-device flows: interpretation mentions user-named metrics; window wording character-for-character with the rule layer; no “近 90”; dates only as_of; intensity-class advice only as qualitative words or sourced T1 blocks; selfcheck and harness selfcheck green |
| 2 | **M1-P10** Metric freshness semantics (lagged daily / in-progress accrual / rolling mean) | Fact-card side + Shortcut generator + ingest empty-sample handling only; **changes one frozen PRD line, needs §6 decision 7** | 08:00 card can show “resting HR 60 bpm (Sep 7, most recent)” and band; energy writes “accrued as of 08:00, in progress, unbanded”; Shortcut empty set no longer POSTs 400 |
| 2' | **M1-P11** Checkboxes as seen + Shortcut full-set sync | Fact-card side + registry + Shortcut generator only; FR-1.5 / FR-2.7 v1.7 **already locked in PRD**; just implement | Card list = checkbox list, coverage denominator = checkbox count; after changing checkboxes, refresh browser switches; same-day values for newly checked items appear after the next Shortcut run, no reinstall |
| 3 | **M1-P9.2** Local timezone + locale date render + plain-text output + cache key + band/copy direction unified | Fact-card side only | All page times local minute precision; Chinese “9月7日 23:29”; no `**`; old interpretation gone after checkbox change |
| 4 | **M1-P9.3** On-device and boundary acceptance | Verification | iPhone Safari full flow; stop Ollama shows “model unavailable”; cross-day cache expires; en-US format |

P9.1 and P10/P11 are independent; two agents may parallel. **P10 and P11 must be done by the same agent in one pass**: both change the Shortcut generator; each reinstall is Mac export + iPhone replace; combine into one reinstall. P9.2 depends on all three.

Each card: selfcheck → official restart → browser/device look → same PR write change-log → update PRD §8 status.

---

## 4. M1-P9.1 concrete approach

### 4.1 New profile `fact_card_interpret`

Add at the existing profile declaration (`harness_report.py` profile table, same level as `wearable_only`), then `python scripts/pha_harness_profile_registry_generate.py --write` regenerate the registry; the diff must show the new profile.

- `slots_tier0`: `TASK`, `NUMERICS_MANIFEST`, `FACT_CARD_CONTEXT` (new slot: compact fact-card JSON, see 4.2), `USER_ASSESSMENT_PROMPT` (new slot: user assessment original; same nature as `SUPPLEMENT_BG` — user speech, not a numeric source).
- `slots_tier1`: empty.
- `forbidden`: `WEARABLE_90D_SUMMARY`, `PATIENT_STATE_WEARABLE`, `PATIENT_STATE_LAB`, `USER_SNAPSHOT`, `SUPPLEMENT_BG`, `DOSSIER_*`, `GET_HEALTH_DATA`, `GET_TEMPORAL_HISTORY_DOSSIER`, `EVIDENCE_CATALOG`. **This directly solves B**: harness’s fixed 90-day summary never enters this path.
- `tools_allowed`: empty.
- `legacy_question_type`: `WEARABLE`.

**How to enter this profile**: add an explicit `profile_override` parameter to `stream_pha_chat_events` / `orchestrate_chat_turn_events`, accepting only profile names that exist in the registry, else ignore and telemetry `profile_override_rejected`. `fact_card_interpret.py` passes `profile_override="fact_card_interpret"`; resolver `infer_profile_hint` is skipped. **By default do not expose this parameter on the public `/api/chat` body** (see §6 decision 4). This is a legitimate TurnEvidencePlan entry, not a phrase rule.

`user_message` becomes a fixed short sentence (e.g. “请生成今日事实卡解读”), no longer concatenating the assessment prompt, so text does not leak into any route/classifier.

### 4.2 Fact card → Numerics Manifest

Add a manifest-build entry (in `numerics_manifest.py` or a separate module, called by the profile’s `NUMERICS_MANIFEST` slot). Input is the card from `load_fact_card()`; output same format as existing `ManifestEntry` `domain|anchor|metric|value|unit`:

- domain uses new value `fact_card` (do not pose as `wearable`, to avoid `wearable_grain_source` logic).
- Each checked valued metric: `fact_card|{as_of}|{label}|{value}|{unit}`.
- Each metric with a baseline: one each `baseline_mean` / `baseline_min` / `baseline_max` / `percentile`, anchor `{baseline_earliest}~{as_of}`, metric name includes the window word (e.g. “睡眠总时长·近 12 个月均值”), plus `fact_card|{anchor}|睡眠总时长·基线夜数|267|nights`.
- Reference ranges: T1 entries `reference|-|{label}·参考下限|7|h` and upper; `source` into metric name or note. Rule: same as FR-2.8, only metrics with registry `reference_range`.
- `reference_date = as_of`; `forbidden_dates` empty.
- **`allowed_dates` currently only takes `lipid` domain 10-digit anchors** (`numerics_manifest.py` about line 234). Expand to also take all ISO dates appearing in `fact_card` domain anchors (as_of, baseline_earliest). This is a tighten not a relax: wearable dates previously neither entered the allow set nor were audited.

`FACT_CARD_CONTEXT` slot holds the compact card (as_of, calendar_day, stale, metrics, summary, advice), topped with “the following are the only citable numbers and dates”. Tier0 budget: this slot after TASK and manifest, before assessment prompt; when over budget, cut advice → summary → metrics; **must not cut manifest or assessment prompt**.

### 4.3 TASK text (in the profile, not in `fact_card_interpret.py`)

Points; wording is the implementer’s: only cite numbers and dates in the manifest; each metric’s window wording must match the card exactly (if the card says “近 12 个月 267 夜” it cannot say “近 90 天”); dates may only appear as as_of (after P10, plus each row’s actual `day`); otherwise relative (“today”, “last N months N nights”); must answer metrics the assessment named; if that metric has no same-day value, say “今日无记录” (after P10 “most recent is day X”); plain text, no Markdown marks; no diagnosis/prescription/dose; ending does not repeat the disclaimer (page already has it); language by `response_locale`.

**Only exit for off-card numbers (problem G)**: assessment prompts often ask for “intensity”, “HR zone”, “how many steps” — numbers not on the card. TASK must say: any number not in the manifest may only appear inside `【参考标准】…（来源：…，请自行查证，非医疗建议）` T1 disclosure and give a source; outside the block only qualitative words (low intensity / moderate / easier / recovery day). The user’s assessment prompt **cannot unlock** this rule — it is user speech, not a numeric source. Then harness `audit_disclosure_block` and `unauthorized_wearable_count` correctly allow/block, and card-side “strip T1 then compare” already compatible.

### 4.4 Redo card-side audit (`fact_card_interpret.py`)

> **From 2026-09-08 20:11 replaced by [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md) §2–§3**: this section’s “every number must ∈ atom set” and “two audits independent” are **withdrawn** (false positives: `SpO2`/`VO2max` labels, `96.0`, educational integers; T1 necessarily fails under en-US). Kept below as history.

Withdraw “≥100 threshold” and “date-fragment allowlist”; two steps:

1. **Date step**: reuse `numerics_manifest._extract_normalized_dates` (already supports ISO and Chinese “2026年9月7日”; if P9.2 introduces English month-name format, add English parse in the same function — a tighten). Every normalized date must ∈ {as_of, calendar_day, baseline_earliest…}, else `audit_rejected` / `unauthorized_date:<d>`. Then mask those date strings from the body.
2. **Number step**: remaining body (T1 already stripped) every number must ∈ the atom set. Atom set = `fact_card_numeric_atoms(card)` ∪ window days actually used on the card (90/365 when `baseline_window` is `90d`/`365d`) ∪ copy constants 7, 12 (“n/7”, “近 12 个月”). **No threshold of any kind.** Not in the set → `audit_rejected` / `unauthorized_value:<t>`.

Harness-side `numerics_audit` rejects whenever `passed=False` (any violation, not only `unauthorized`). Two audits independent, both must pass; card-side audit is a **supplementary dimension** to harness audit (window consistency, off-card dates), not a substitute.

Cache records add fields: `harness_profile`, `numerics_audit` (full object), `card_digest`, for telemetry.

**Failed state must tell the user the rejected number** (local data, no privacy issue): `GET …/interpret` `failed` response keeps `violations`; page writes “the model wrote a number not on the card (100); the whole segment was dropped; you may retry”. Also change the “My assessment requirements” textarea hint to one sentence: “Interpretation can only cite numbers on the card; intensity, HR-zone class advice will be qualitative or given as sourced reference standards”, so expectation management is at the input.

### 4.5 Cache key

`sha256(user_id | as_of | card_digest | locale | assessment_prompt)`, where `card_digest` = stable serialization hash of selected metric ids sequence + per-metric value/baseline_window/baseline_n. Checkbox change, value change, language change all auto-invalidate.

### 4.6 Selfcheck (`scripts/pha_fact_card_selfcheck.py` extend + at least one harness-side)

Fact-card side (monkeypatch stream):

- Card window 365d, fake reply writes “近 90 天” → `audit_rejected` contains `unauthorized_value:90`.
- Fake reply writes `2026-06-10` not on the card → `unauthorized_date:2026-06-10`.
- Fake reply writes “2026年9月7日” (= as_of Chinese) and `7.6h`, `267` → `done`.
- Fake reply with T1 block and in-block numbers = registry reference range → `done`.
- Harness `numerics_audit.passed=False` and violation is `future_date` → reject (prove we no longer only look at `unauthorized`).
- Assessment writes “give intensity advice”, fake reply outside the block writes “心率 120–140” → reject; rewrite as T1 “【参考标准】中等强度常见对应最大心率 64–76%（来源：ACSM，请自行查证，非医疗建议）” → `done`; `violations` go into GET response as-is.
- Reproduce G: fake reply outside the block writes “参考范围 60–100” while the card’s RHR reference is 60–100 → still reject (reference ranges may only appear as T1; same as FR-2.8).
- After checkbox change `current_interpret_key` changes; old cache misses.
- Without tapping, `interpretation is None`; notification body and `assessment` have no interpretation wording (existing, keep).

Harness side: after registry `--write`, `python3 scripts/pha_chat_turn_fsm_selfcheck.py`, `pha_numerics_manifest_selfcheck.py` still PASS; add or extend one selfcheck proving a plan with `profile_override="fact_card_interpret"` has `WEARABLE_90D_SUMMARY` in forbidden, and `NUMERICS_MANIFEST` entry count = checked valued metrics + baseline entries + reference entries.

On-device/browser: rerun two real flows. ① Assessment “focus sleep total and deep” → body has “深睡” and “睡眠总时长”; baseline wording matches the card’s “近 12 个月 267 夜”; body has no “90”; no dates besides as_of. ② Assessment is the maintainer 9/8 original (resting HR + HRV + deep + workout type/intensity) → `done`; intensity only as qualitative or T1; resting HR same-day missing said explicitly; page shows model name. Both rounds log `route=fact_card_interpret`.

### 4.7 Docs

- `harness-change-log.md`: entry declares **P2 (Profile/Registry extension) + C-layer audit extra dimension**; list profile slots; rollback = delete profile declaration + `--write` regenerate + restore `allowed_dates`.
- `pha-ios-proactive-change-log.md`: entry + note withdrawing last night’s “audit relax”.
- PRD: FR-6 add two rows (wording in §7); §8 M1-P9 note becomes “P9.1 DONE”.

---

## 5b. M1-P10 Metric freshness semantics (answering “does PHA simply not use yesterday’s data”)

### 5b.1 Conclusion first

Yes, today’s card follows PRD §4.1 “calendar-day same-day row (missing stays empty, do not backfill)”, so 9/8 morning resting HR shows “none”. The principle’s purpose is **not to let a non-today number pose as today**, and that must stay; but it tied “do not pose” to “do not display”, which fails for Apple once-daily lagged metrics, morning stub accrual metrics, and metrics that are themselves multi-day means. The fix is not abandoning the principle; it is writing “what this metric’s value is in time” into the registry, letting the card take values by the declaration and **write the actual date / as-of time on the face**.

### 5b.2 Registry: `fact_card.temporal` (anti-hardcode; no `if` metric name in Python)

Each eligible metric declares a `temporal` object; default = current behavior (same-day full-day value only), so unchanged-registry metrics keep behavior.

| `kind` | Meaning | Value rule | Card wording | Suggested class |
|--------|---------|------------|--------------|-----------------|
| `accrual` | Accrues within the day; complete only at day end | Take same-day row; if `calendar_day == today` mark `partial_day=true`, attach `as_of_time`, **unbanded**; baseline uses full days only | “active energy 13.5 kcal · accrued as of 08:00 · in progress, unbanded” | steps, active energy |
| `daily_lagged` | Platform once-daily derived, often lagged | Look back within `freshness_days` (default 2) for the latest row; emit the row’s `day` as-is, `freshness = same_day \| prior_day`; still band; only beyond window “none” | “resting HR 60 bpm (Sep 7, most recent) · above your last 12 months…” | resting HR; future VO2max, walking HR mean |
| `overnight` | Attributed to wake day | Existing sleep logic unchanged | “sleep total 6.2h” | sleep items; HRV see §6 decision 9 |
| `rolling_mean` | The metric itself is a multi-day mean | Take mean of daily values in `window_days` and emit `n_days`; baseline uses the same rolling series (same contract vs same contract) | “last 7-day mean X · n=5” | “past 7-day mean” class the user mentioned; no registry instance yet; define the kind first |

Notification lead coverage then subdivides: “7/9 have values, of which 1 is prior-day, 2 in progress”. Any row `day != calendar_day` or `partial_day` must not be written as “today” — this is the new honesty invariant replacing the old selfcheck “today must stay empty”.

### 5b.3 Shortcut generator (`scripts/macos/build_pha_ingest_shortcuts.py`)

- `daily_lagged` metrics: Find becomes `Start Date is in the last 2 days` (same as T6.1 sleep D1, Operator 1001 / 2 / 16384); Get Details takes **Start Date and value**; POST per sample with real date on `timestamp`; ingest aggregator daily-means. Cannot keep a dateless Average.
- All quantity Shortcuts: Find result **count = 0 skips POST** (If branch); no longer send empty values. That kills the 08:00:46 400 and the top “sync failed”.
- `accrual` metrics keep “today Sum”; ingest already lands time with `received_at`; the card uses that for `as_of_time`.
- After generate, maintainer re-exports on Mac and replaces the Shortcut on iPhone (existing flow).

### 5b.4 ingest (do not touch the sleep path)

- Empty values still fail-closed 400 (principle unchanged), but receipt `error` distinguishes `empty_sample` (Shortcut got nothing) vs `unreadable_value` (bad value); full-card top copy writes “Health has no resting HR yet today” rather than “sync failed”. After the Shortcut is fixed this should rarely appear, but keep it.
- Accept `rhr` / `hrv_sdnn` per-sample with `timestamp`; `daily_key` aggregate by `timestamp` local day.

### 5b.5 Fact card (`fact_card.py` / `fact_card_prefs.py` / `fact_card_html.py`)

- `FactCardMetricSpec` carries `temporal`; `_metric_row` takes values by kind; new output fields `day` (already exists), `freshness`, `partial_day`, `as_of_time`, `n_days`.
- `fact_card_numeric_atoms` includes each row’s `day`, `as_of_time` (HH:MM), else P9.1 date audit would treat “9月7日” as off-card.
- Copy templates three sets by kind; `compose_assessment_summary` card-level composite: whether `partial_day` and `prior_day` rows vote → see §6 decision 8.
- P9.1 manifest build: each entry’s anchor uses that row’s actual `day`; accrual partial rows add `·截至HH:MM`.

### 5b.6 Selfcheck

RHR only has a D-1 row → show D-1 date, `freshness=prior_day`, has band; only D-3 (beyond 2 days) → “none”; accrual today has a stub → `partial_day=true`, unbanded, copy contains “截至”; `rolling_mean` 7 days 5 rows → mean + `n_days=5`; notification lead contains “prior-day” count; invariant: any `day != calendar_day` row copy has no “今日”; Shortcut plist: RHR Find has last-2-days predicate and Get Details Start Date; all quantity Shortcuts have count=0 skip branch; ingest selfcheck: empty receipt `error=empty_sample`.

### 5b.7 Docs

PRD §4.1 that line becomes “take values by registry `temporal` declaration and write the actual date / as-of time; empty only beyond the freshness window; never label a non-today value as today”; FR-2.1 / FR-2.2 in sync; §11 records decisions 7–9; `wearable-metric-registry-v1.md` adds `temporal` field notes; `pha-ios-proactive-change-log.md` entry; `pha-fact-card.md` table adds a “freshness” row.

---

## 5c. M1-P11 Checkboxes as seen + Shortcut full-set sync

### 5c.1 Possibility analysis

**Problem H (card ≠ checkboxes)**: pure software, no physical limit. Drop implicit expand.

**Problem I (changing checkboxes without reinstalling the Shortcut)**, exclude one by one:

| Path | Feasibility | Conclusion |
|------|-------------|------------|
| Refresh browser alone gets **new data** | Mac cannot reach HealthKit (PRD §1.4 physical data fact); refresh can only recompute numbers already in the ledger | **Impossible** to get new data; but for metrics with history already in the ledger (e.g. steps 9/4–9/5, all zip history), refresh shows them; that half is naturally true |
| Shortcut at runtime asks Mac for the list then “Find by list” | iOS “Find Health Samples” type is a static parameter, cannot be a text variable | **Impossible** as a generic loop |
| **A. Shortcut covers the full set; card filters by checkboxes** | Generator emits Find for registry `eligible ∧ shortcut_health_type` full set (currently 4: steps / active energy / resting HR / HRV; sleep Shortcut is already a whole pack), no longer reads prefs; checkboxes only affect card display and assessment | **Feasible and simplest**. Change checkboxes → refresh switches; newly checked same-day values appear after the next Shortcut run (timed or manual); only when the registry adds a new `shortcut_health_type` (e.g. SpO2) need one reinstall. Cost: one extra Find per run (seconds), ledger stores metrics the user is not currently looking at — which matches §1.3a “all comparable history”, baselines accumulate early. **Conflict**: FR-1.5 original “for user-selected… items” vs `pha-fact-card.md` “generate from current checkboxes” |
| **B. Full-set Find + runtime If gated by server plan** | Shortcut starts with `Get Contents of URL` to `GET /proactive/fact-card/prefs`; each Find wrapped in If “list contains this id” | Feasible, does not change FR-1.5; but only “rerun Shortcut takes effect”, not “refresh takes effect”; unchecked metrics not ingested, baselines do not accumulate; plist complexity doubles, one more network fail point; when Mac is unreachable the whole Shortcut already fails |
| C. Wait for M2 App to read prefs and decide sync items | App stage solves it naturally | Does not solve now |

**Maintainer 2026-09-08 08:27 locked A** (reasons in §6 decision 11). B no longer considered.

### 5c.2 Approach (per A)

- **Registry**: delete `fact_card.reveal_when_selected` on the five sleep-stage rows; keep `include_when_selected` (it only serves whole-pack sleep Shortcut sync; data-layer semantics; does not affect card display). `wearable-metric-registry-v1.md` line 64 delete or mark deprecated.
- **`fact_card_prefs.resolve_metric_specs`**: drop the “append by reveal” branch; card metric set = `sanitize_metric_ids(checkboxes)`, order by checkboxes. Delete `FactCardMetricSpec.reveal_when_selected`.
- **`healthkit_sync_plan.shortcut_sync_specs`**: no longer read prefs; return registry full set (`eligible ∧ shortcut_health_type ∧ ingest_key`). Sleep `shortcut_sleep_specs` likewise whole-pack (already close). Keep Sum-before-Average sort.
- **`build_pha_ingest_shortcuts.py`**: call site no longer passes user_id checkbox semantics; generated name unchanged; “Show Result” lists which metrics this run synced. Change together with P10 last-2-days / count=0 skip; **one reinstall**.
- **HTML**: `catalog` hint three-state: “synced by health Shortcut”, “synced by sleep Shortcut”, “no Shortcut sync yet, history only”; footer copy becomes “checkboxes only decide card display and assessment; data is synced by Shortcut from the full set. After changing checkboxes, refresh; newly checked same-day values appear after the next Shortcut run”. Fix the current wrong hint that marks “睡眠总时长” as “display only, Shortcut not syncing” (it is derived by the sleep Shortcut).
- **Notification lead / assessment**: coverage denominator automatically becomes checkbox count; no extra change.
- **P9.1 cache key** already includes metric digest; old interpretation auto-invalidates after checkbox change.

### 5c.3 Selfcheck

Check 5 → `facts.metrics` exactly 5 rows in checkbox order; `coverage_total == 5`; unchecked REM appears in none of facts / assessment / notification; checking only “deep” no longer brings “in bed”; `shortcut_sync_specs` independent of prefs (same before/after prefs change) and equals registry full set; generated plist has 4 quantity Finds; `sleep_time_asleep` catalog hint is “synced by sleep Shortcut”. Existing asserts “prefs save should keep catalog order” “sync plan must be selected ∩ quantity types” must become the new contract.

### 5c.4 Docs

PRD FR-1.5 / FR-2.7 / §4.1 data-integrity paragraph / §8 / §11 / §12 **already written in v1.7; do not rewrite wording**; executing agent only: after done, §8 `M1-P11` status `TODO → DONE` and fill the completion record; `pha-ios-proactive-change-log.md` add an entry (class: registry / Shortcut generator / fact-card prefs; evidence; rollback); `pha-fact-card.md` “PHA 同步健康” section already rewritten to full-set contract — after land, check once against the actual generated artifact; `wearable-metric-registry-v1.md` line 64 delete. Do not change M1-P5 historical entries.

### 5c.5 Execution checklist (P10 + P11 same agent, check in order)

Prep: read this file §0–§3, §5b, §5c; `git status` matches §0; **do not commit**.

1. **Registry** (`storage/registry/wearable_metric_registry.json`)
   - Five sleep-stage rows delete `fact_card.reveal_when_selected`; keep `include_when_selected`.
   - Per §5b.1 add `fact_card.temporal` to each eligible metric (P10).
   - `python3 scripts/pha_wearable_registry_selfcheck.py` green (if it validates the `fact_card` field set, also accept `temporal` and drop `reveal_when_selected`).
2. **prefs resolve** (`pha/fact_card_prefs.py`)
   - `resolve_metric_specs` drop reveal-append branch; return = `sanitize_metric_ids(checkboxes)` in checkbox order.
   - Delete `FactCardMetricSpec.reveal_when_selected`; grep the repo for leftover refs.
   - `catalog_specs` hint field three-state (§5c.2 HTML); `derived_from_asleep_stages` maps to “synced by sleep Shortcut”.
3. **Sync plan** (`pha/healthkit_sync_plan.py`)
   - `shortcut_sync_specs()` no longer calls `load_enabled_metric_ids`; return registry `eligible ∧ shortcut_health_type ∧ ingest_key` full set, Sum before Average.
   - `shortcut_sleep_specs()` likewise whole-pack.
   - Keep `user_id` in the signature so callers do not break, but the body does not use it; docstring “independent of checkboxes (FR-1.5 v1.7)”.
4. **Shortcut generator** (`scripts/macos/build_pha_ingest_shortcuts.py`)
   - Quantity Shortcut: full-set Find; `daily_lagged` items per §5b.2 last `freshness_days` with sample dates; `count == 0` skip POST.
   - “Show Result” lists metrics actually synced/skipped this run.
   - Generate → local import verifies plist opens; **deliver once** to the maintainer for reinstall.
5. **ingest** (`pha/healthkit_ingest.py` quantity path; sleep path untouched)
   - Per §5b.3 accept dated samples; still reject empty.
6. **Fact card** (`pha/fact_card.py` / `fact_card_html.py`)
   - Coverage denominator automatically = checkbox count; confirm nowhere still references reveal.
   - HTML footer: “checkboxes only decide card display and assessment; data is synced by Shortcut from the registry full set. After changing checkboxes, refresh; newly checked same-day values appear after the next Shortcut run.” Delete “after changing checkboxes, regenerate the Shortcut on Mac”.
   - P10 actual date / in-progress marks per §5b.4.
7. **Selfcheck** (`scripts/pha_fact_card_selfcheck.py` + Shortcut generator selfcheck)
   - All §5c.3 asserts + all §5b.6 cases; change old assert “sync plan must be selected ∩ quantity types”.
   - `python3 scripts/pha_fact_card_selfcheck.py` PASS.
8. **Restart + browser**: `bash scripts/pha_restart_accept.sh`; open full card: check 5 → card 5 rows, “N of 5 selected have values”; uncheck “deep” → refresh → 4 rows, no other stages; check “steps” → refresh → immediately show history (9/4, 9/5 have values), same-day “none” until next Shortcut run.
9. **Docs**: §5c.4; PRD §8 P10 / P11 → DONE; change-log two entries (P10, P11 may combine).
10. **Deliver to maintainer**: one sentence “need to replace ‘PHA 同步健康’ once on iPhone; after that, changing checkboxes no longer needs it”.

---

## 5. M1-P9.2 concrete approach (fact-card side only)

### 5.1 Three-layer date/time rules

- **Machine layer always ISO 8601**: storage, `GET /proactive/fact-card` JSON, cache key, audit compare unchanged.
- **Display layer renders by locale; the user does not pick a date format, only a language**. prefs add `locale` (`zh-CN` / `en-US`, default see §6 decision 2); source priority: prefs > request `Accept-Language` > default. Same value passed to `stream_pha_chat_events(response_locale=…)`.
  - zh-CN: `9月7日`; year only when crossing years `2025年12月31日`; range `6月10日–9月7日`; time `9月7日 23:29`.
  - en-US: `Sep 7, 2026`; range `Jun 10 – Sep 7, 2026`; time `Sep 7, 23:29`.
  - **Any language forbids pure numeric slash format** (`09/07` US/UK ambiguous); selfcheck regex asserts HTML has no `\d{1,2}/\d{1,2}`.
- **LLM text layer prefers relative expressions** (already required in 4.3 TASK).

### 5.2 Change points

- `fact_card_html.py`: `generated_at`, `facts.ingest_last.at`, `facts.healthkit.last_timestamp`, header `as_of` / `calendar_day` all through one locale-aware display function; timezone is Mac system timezone (prefs may add `timezone` override, default not); minute precision. JSON unchanged.
- Interpretation block: model name + “generated at 9月7日 23:29”; body may strip Markdown mark characters `*`, `#`, backticks (strip marks only, **must not change any number or date**), or rely on 4.3 plain-text instruction; recommend both.
- Failed-state button text “Retry”; fail reason one human sentence plus the rejected token: `audit_rejected` → “the model wrote a number not on the card (100); the whole segment was dropped”; `model_unavailable` → “local model did not respond”.
- Unify band label and copy direction: either labels become numeric-direction words (“above / typical / below”) and quality goes to copy, or labels keep quality direction but become words without high/low (“harder / typical / off”). Prefer the former, consistent with P7 copy “above your last 12 months…”.
- Render P10 new fields: `prior_day` row date in locale format after the value; `partial_day` row shows “as of HH:MM”.
- Notification body `as_of` date format **this card does not change** (selfcheck and Shortcut copy depend on ISO); whether to localize is §6 decision 5.

### 5.3 Selfcheck

zh render contains “9月7日” and not `T15:29`; en render contains `Sep 7`; neither contains slash dates; JSON `facts.as_of` still ISO; `interpretation.generated_at` still ISO (display conversion does not write back).

---

## 6. Needs maintainer lock (defaults; execute defaults if no reply)

| # | Decision | Default |
|---|----------|---------|
| 1 | 90-day window conflict: A = interpretation profile forbids `WEARABLE_90D_SUMMARY`, use only the card’s progressive baseline; B = harness wearable T0 summary as a whole becomes progressive window and must carry n | **A**. B affects all Q&A contracts; separate harness card |
| 2 | `locale` default | **en-US (git / OSS)**. Maintainer local prefs may still be zh-CN. 2026-09-08 overrides original “default zh-CN” |
| 3 | Withdraw or keep the card-side second audit | **Keep**, but redo per 4.4 as date/number two steps with no threshold. Neither consensus allows “delete audit because redundant” |
| 4 | Expose `profile_override` on public `/api/chat` | **Do not expose**, internal call only; exposing needs a separate decision and PRD §11 |
| 5 | Localize notification body dates | **Decide at P9.3**; this round ISO stays |
| 6 | True-test “model unavailable” needs stopping Ollama | Stopping Ollama is not a PHA restart red line, but please the maintainer confirm a time window |
| 7 | **Change a frozen line**: PRD §4.1 “missing same-day row stays empty, do not backfill” → “take values by registry freshness semantics and write the actual date; empty only beyond window; do not label a non-today value as today” | **Agree to change**. Principle “do not pose” stays; only unbind “do not display” |
| 8 | Does card-level composite vote accept `prior_day` / `partial_day` rows | `prior_day` **accept** (resting HR is already last-night-to-this-morning); `partial_day` **do not** (stubs must not vote) |
| 9 | HRV `temporal.kind` | **`overnight`**: Apple Watch SDNN is mainly measured in sleep; morning value can be treated as “this night”; but registry must write `min_samples` (suggest 2); below that mark “few samples, unbanded for now”. If the maintainer trusts Health’s “same-day mean” more, change to `accrual`, cost morning forever unbanded |
| 10 | `daily_lagged` `freshness_days` | **2**; resting HR older than 2 days has no reference value for “how to train today” |
| 11 | **Change FR-1.5**: Shortcut from “generate from user-selected” to “generate from registry full set, card filters by checkboxes” (§5c option A); meanwhile P10 lets resting HR POST “last 2 days samples with dates”, touching FR-1.5 “forbid Find raw lists” literally | **Maintainer 2026-09-08 08:27 locked: agree A. Written into PRD v1.7 FR-1.5 / §11 / §12.** Original recommend reasons: ① meets “after changing checkboxes, refresh switches, rerun Shortcut fills numbers, no reinstall”; ② ledger storing 1–2 extra metrics matches §1.3a “all comparable history”, unchecked metrics’ baselines accumulate early; ③ anti-hardcode still holds — full set from registry not code; ④ one extra Find per run, seconds. “Forbid Find raw lists” meant to stop steps raw-sample explosion; resting HR is 1 sample/day; sleep D1 already passed acceptance the same way; wording already “accrual forbids Find raw lists; once-daily type may POST per sample with date”. Option B void |
| 12 | Drop sleep-stage `reveal_when_selected` implicit expand | **Chosen for the maintainer: drop.** Per FR-2.7 “metric set specified by the user”, implicit expand makes card ≠ checkboxes, coverage denominator distorted, assessment says “missing”; change-log has no maintainer decision for that behavior; it is an implementation choice, not a consensus conflict. Want stages, check stages; sleep Shortcut whole-pack sync unaffected (`include_when_selected` kept) |

---

## 7. Suggested PRD wording (same PR as P9.1, after maintainer confirms §6)

FR-6 table add:

- **FR-6.8 Evidence source**: the interpretation’s only first-class evidence source is that day’s fact-card JSON (facts + progressive baseline + reference layer); enter harness via `fact_card_interpret` profile; Tier0 only TASK / NUMERICS_MANIFEST (built from the card) / FACT_CARD_CONTEXT / USER_ASSESSMENT_PROMPT; fixed-window summaries such as `WEARABLE_90D_SUMMARY` are forbidden on this path. Any window, n, date in the interpretation must match the card’s rule layer character-for-character. Acceptance: selfcheck injects “近 90 天” on a 365d card → reject.
- **FR-6.9 Dates and language**: machine layer ISO 8601; display layer renders by `locale`, forbids pure numeric slash dates; LLM text prefers relative expressions; absolute dates only as_of; audit treats dates as an independent word class, normalize then compare. Acceptance: HTML selfcheck both zh/en locales; `unauthorized_date` case.

§4.2 append one: “letting a fixed-window wearable summary (`WEARABLE_90D_SUMMARY`) enter the fact-card interpretation path”.

FR-6 add another row:

- **FR-6.10 Off-card number exit**: any number in the interpretation not in the fact-card manifest (intensity, HR zone, target steps, etc.) may only appear as a T1 disclosure block with a source; outside the block only qualitative description. The user assessment prompt cannot unlock this. Acceptance: selfcheck outside-block “120–140” → reject, inside T1 → pass.

FR-2 add a row (P10):

- **FR-2.10 Metric freshness semantics**: each eligible metric declares in the registry `temporal.kind ∈ {accrual, daily_lagged, overnight, rolling_mean}` and window params; the card takes values by the declaration; the row must write actual `day` or `as_of_time`; `accrual` same-day in-progress unbanded; `daily_lagged` looks back within `freshness_days` and marks “prior day”; empty only beyond window. Notification lead counts coverage by same-day / prior-day / in-progress. Forbid Python specials by metric name. Acceptance: all §5b.6 cases.

**FR-1.5 / FR-2.7 v1.7 already written into the PRD on 2026-09-08** (including §4.1 data-integrity paragraph, §8 five new cards, §11 three items, §12 v1.7 row); executing agent must not rewrite. Still for the executing agent to write with the PR: FR-6.8 / 6.9 / 6.10 (P9.1), FR-2.10 and §4.1 “missing stays empty” rewrite (P10, see §5b.7), §4.2 extra forbid (P9.1), §11 land records for decisions 1, 3, 7, 8, 9, 10.

---

## 8. Do not

- Do not use thresholds like “only block ≥N”, “only block large numbers” to get interpretation through.
- Do not stuff keywords into `user_message` to bump routing so the model mentions deep sleep; use a profile.
- Do not assemble a system prompt in `fact_card_interpret.py` to replace the profile’s TASK slot.
- Do not add a “date format” option for the user; only `locale`.
- Do not change notification-body date format (this round).
- Do not stuff `interpretation` into `assessment` or the notification.
- Do not fill yesterday’s value into today’s row or drop the “do not backfill” assert just so resting HR “has a number”; go P10 `temporal` declaration and show the actual date.
- Do not write `if metric_id == "resting_heart_rate_bpm"` in `fact_card.py`; freshness semantics only from the registry.
- Do not let ingest accept empty values and write 0 or NULL samples; empty sets skip on the Shortcut side.
- Do not replace `reveal_when_selected` with another implicit rule (e.g. “checking sleep total defaults checking stages” in prefs); card = checkboxes, not one extra word.
- Do not leave the generator a “generate from checkboxes” switch or parameter; FR-1.5 v1.7 has one contract: registry full set.
- Do not add If gates in the Shortcut “to only sync what the user cares about” (option B void).
- Do not change PRD FR-1.5 / FR-2.7 v1.7 wording; that is the maintainer-locked original.
- Do not deliver P10 and P11 Shortcut changes to the maintainer as two reinstalls.
- Do not push; do not commit until the maintainer says “commit”.

---

## 9. Live cheat sheet (2026-09-08 08:00)

- PHA `0.0.0.0:8788`, pid in `bash scripts/pha_restart_accept.sh` output; Ollama `127.0.0.1:11434` online, model `qwen2.5:7b-instruct` (`OLLAMA_MODEL`).
- DB `data/pha_storage.db`; `default` 9/8 08:00 card: as_of 2026-09-08, coverage 7/9; sleep total 6.2h (365d n=267 below), HRV 19.3 ms (n=274 below, overnight samples), deep 0.9h, REM 1.6h, awake 0.1h, core 3.7h (1/7), active energy 13.5 kcal (below, in-progress stub); **resting HR none** (9/6=60, 9/7 and 9/8 NULL); in bed none. Top “last sync failed 08:00:46 · quantity · unreadable_value” = RHR empty POST.
- 9/8 08:00 Shortcut four POSTs: three 200 and “empty timestamp; using received_at”, one `rhr` empty 400. Shortcut currently carries no sample date.
- `data/fact_card_interpret/` three caches: 9/7 23:29 done (last 90 days 7.6h), 9/8 08:01 done (last 90 days 6.9h), 9/8 08:04 failed `unauthorized_wearable_count:100`. Clear all after P9.1.
- Current prefs: checked sleep total / HRV / resting HR / deep / active energy; assessment is the maintainer 9/8 original (resting HR + HRV + deep + workout type/intensity).
- 08:12 screenshot: card lists 9, checked 5; extra 4 from registry `reveal_when_selected` (`sleep_deep / sleep_rem / sleep_core / sleep_in_bed / sleep_awake` all `[sleep_time_asleep, sleep_deep, sleep_rem]`). Quantity Shortcut current Finds: checked among steps, active energy, resting HR, HRV; `spo2_percent` / `respiratory_rate` have no `shortcut_health_type`, so under any option they can only show history.
- Related code: `pha/fact_card_prefs.py` (`resolve_metric_specs` reveal-append branch, `FactCardMetricSpec.reveal_when_selected`), `pha/healthkit_sync_plan.py` (`shortcut_sync_specs` reads `load_enabled_metric_ids`), `scripts/macos/build_pha_ingest_shortcuts.py` lines 671–673, `docs/wearable-metric-registry-v1.md` line 64.
- Entry points: `pha/fact_card_interpret.py` (`run_interpretation` / `start_interpretation` / `_unauthorized_numbers`), `pha/fact_card_api.py` (`POST/GET /proactive/fact-card/interpret`), `pha/fact_card_html.py` (`_interpret_status_html` + poll script), `pha/fact_card_prefs.py` (`assessment_prompt`).
- Harness: profile table in `pha/harness_report.py`; registry `rules/harness_profile_registry.generated.json`; manifest and date normalize in `pha/numerics_manifest.py` (`NumericsManifest.allowed_dates` about 234, `_extract_normalized_dates` about 511, `_audit_dates_and_citation` about 751); locale in `pha/response_language.py` (`resolve_response_locale`); `response_locale` already flows `chat_service` → `chat_turn_orchestrator` → `chat_turn_slots` → `chat_turn_compose`.
- Last night’s log evidence: `~/Library/Logs/pha/pha-8788.log` two rounds 23:24 and 23:29 `route=supplement_manifest`, `WARN: matrix_gap_supplement_text_matches_wearable_regex`.
- Browser acceptance URL: `/proactive/fact-card/view?user_id=default&token=<PHA_INGEST_TOKEN>`; token in `~/Library/Application Support/pha/env-8788.sh`.

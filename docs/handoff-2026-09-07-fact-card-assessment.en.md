# Handoff · Fact-card assessment layer redo (M1-P7 / P8 / P9)

> **Language / 语言**：English (this document) · [中文](handoff-2026-09-07-fact-card-assessment.md)

> For the successor coding agent · 2026-09-07 16:50 · Maintainer has approved the design; **zero lines of code yet**  
> First reply must output: `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> When touching `hrv_rmssd_ms` / numerics / skip-LLM, also: `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> Source of truth: [`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.6** (§1.3 / §1.3a / FR-2.1 / FR-2.6 / FR-2.8 / FR-2.9 / FR-6 / §8)

---

## 0. One-paragraph background

PHA’s iPhone proactive fact card already receives notifications, opens the full card, lets the user check metrics, and syncs steps / energy / resting HR / HRV / sleep (M1-P0–P6). The full card’s **assessment layer is almost empty**, only writing “personal baseline under 7 days, no banding”. The maintainer locked three decisions today:

1. **“Baseline insufficient” is wrong.** The Mac ledger for user `default` has sleep 642 nights, HRV 1936 days, resting HR 2255 days, energy 2286 days (from 2016; zip import ends 2026-06-09). `pha/fact_card.py`’s `BASELINE_DAYS = 90` looks back from `as_of`, which excludes the entire zip, so n becomes 0/1. The proactive agent is part of PHA and **must not be split from the Mac ledger**: the baseline window must progress by available volume (90d → 365d → all history) and the card must say which window was used.
2. Besides the personal baseline there must be a **generic reference layer** so the user can read the numbers on day one; format is the already-shipped `manifest-tier-v1` T1 disclosure block (`【参考标准】…（来源：…，请自行查证，非医疗建议）`). Ranges live in the registry, not hard-coded in Python. HRV absolute values **do not** get a population range.
3. Agreed: **“My assessment requirements”** (user free text) + **“button interpretation”** (LLM only after the user taps). This is not the proactive path (user tap = speaking), so it **must reuse the chat harness** (TurnEvidencePlan + Numerics audit). Bare Ollama is forbidden; pre-generation is forbidden; it must not enter the notification. M3 “in-app Q&A” therefore shrinks to the App hitting the same endpoint; order unchanged.

Incidental old account: all 11650 `wearable_data` rows with `metric_type=hrv` have `sample_id` of the form `HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…|<Watch device name>`. So the `hrv_rmssd_ms` column **has always been Apple SDNN**; the ledger never had RMSSD. Today’s on-device ingest `hrv_sdnn_ms=40.97` is the same physical quantity as those 7 years of history; only the column name blocked the baseline.

---

## 1. Work order (do not parallelize, do not skip)

| # | Card | Point | Done when |
|---|------|-------|-----------|
| 1 | **M1-P7** Progressive baseline + reference layer | Pure rules, no LLM, do not touch numerics | Full card for `default` immediately has “vs your last 12 months N nights → below/typical/above” + a reference sentence; selfcheck green |
| 2 | **M1-P8** HRV column semantics correction | Touches numeric path; stack harness ACK | Today’s SDNN matches historical baseline; skip-LLM “HRV” Q&A and numerics selfcheck green; no RMSSD wording posing as SDNN |
| 3 | **M1-P9** Assessment prompt + interpretation | ① prefs textarea (no LLM) → ② async endpoint + cache → ③ via `chat_service` → ④ HTML independent block | Tap returns “generating” in <1s; refresh shows it; stopping Ollama shows “model unavailable”; audit reject shows “not generated” |

Each card: run selfcheck → official restart `bash scripts/pha_restart_accept.sh` → look at the full card on device/browser → same PR write [`pha-ios-proactive-change-log.md`](pha-ios-proactive-change-log.md) → update PRD §8 status. **Local commit only, no push** (commit only when the maintainer says “please commit”).

---

## 2. M1-P7 concrete approach

### 2.1 Progressive baseline (`pha/fact_card.py`)

Today: `compose_fact_card` uses `rolling_n_grain(BASELINE_DAYS, baseline_end)` for one `baseline_rows` slice (excluding `as_of` day); `_metric_row` samples each metric in that same slice; `< MIN_BASELINE_N(7)` → `band="unknown"`.

Change to:

- Ordered baseline candidate windows: `("90d", 90)`, `("365d", 365)`, `("all", None)`. **Per metric** (not per card) take the first window with `len(samples) >= MIN_BASELINE_N`; only if all three fail, `unknown`.
- `_metric_row` emits two extra fields: `baseline_window` (`"90d"|"365d"|"all"|null`) plus existing `baseline_n`. `fact_card_numeric_atoms` already collects `baseline_n`; the window string is not a number and need not enter.
- Copy: every hard-coded “近90日” in `_advice` / `sleep_verify_copy` / `compose_assessment_summary` must be generated from the window: `90d → last 90 days`, `365d → last 12 months`, `all → all history (since {first-day year-month})`, with n: “vs your last 12 months 268 nights”. **Do not** leave a fixed “近90日” string.
- `unknown` copy becomes progress: “personal history {n}/7 days, not banding yet”, no longer “baseline insufficient”.
- **Merge only under the same definition**: zip vs HealthKit union definitions for `sleep_hours` / `sleep_deep_hours` / `sleep_rem_hours` / `awake_duration_hours` are consistent, so same series; `sleep_core_hours` and `in_bed_hours` are historically empty (checked: core only one day 9/7, in_bed 0 days) → naturally fall to unknown; copy may say “no history”; do not special-case.
- Card-level three-band summary (FR-2.6): add in `compose_assessment_summary`: take `band` of `sleep_hours`, HRV (the actual field after P8 `hrv_sdnn_ms`/fallback), and `resting_heart_rate_bpm`; vote “easier / typical / harder” only if all are in `{below, typical, above}`; any missing/unknown → `"no composite"`. An unchecked item among those three also counts as missing; do not silently use unselected metrics.
- Performance: `load_fact_card` currently queries 90-day rows; change to load on demand (90 first, then 365, then all) or pull all 3504 history rows once (local SQLite, acceptable). Prefer simple and readable.

### 2.2 Generic reference layer (registry + `fact_card.py` + `fact_card_html.py`)

- Under `fact_card` of each applicable metric in `storage/registry/wearable_metric_registry.json` add:
  ```json
  "reference_range": { "low": 7, "high": 9, "unit": "h", "source": "National Sleep Foundation 成人建议", "note": "常见建议范围" }
  ```
  v1 suggested fills: sleep total 7–9 h; deep as share of asleep 13–23%; REM as share of asleep 20–25%; resting HR 60–100 bpm; steps 7000–10000. **Do not fill HRV, awake, in bed, core.** Ratio kinds need `kind: "ratio_of", "of": "sleep_hours"` — if that is too tangled, v1 only do the four absolute items (sleep total, RHR, steps); leave ratios as TODO in the change-log; do not force it.
- `fact_card_prefs.FactCardMetricSpec` gains a field to carry it; `_metric_row` emits `reference: {"low","high","unit","source","status": "within|below|above"}`; `fact_card_numeric_atoms` includes low/high (otherwise full-card numbers ⊆ JSON selfcheck goes red).
- Copy strictly uses the T1 block format (`pha/numerics_manifest.py` has regex `【参考标准[^】]*】…（来源：…，请自行查证，非医疗建议）`, reusable for selfcheck):  
  `【参考标准】成人睡眠常见建议 7–9 h，你今日 7.6 h 在范围内（来源：National Sleep Foundation，请自行查证，非医疗建议）`
- HTML: one small line under each rule-assessment item; no red/green coloring (avoid a diagnostic feel).

### 2.3 Selfcheck (`scripts/pha_fact_card_selfcheck.py`)

New cases: 90d empty, 365d has 30 rows → `baseline_window="365d"` and band not unknown; all three empty → unknown and copy contains `/7`; `reference.status` three-state; HRV has no `reference`; copy contains no hard “近90日”; card-level composite missing item → “no composite”.

---

## 3. M1-P8 concrete approach (stack harness ACK)

- First run and save baselines: `python3 scripts/pha_numerics_manifest_selfcheck.py`, skip-LLM selfcheck, `python3 scripts/pha_fact_card_selfcheck.py`.
- Pick one scheme (write why in the change-log):
  - **A. Migrate**: copy historical `wearable_daily.hrv_rmssd_ms` into `hrv_sdnn_ms` (only when `hrv_sdnn_ms IS NULL`); change `wearable_data` `metric_type='hrv'` to `hrv_sdnn`; delete or mark `deprecated` the `hrv_rmssd_ms` registry row; drop `display_fallback_metric_id` / `include_when_selected`.
  - **B. Rename**: keep the column; change registry `hrv_rmssd_ms` label to “HRV (SDNN, historical)” and `merge_into: hrv_sdnn_ms`.
  - Recommend A: one-shot, no further explaining. Migration script in `scripts/`, idempotent, `--dry-run` prints counts first.
- Migrate only rows whose `sample_id` contains `HeartRateVariabilitySDNN`; future third-party true RMSSD samples are unaffected.
- Regression: skip-LLM path for “how is my HRV” must take numbers from the new column; fact-card HRV row `baseline_n` should be ≥ 200 (274 in last 365 days).

---

## 4. M1-P9 concrete approach

### 4.1 My assessment requirements (no LLM)

- `data/fact_card_prefs.json` gains per-user `assessment_prompt: str` (may be empty). Extend `fact_card_prefs.py` `prefs_payload` / `save_*`; extra field on `PUT /proactive/fact-card/prefs` body (`fact_card_api.FactCardPrefsBody`).
- HTML full card bottom: “My assessment requirements” textarea + save; refresh echoes. Length cap 2000 characters, over → 400.
- The rule layer **does not read** this field.

### 4.2 Interpretation endpoint (async + cache)

- `POST /proactive/fact-card/interpret?user_id=` (same ingest token): read current card JSON + prefs; `key = sha256(user_id|as_of|assessment_prompt)`; if cache `data/fact_card_interpret/{key}.json` exists, 200 return it; else write `status=pending` and start a background thread/task, 200 `{status:"pending"}`.
- `GET /proactive/fact-card/interpret?user_id=`: return `{status: pending|done|failed, text, model, generated_at, error}`.
- **Generation path**: call `pha.chat_service.stream_pha_chat_events(user_id=…, user_message=<fixed instruction + user assessment_prompt>, model=<configured local model>, extra_system_context=<facts JSON + baseline summary + reference layer, labeled “the following numbers are the only citable numbers”>, session_id=None)`, collect SSE until final. TurnEvidencePlan / Compose / Numerics audit then apply naturally. **Do not** import the Ollama client directly.
- Audit: if the final event carries a violation (`unauthorized_value` class) → `failed` + `error="audit_rejected"`; exact numbers outside facts ∪ baseline ∪ reference range also reject (extra allowlist check via `fact_card_numeric_atoms`). T1 blocks (`【参考标准…`) are allowed.
- Ollama down / timeout → `failed` + `error="model_unavailable"`. Rule layer continues as usual; **never** use template text posing as AI interpretation.
- Cache key includes `as_of`, so it expires the next day; changing the requirements text also invalidates.

### 4.3 HTML

- After rule assessment, a new independent block “AI interpretation (experimental) · not medical advice”: button “Generate interpretation” → fetch POST → poll GET (every 5s, up to 4 minutes) → render `text` + “model {model} · {generated_at}”. pending shows “generating; you can close and refresh later”; failed shows the reason.
- Notification body / `assessment` never contain interpretation; `GET /proactive/fact-card` JSON puts interpretation at top-level `interpretation` (`null` when uncached), not inside `assessment`.

### 4.4 Selfcheck

- Fake chat pipeline (monkeypatch `stream_pha_chat_events`): return with foreign numbers → failed/audit_rejected; return with T1 block → done; throw → failed/model_unavailable.
- Without tapping the button, JSON `interpretation is None` and no LLM call.
- Second POST with the same key does not trigger a second generation.

---

## 5. Do not

- Do not replace “近90日” with another hard-coded number; the window must progress and be written into JSON.
- Do not invent numbers to make assessment “have content”, use yesterday for today, or pad the composite with unchecked metrics.
- Do not put LLM text in the notification; do not pre-generate; do not bypass `chat_service` to talk to Ollama.
- Do not change `packages/harness_core`; do not change public README narrative; do not push.
- Reference ranges do not enter Python constants; they enter the registry. No population range for absolute HRV.
- Before P8 migration, do not merge `hrv_rmssd_ms` and `hrv_sdnn_ms` into one baseline on the fact card (existing fallback is display-only, not a merge).

---

## 6. Live facts cheat sheet (2026-09-07 16:45)

- PHA on `0.0.0.0:8788`; restart only with `bash scripts/pha_restart_accept.sh`.
- DB: `data/pha_storage.db`; `default` `wearable_daily` 3504 rows (2016-09-26–2026-09-07).
- Today on device: 9/7 asleep 7.60 / awake 3.45 / core 4.90 / deep 1.65 / REM 1.05 / in bed empty; 9/6 SDNN 40.968, RHR 60, energy 703.6.
- Fact-card entry points: `pha/fact_card.py` (`compose_fact_card`, `_metric_row`, `compose_assessment_summary`), `pha/fact_card_prefs.py`, `pha/fact_card_api.py` (`/proactive/fact-card`, `/view`, `/prefs`), `pha/fact_card_html.py`, `scripts/pha_fact_card_selfcheck.py`.
- Sync receipt (T7) already shipped: `GET /ingest/healthkit/last`, full-card top “last sync”.
- Chat pipeline entry: `pha.chat_service.stream_pha_chat_events` → `chat_turn_orchestrator.orchestrate_chat_turn_events`; `/api/chat` is its SSE shell.
- T1 disclosure regex: `pha/numerics_manifest.py` (`block_open_re`, `t1_disclosure_incomplete`).
- Sleep M1-P6 is still IN_PROGRESS (owes consecutive-nights acceptance T9); parallel to this handoff, neither blocks the other; do not change the sleep path in `pha/healthkit_ingest.py`.

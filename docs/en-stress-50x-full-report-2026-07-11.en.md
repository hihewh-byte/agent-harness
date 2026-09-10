# PHA full English stress-test report (50×≥8)

> **Language / 语言**：English (this document) · [中文](en-stress-50x-full-report-2026-07-11.md)

- **Dates**: 2026-07-11 ~ 2026-07-12 (UTC start `20260711T121936Z`)
- **Endpoint**: `http://127.0.0.1:8788` · build `pha-v2.3.32-full-import-only`
- **Model**: `qwen2.5:7b-instruct` · `response_locale=en`
- **Bank**: `rules/e2e_question_bank_en_v1.json` (seed=`20260711`)
- **Assets**: jun11 `IMG_690*` six-panel wearable screenshots · `IMG_0313` lab/report image · existing warehouse lipid/wearable samples
- **Wall clock**: 15527.6s (about 4.31 hours)
- **Artifacts**: `reports/e2e/` (JSONL / auto MD / plan / manifest / runner.log)

## 1. Verdict overview

| Metric | Value |
|------|------|
| Sessions | **50/50** completed |
| Turns | **409** (each session ≥8, some 9–10) |
| Turn pass | **134** (32.8%) |
| Turn fail | **275** (67.2%) |
| All-green sessions | **7/50** |
| API errors | **1** |
| Empty answers | **0** |
| Non-English (CJK>12%) | **272** |
| Wearable metric mis-ledger | **0** |

**Verdict**: the stress run **executed fully** (50 sessions × ≥8 turns of all-English input), but **fail rate is high** under the “reply must be English” hard gate. The main cause is not a path crash (API error=0). It is that **deterministic CompareTable / weak-followup templates are still hardcoded Chinese**, so RLP (`response_locale=en`) does not cover non-LLM fast paths.

## 2. Plan recap

| Block | Count | Focus |
|------|------|------|
| EN01–EN20 | 20 | Classic upload / warehouse English mirrors |
| EN21–EN35 | 15 | Warehouse tour, PDF/lab, body-age, supplement, rapid |
| EN36–EN50 | 15 | combined review, locale lock, mixed assets, finale |

Pass standard: non-empty answer · CJK≤12% · wearable ingest jun11 KPI alignment · no API error.

## 3. Failure taxonomy

| Check prefix | Count | Meaning |
|------------|------|------|
| `non_english_cjk_ratio` | 272 | |
| `reintroduced_full_table_on_followup` | 13 | |
| `correction_missing_6h_sleep_en` | 2 | |
| `api_error` | 1 | |

### Template hits (answer body)

| Template fragment | Hit turns |
|----------|----------|
| Weak-followup caution “关于您还需留意的事项” | 134 |
| metric focus “关于您关心的指标” | 52 |
| CompareTable “根据您上传的 Apple Watch 截图” | 42 |
| Warehouse Chinese 90-day opener | 0 |
| Warehouse English 90-day opener (fixed this run) | 36 |

**Key bug pattern**: many weak-followup / closing turns (Thanks / OK / Got it) return the same Chinese caution (respiratory-rate range + workout count) in ~0.2–5s, forming **134** template-spam turns. That violates both the English gate and dialog relevance.

## 4. Path split

| Path | Turns | Notes |
|------|------|------|
| Fast path `<8s` (mostly deterministic templates) | 199 | English-failure concentration |
| Slow path `≥8s` (mostly LLM / reassemble) | 210 | English pass rate significantly higher |
| Wearable-attachment turns | 35 | jun11 six-panel |
| Lab-image attachment turns | 2 | IMG_0313 |

Slow-path English pass examples (excerpt):
- `EN03_upload_lipid_clarify T6` (67.8s): Based on the data from your Apple Watch screenshots and the injected WEARABLE_COMPARE_TABLE, here is a point-by-point an…
- `EN06_upload_workout_probe T7` (68.9s): Based on the latest wearable data and the past 90 days, here are some key points to consider:  ### Key Metrics Compariso…
- `EN07_warehouse_hrv T1` (1.6s): From your ~90-day health records:  - **Mean HRV**: 33.54ms (2026-04-13~2026-07-11)…

## 5. Session / Lane summary

Full table: auto report `en_stress_50x_20260711T163824Z.md`. Lane fail density (fails/turns):

| Lane | Sessions | Turns | Fails | Fail% |
|------|----------|-------|-------|-------|
| warehouse_then_upload | 2 | 16 | 13 | 81% |
| upload_rapid | 1 | 10 | 9 | 90% |
| mixed_prior_assets | 1 | 8 | 8 | 100% |
| stress_finale | 1 | 10 | 8 | 80% |
| upload_body_age | 1 | 8 | 8 | 100% |
| upload_clarify_years | 1 | 8 | 8 | 100% |
| upload_closing_polite | 1 | 8 | 8 | 100% |
| upload_delta_focus | 1 | 8 | 8 | 100% |
| upload_exercise_chain | 1 | 8 | 8 | 100% |
| upload_holistic_chain | 1 | 8 | 8 | 100% |
| upload_hrv_delta | 1 | 8 | 8 | 100% |
| upload_long | 1 | 10 | 8 | 80% |
| upload_metric_tour | 1 | 8 | 8 | 100% |
| upload_remerge | 1 | 8 | 8 | 100% |
| upload_reparse_loop | 1 | 8 | 8 | 100% |
| upload_respiratory | 1 | 8 | 8 | 100% |
| upload_resting_hr | 1 | 8 | 8 | 100% |
| upload_running | 1 | 8 | 8 | 100% |
| upload_sleep_correct | 1 | 8 | 8 | 100% |
| upload_spo2_sleep | 1 | 8 | 8 | 100% |
| upload_supplement_bridge | 1 | 8 | 8 | 100% |
| upload_then_pdf_bridge | 1 | 8 | 8 | 100% |
| upload_weak_then_metric | 1 | 8 | 8 | 100% |
| upload_hr_spo2_combo | 1 | 8 | 7 | 88% |
| upload_lipid_clarify | 1 | 8 | 7 | 88% |
| upload_spo2_chain | 1 | 8 | 7 | 88% |
| upload_spo2_deep | 1 | 8 | 7 | 88% |
| upload_workout_probe | 1 | 8 | 7 | 88% |
| lab_then_wearable | 1 | 8 | 6 | 75% |
| upload_casual_weak | 1 | 8 | 6 | 75% |
| upload_hr_generic | 1 | 8 | 6 | 75% |
| formal_heavy_warehouse | 1 | 8 | 5 | 62% |
| upload_exercise_caution | 1 | 8 | 5 | 62% |
| warehouse_tour | 1 | 8 | 5 | 62% |
| combined_review | 1 | 8 | 4 | 50% |
| upload_summary | 1 | 8 | 4 | 50% |
| lab_image_chain | 1 | 8 | 3 | 38% |
| warehouse_steps | 1 | 8 | 2 | 25% |
| english_locale_lock | 1 | 8 | 1 | 12% |
| prior_sample_replay | 1 | 8 | 1 | 12% |
| warehouse_lipid_deep | 1 | 8 | 1 | 12% |
| warehouse_sleep_deep | 1 | 8 | 1 | 12% |
| pdf_lab_warehouse | 1 | 8 | 0 | 0% |
| rapid_warehouse | 1 | 9 | 0 | 0% |
| warehouse_compare_weeks | 1 | 8 | 0 | 0% |
| warehouse_hrv | 1 | 8 | 0 | 0% |
| warehouse_lipid | 1 | 8 | 0 | 0% |
| warehouse_only_long | 1 | 10 | 0 | 0% |
| warehouse_spo2_resp | 1 | 8 | 0 | 0% |

## 6. Confirmed effective / ineffective

### Effective
- The all-English bank can drive 50×≥8 independent sessions; attachment upload and warehouse query paths are stable (**0 API error**).
- Warehouse single-metric skip path can emit English after restart: `From your ~90-day health records` (see this-run patch in `pha/grounded_answer_composer.py`).
- LLM long answers mostly stay English under explicit `response_locale=en` (finale / lipid analysis, etc.).

### Ineffective / to fix (P0)
1. **CompareTable / metric_focus / weak_caution templates are not bilingual** (`wearable_compare_table_v1.py` etc.) — they ignore `response_locale`.
2. **Weak-followup relevance collapse**: Thanks/OK repeatedly replay the same caution instead of a light thank-you path.
3. **Sleep-verify English assertion**: occasional `correction_missing_6h_sleep_en` (narrative mixes zh/en screenshot fields).
4. **LLM occasional zh/en mix** (even with locale=en); strengthen the RLP system directive or a post language gate.

## 7. Loop Engineering / Reflection (auto iteration)

See: `docs/rfcs/rfc-loop-reflection-auto-evolution.md`

Landing suggestions (tied directly to this JSONL):

1. **Harvest**: write `non_english_cjk_ratio` / caution spam / sleep-verify failures from this report’s JSONL into `reports/loop/slow_round_candidates.jsonl`.
2. **Reflection Critic**: propose by taxonomy — Layer 1 only: English composer copy, catalog EN aliases, weak-followup skip rules; **forbid** changing the routing state machine.
3. **Verify**: EN07 / EN15 / EN50 subset regression + selfcheck; Nightly after human-reviewed PR.
4. **Cross-product**: PHA / tax_agent / HIO-A share the Harvest→Proposal→CI veto skeleton; each product only fills domain catalog and Critic rubrics.

## 8. Suggested next actions

1. P0: deterministic templates fully honor `response_locale` (CompareTable opener, focus, caution, follow-ups).
2. P0: weak followups (thanks/ok/got it) must take a light English reply; forbid caution replay.
3. P1: Nightly 10 EN sets; Weekly full 50.
4. P1: implement `pha_reflection_critic.py`, using these 409 turns as the first corpus.

## 9. Artifact index

| File | Path |
|------|------|
| Full JSONL | `reports/e2e/en_stress_50x_20260711T121936Z.jsonl` |
| Auto session table | `reports/e2e/en_stress_50x_20260711T163824Z.md` |
| Plan | `reports/e2e/plan_en_stress_50x_20260711T121936Z.md` |
| Question manifest | `reports/e2e/question_manifest_20260711T121936Z.json` |
| Runner log | `reports/e2e/runner.log` |
| English bank | `rules/e2e_question_bank_en_v1.json` |
| Runner script | `scripts/pha_e2e_en_stress_50x.py` |
| Loop/Reflection RFC | `docs/rfcs/rfc-loop-reflection-auto-evolution.md` |

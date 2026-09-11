# Harness Change Log

> **Language / 语言**：English (this document) · [中文](harness-change-log.md)

## 2026-09-11 (P0: CHB lineage stub regex flags)

- **Category**: **P0 (chat SSE / HTTP 0)**. Field: compare two-day HRV + which supplements in use → `request failed HTTP 0` / `global flags not at the start of the expression at position 25`.
- **Change**: `_LINEAGE_WINDOW_STUB_RE` moves `(?i)` to `re.compile(..., re.I)`. Python 3.11+ rejects inline flags after the first alternative; wearable turns that mount `USER_CONTEXT_BRIEF` import `chb_compiler` and crash; orchestrator SSE's the `re.error`. build `pha-v2.3.47-lineage-stub-re-flags`.
- **Evidence**: `python3.12` reproduces `re.error`; `pha_chb_compiler_selfcheck` (incl. `test_lineage_window_stub_regex_compiles`).
- **Rollback**: revert to v2.3.46 (chat HTTP 0 returns).

## 2026-09-11 (P1: M1-P15 → DONE)

- **Category**: **P1 (§8 stamp)**. Maintainer: fixture-med unfit for training gold; `slot_named_ge2` 5/10 acceptable.
- **Change**: docs closeout PRD v1.22; **no** harness code change. Deferred audit/rate/prefs open later. No git in this chat.

## 2026-09-11 (P1: named-day enumerate + wearable CHB background)

- **Category**: **P1 (chat evidence / FR-6.14)**.
- **Change**: Time grain unions relative + calendar grammar point days (no single-winner); |D|≥2 enumerates into Manifest; `WEARABLE_90D_SUMMARY` stays last 90 days. Wearable turns mount `USER_CONTEXT_BRIEF` when supplement schema positive score meets threshold; projection is §Background only. build `pha-v2.3.46-named-days-chb-brief`.
- **Evidence**: `pha_healthkit_ingest_selfcheck` grain cases; `pha_chb_compiler_selfcheck` projection + slot mount.
- **Rollback**: revert to v2.3.45.

## 2026-09-11 (P1: active energy / steps cross-source double-count)

- **Category**: **P1 (daily rollup)**.
- **Change**: `active_energy` per-source then max; drop `healthkit` daily when ≈ multi-device sum; Shortcut step multi-value without covering Sum → max. build `pha-v2.3.44-additive-max-source`.
- **Evidence**: `pha_wearable_daily_aggregator_selfcheck` PASS; today card 355.6 kcal / 6963 steps.

## 2026-09-11 (P1: population_commons + gold gate)

- **Category**: **P1 (FR-6.10 / FR-6.12)**.
- **Change**: Manifest commons domain; gold gate ≥2 brief items. build `pha-v2.3.45-p15-commons-gate`.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py`; `reports/p15_eval/runs_v244_commons_gold10.jsonl`.

## 2026-09-11 (P1: ctx-min + drop % bait + think control)

- **Category**: **P1 (FR-6.12)**.
- **Change**: `slot_start` min; TASK item 3 drops 70–80%; brief schema hygiene; timeout 300. build `pha-v2.3.43-p15-ctxmin-think`.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py`; `reports/p15_eval/runs_v243_ctxmin_think_gold5.jsonl`.

## 2026-09-11 (P1: CHB-path gold × 10 — still not DONE)

- **Category**: **P1 (FR-6.12 acceptance)**.
- **Evidence**: `brief_source=chb`×10; dual-named 0/10; hard Markdown 9/10; audit reject 7. **Do not** mark DONE.

## 2026-09-11 (P1: CHB one-item rows + slot adjacency)

- **Category**: **P1 (FR-6.12)**.
- **Change**: copy/schema carry `item_seps`/`row_caps`; assemble brief next to assessment prompt; acceptance asserts `brief_source=chb`. build `pha-v2.3.42-p15-chb-itemrows`. P15 still IN_PROGRESS.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py`; `reports/p15_eval/run_p15_batch.py`.
- **Rollback**: restore v2.3.41.

## 2026-09-11 (P1: named-prose gold × 20 — still not DONE)

- **Category**: **P1 (FR-6.12 acceptance)**.
- **Evidence**: dual-named 0/20; Markdown 19/20; audit reject 6; prefs unchanged. **Do not** mark DONE.

## 2026-09-11 (P1: named-prose slot wording + continuous prose)

- **Category**: **P1 (FR-6.8 / FR-6.12)**.
- **Change**: TASK items 4/5; lead aligned. build `pha-v2.3.41-p15-named-prose`. P15 still IN_PROGRESS.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py`.
- **Rollback**: restore v2.3.40 TASK / lead.

## 2026-09-11 (P1: gold × 20 — P15 still not DONE)

- **Category**: **P1 (FR-6.12 acceptance)**.
- **Evidence**: `qwen3:14b` × gold 20; dual-named 2/20; Markdown 17/20; prefs unchanged. **Do not** mark DONE.

## 2026-09-11 (P1: disk-land v1.19 no-skip + weak causal)

- **Class**: **P1 (FR-6.8 / FR-6.12 v1.19 · 3F §19)**.
- **Change**: Runtime TASK / lead drop skip; fold into advice sentences; forbid definitive causal. **Do not** require a 注意事项 section. **Do not** add interpret to `USER_CONTEXT_BRIEF_PROFILES`.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py`.
- **Rollback**: TASK / lead back to skip-when-unrelated.

## 2026-09-10 (P1: TASK slot contract — no invented numbers + brief present must not skip)

- **Class**: **P1 (FR-6.8 / FR-6.12 v1.19 · 3F §19)**.
- **Change**: `fact_card_interpret` TASK forbids derived percentiles; when the brief is present the whole slot must not be skipped; lead-in aligned. Projection re-renders from rows. **Do not** weaken Numerics; **do not** add interpret to `USER_CONTEXT_BRIEF_PROFILES`.
- **Evidence**: `scripts/pha_fact_card_selfcheck.py` TASK asserts; `scripts/pha_chb_compiler_selfcheck.py`.
- **Rollback**: TASK / lead back to skip-when-unrelated.

## 2026-09-10 (P1: CHB background_rows + USER_CONTEXT_BRIEF projection §Background)

- **Class**: **P1 (FR-6.12 v1.18 · 3F §18)**.
- **Change**: CHB self-report rows structured; chat `USER_CONTEXT_BRIEF` carries §Background. Interpretation turns still only `USER_BACKGROUND_BRIEF`. **Do not** add interpret to `USER_CONTEXT_BRIEF_PROFILES`. TASK unchanged.
- **Evidence**: `scripts/pha_chb_compiler_selfcheck.py`.
- **Rollback**: projection drops the background section.

## 2026-09-10 (P1 encode: M1-P20 exclusive inject + M1-P15 CHB)

- **Class**: **P1 (FR-6.8 / FR-6.12 v1.16 · 3F §17)**.
- **Change**: exclusive interpretation turn Manifest/FACT_CARD_CONTEXT ⊆ `infer_wearable_metric_ids`; brief read side uses the same negatives as capture; CHB combo hash + interpret projection has no §Facts; GET fact-card background `recompile_chb_if_stale` (once per day). **Do not** sweep the whole card, **do not** flip Data > Context, **do not** put brief numbers into Manifest, **do not** add `fact_card_interpret` to `USER_CONTEXT_BRIEF_PROFILES`.
- **Evidence**: `scripts/pha_p20_selfcheck.py`; `scripts/pha_chb_compiler_selfcheck.py` P15; `pha_fact_card_selfcheck` question fixtures.
- **Rollback**: `PHA_EXCLUSIVE_INJECT_NAMED=0`; `PHA_CHB_AUTOCOMPILE=0`.

## 2026-09-10 (P1 encode: M1-P19 eval audit land)

- **Class**: **P1 (FR-6.8 / FR-6.13 v1.15 · 3F §16)**.
- **Change**: emphasis TASK sentence 1 overall (exclusive does not add it); `fact_card_interpret` / `wearable_daily_review` raise this-profile T0 budget, FACT_CARD_CONTEXT may compress advice, forbid `_cap_system_content` tail-cutting T0; fact-card profiles’ `format_manifest_tier0_block` **does not** chop KV at 600 characters; `build_fact_card_event` when a card exists, scope ⊆ card rows; `workout_*` intent_hints drop bare “运动/training”. **Do not** do must-cover / retry missing rows / prefs∩; **do not** start P15 early.
- **Evidence**: `scripts/pha_p19_selfcheck.py`; `pha_p17_p18_selfcheck` regression; registry bundle `--check`.
- **Rollback**: see handoff `handoff-2026-09-10-eval-audit-solution.md` §3.

## 2026-09-09 (P1 encode: P17 outline banding + P18 context_lookup)

- **Class**: **P1 (FR-6.8 / FR-6.14 / 3F §15)**.
- **Change**: catalog `assessment_outline` + `goal_markers.context_lookup` (v1.9); TASK by exclusive/emphasis/cover-card; `advice_partial`/`hk_ok` domains; Arbiter `goal_context_lookup` / `explicit_metric_with_context_lookup`; `is_warehouse_metric_focus_turn` veto by goal; `build_fact_card_event` empty scope does not emit a card; schema capture negatives; chat injection aligned to P14 quota/dedupe. Flags: `PHA_ASSESSMENT_OUTLINE=1`, `PHA_CONTEXT_LOOKUP=1`. **Do not** flip Data > Context; **do not** start P15 early.
- **Evidence**: `scripts/pha_p17_p18_selfcheck.py` O1–O3 / C1–C4; goal/arbiter / fact_card / parity / registry `--check` green. On-device 8788 pid 65097 see proactive change-log 20:08.
- **Rollback**: turn off the corresponding flags; copy keys git revert. When `PHA_CONTEXT_LOOKUP` is off, card emission falls back to “emit if entries exist”.

## 2026-09-09 (P1 docs: outline banding + context_lookup · not encoded)

- **Class**: **P1 (FR-6.8 / FR-6.14 / 3F §15)**. Docs locked, no code.
- **Change**: PRD v1.14; 3F RFC §15; handoff `handoff-2026-09-09-outline-and-context-lookup.md`. Opened M1-P17 (`assessment_outline` + copy domains), M1-P18 (`context_lookup` + card emission ⊆ scope + questions not captured). **Do not** flip Data > Context; **do not** start P15 early.
- **Evidence**: 2026-09-09 on-device (interpretation exclusive too strict; medication questions skip-LLM + default 90d card); maintainer agreed 18:07 audit rejecting the original patch plan.
- **Rollback**: docs git revert the files of this entry; runtime behavior unchanged.

## 2026-09-09 (P1: chat ↔ fact-card interpretation same-source)

- **Class**: **P1 (FR-6.13)**. Chat side and proactive fact card share the Registry; sleep substages answerable; “can I train” goes `wearable_daily_review`.
- **Change**: Registry `catalog.*` + bundle schema generate; `infer_wearable_metric_ids` cluster expand; Numerics/skip-LLM fetch by registry id; `daily_readiness` → `wearable_daily_review` (same slots as interpret, memory policy still `chat`); session anchor `focus_grain_*`; follow_ups into catalog; SSE `label_display` / `metrics_in_scope`. Flags: `PHA_WEARABLE_REGISTRY_CATALOG` (off → RuntimeError), `PHA_WEARABLE_CLUSTER_EXPAND`, `PHA_DAILY_READINESS_PROFILE`, `PHA_EPISODIC_GRAIN_ANCHOR` (this-track acceptance default on).
- **Evidence**: offline `pha_chat_fact_card_parity_selfcheck` H9–H13; label freeze in `pha_numerics_manifest_selfcheck`; registry `--write`. On-device 8788 (pid 41270, `qwen3:14b`) H10–H13 / H10E / H13E skip-LLM all pass; H9-zh web+interpret pass; H9E audit pass (see proactive change-log 16:51).
- **Rollback**: `PHA_DAILY_READINESS_PROFILE=0` and `PHA_EPISODIC_GRAIN_ANCHOR=0` turn off new behavior; catalog path git revert.

## 2026-09-09 (M1-P14: USER_BACKGROUND_BRIEF Tier1)

- **Class**: **P1 (FR-6.12)**. Button interpretation can see chat self-reported background, but only as a non-numeric source.
- **Change**: `pha/fact_card_background_brief.py`; `fact_card_interpret` `slots_tier1=["USER_BACKGROUND_BRIEF"]`; TASK item 5; `interpret_cache_key` adds `bg_brief_digest`; `leftover_s_level_numeric_tokens` posterior (audit policy unchanged). 9-metric card soul+T0 ≈10.2k; default system cap 10k would drop T1 as a whole, so `PHA_SYSTEM_CONTENT_MAX_CHARS` default 12000. `pha_harness_profile_registry_generate.py --write`.
- **Evidence**: `pha_fact_card_selfcheck` P14 eight segments PASS; registry `--write` + selfcheck PASS. Runtime acceptance in proactive change-log.
- **Rollback**: `PHA_FACT_CARD_BG_BRIEF=0`; slot back to `[]`; TASK delete item 5; system cap back to 10000.

## 2026-09-09 (M1-P13: memory_write_policy)

- **Class**: **P0 (FR-6.11)**. `fact_card_interpret` borrows the chat pipe but must not write session memory.
- **Change**: registry `memory_write_policy` (default `chat`, interpret=`none`); predicate `profile_writes_chat_memory`; orchestrator `TurnMemorySink`; `EPISODIC_BRIDGE` explicitly emptied for `none`. `pha_harness_profile_registry_generate.py --write`.
- **Evidence**: registry selfcheck PASS; `pha_fact_card_selfcheck` P13 segment PASS (interpret five-table row counts unchanged, `session_id=null`; control lifestyle session +1).
- **Rollback**: predicate always True, delete Sink.

## 2026-09-09 (M1-P9.5b: TASK forbids extra sentences for unnamed rows)

- **Class**: **P1 (interpretation outline)**. TASK item 1 adds one sentence forbidding new paragraphs for unnamed rows.
- **Evidence**: 3 rounds each zh/en; SpO2/respiratory rate EN 1/3, ZH 0/3.
- **Rollback**: delete that sentence.

## 2026-09-08 (M1-P9.5: fact_card_interpret dedicated minimal soul)

- **Class**: **P1 (interpretation outline)**. `fact_card_interpret` no longer uses the full medical soul’s three-step review.
- **Change**: `PHA_FACT_CARD_SOUL_MINIMAL` (`harness_plan`); `chat_turn_slots.select_soul_base`; interpretation cache key includes soul. `harness_report.dry_run_harness_report` still uses full soul (not on the interpretation path; to be unified).
- **Evidence**: `pha_fact_card_selfcheck` soul routing / anti-hardcode / cache rev; registry no diff.
- **Rollback**: drop the fact_card branch.

## 2026-09-08 (M1-P9.4.1: English yearless dates)

- **Class**: **P1 (audit)**. Yearless `September 3` aligned to card `allowed_dates` then whole-span masked.
- **Change**: `_extract_fact_card_dates` + `_fact_card_date_surface_needles`; `FACT_CARD_AUDIT_POLICY_REV=v1.1`.
- **Evidence**: `FC-en-yearless-*` PASS.
- **Rollback**: restore the date-extract branch.

## 2026-09-08 (M1-P9.4: fact_card audit policy)

- **Class**: **P1 (audit)**. When `manifest.profile == fact_card_interpret`, clause-level S/E/T1; no longer the 0.5–15 decimal band.
- **Change**: `LANG_T0_CLAIM_MAP` adds temporal/educational/measurement; identifier mask; window spoken tokens; `educational_ints` telemetry.
- **Evidence**: `pha_numerics_manifest_selfcheck.py` FC-* cases PASS.
- **Rollback**: drop `audit_response_numerics` fact_card dispatch.

## 2026-09-08 (M1-P9.3: fact_card_interpret outline lives in TASK)

- **Class**: **P2 (Profile TASK)**. Withdraw assessment-prompt → metric-id parser (anti-hardcode).
- **Change**: TASK states USER_ASSESSMENT_PROMPT is the outline; if named, only those rows; valued must not be called missing. T0 order TASK / USER_ASSESSMENT_PROMPT / FACT_CARD_CONTEXT / NUMERICS_MANIFEST. Numerics still built from the whole card.
- **Evidence**: `pha_fact_card_selfcheck.py` PASS (TASK contract); `pha_chat_turn_fsm_selfcheck.py`, `pha_numerics_manifest_selfcheck.py` PASS.
- **Rollback**: restore `_FACT_CARD_INTERPRET_TASK` and slot order + `--write`.

## 2026-09-08 (M1-P9.1: fact_card_interpret profile + card-side date word class)

- **Class**: **P2 (Profile/Registry extension) + C-layer audit extra dimension** (main route stays deterministic; audit only tightens; no threshold-to-allow).
- **Change**: add `fact_card_interpret` (T0: TASK / NUMERICS_MANIFEST / FACT_CARD_CONTEXT / USER_ASSESSMENT_PROMPT; T1 empty; forbidden includes `WEARABLE_90D_SUMMARY` / `GET_HEALTH_DATA` / `EVIDENCE_CATALOG` etc.; tools empty). `stream_pha_chat_events` / `orchestrate_chat_turn_events` add internal `profile_override` (not on public `/api/chat` body). `NumericsManifest.allowed_dates` also takes `fact_card` domain ISO dates. Card-side audit: compare after date normalize; withdraw ≥100 relax and date-fragment allowlist.
- **Evidence**: after `python3 scripts/pha_harness_profile_registry_generate.py --write` the registry shows the new profile; `python3 scripts/pha_chat_turn_fsm_selfcheck.py`, `python3 scripts/pha_numerics_manifest_selfcheck.py`, `python3 scripts/pha_fact_card_selfcheck.py` PASS.
- **Rollback**: delete profile declaration + `--write` regenerate + restore `allowed_dates` and `fact_card_interpret.py` audit.

---

## 2026-09-05 (Patient State today’s steps bound to point-day)

- **Class**: evidence-slice honesty (does not change `harness_core`).
- **Change**: `_wearable_ledger_lines` “今日步数” uses `pick_point_day_row(..., ref)`; the window’s last day must not be labeled today.
- **Rollback**: restore that section of `pha/patient_state.py`.

---

## 2026-07-18 (CI coverage gate for harness packages; audit plan P2-4)

- **Class**: P2 (audit plan P2-4: coverage regression gate after in-package tests exist).
- **Config**: repo-root `.coveragerc` — measure `harness_core` + `harness_loop` library surface; **omit** `cli.py` / `paths.py` / `plugins/*` (CLI and PHA plugins still covered by selfcheck / e2e).
- **CI**: `.github/workflows/ci.yml` unit-test step becomes `pytest-cov` + `--cov-fail-under=80`.
- **Threshold rationale**: library surface ≈86% at land; `80` prevents silent regression, does not force CLI unit tests immediately.
- **Iron law unchanged**: do not expand to `pha/` giant modules; do not change the online fuse path.

---

## 2026-07-15 (harness-core α2 — frozen DomainAdapter contract + minimal attach; audit plan P1.5-1)

- **Class**: P1.5 (audit plan P1.5-1: Adapter contract freeze + zero health-domain minimal attach example).
- **Contract**: `harness_core.interfaces` (v1, 10 public symbols ≤15 budget) — `DomainAdapter` (`build_plan` / `extract_atoms` / `allowed_atoms` three-method structured Protocol, inheritance not required), `run_post_audit` (fail-closed member audit: `atom_not_allowed:*` + `compute_plan_vs_actual` machine-diff codes; empty allowlist blocks any atom), `emit_failure_event` (fields a `harness_loop.harvest` consumption superset: `passed`/`message`/`session_name`/`turn`/`lane`/`harness_profile`/`checks`), `AuditVerdict`, `is_domain_adapter`. New public symbols need a task card.
- **Example**: `examples/attach_minimal/` (`ticket_adapter.py` / `fake_agent.py` / `run_demo.py`) — in-memory IT-ticket scene, zero health-domain words; Turn 1 PASS, Turn 2 invented ticket + over-privilege role → FAIL-CLOSED and writes `failures.jsonl` (verified directly consumable by `harness-loop harvest`).
- **PHA degrades to a reference implementation**: `pha/harness_core_adapter.py` adds `PHANumericsAdapter` thin wrapper (reuses numerics manifest value/date sets and existing extract regex; **does not** touch chat/routing main path); `pha_harness_core_adapter_selfcheck` adds contract reconcile (`is_domain_adapter` + pass/fuse dual-path asserts).
- **Tests/CI**: `packages/harness_core/tests/test_interfaces.py` (8 cases; includes symbol-budget freeze assert); CI adds an independent step running `run_demo.py` and asserting FAIL-CLOSED on disk.
- **Docs**: `docs/attach-in-15-minutes.md` one-page attach guide; README “Attach Harness” line adds a link.
- **Version**: harness-core `0.0.0a2`.
- **Iron law unchanged**: zero third-party deps; `harness_core` does not `import pha.*`; no runtime self-heal.

---

## 2026-07-15 (Threat model v0; audit plan P1-4)

- **Class**: P1 (audit plan P1-4: complete the security narrative; ToB/medical scenes can cite it directly).
- **Doc**: `docs/threat-model-v0.md` — three-level trust boundary (online Core / offline Loop / human-review PR); online O1–O3 (number substitution / phase confusion / adapter smuggling) and offline L1–L4 (JSONL poisoning → 1E gates + static veto + human review as three defenses; `--confirm YES` adopt gate; residual artifact-tamper risk); explicit non-goals (no runtime input filtering / multi-tenant / artifact signing).
- **Index**: `AGENTS.md` doc table adds a “security / threat model” row.
- **Iron law unchanged**: docs only; no online/offline code path changed.

---

## 2026-07-14 (Harness Loop α4 — portable gates/distill; audit plan P1-1)

- **Class**: P1 (audit plan P1-1: 1E gate frame + distill domain-agnostic stages move into `harness_loop`).
- **Portable**: `harness_loop.gates` (strip → pre-reject → ordered gates → tier verdict; injectable token maps / gate fns) · `harness_loop.distill` (phrase extract / cluster / tiered admission / budget / patch ops / proposal assembly).
- **PHA degrades to domain params**: `scripts/pha_loop_alias_distiller.py` 397→204 lines, delegates `harness_loop.distill`; `pha/loop_keyword_conflicts.py` `classify_alias_phrase` delegates `harness_loop.gates.classify_phrase`; domain lexicons and 1E-a/b/c/d concrete rules stay in PHA.
- **Tests**: in-package add `test_gates.py` + `test_distill.py` (38 harness_loop cases total); full selfcheck still green.
- **Version**: `0.1.0a4`.
- **Iron law unchanged**: proposal-only; no auto-merge; do not write catalog.

---

## 2026-07-14 (Harness Loop — package-local pytest suite; audit plan P0-2)

- **Class**: P0 (audit plan P0-2: package can self-prove without this repo; paves PyPI).
- **Tests**: `packages/harness_loop/tests/` adds 20 pytest cases (proposals static veto / harvest dedupe and fields / pipeline order and fuse / eval_set toy domain); fixtures all in-package; zero `pha.*` / `scripts/` deps.
- **CI**: new step `Harness packages unit tests` runs `harness_core` + `harness_loop` in-package tests together (core tests were also not in CI before).
- **Iron law unchanged**: tests cover offline pure functions only; do not touch the online path.

---

## 2026-07-14 (Harness Loop α3 — portable harvest/pipeline/static promote)

- **Class**: P1 (Loop β: extract orchestration from PHA bash into `harness_loop`; business scripts remain a reference plugin).
- **Portable**: `harness_loop.candidates` · `harvest` · `pipeline` · `proposals.static_veto` / `write_static_promote_verdict`.
- **CLI**: `harvest --e2e-jsonl` (runs without PHA); `promote --static-only`; `harvest --plugin pha` goes through in-package `run_harvest_pipeline` staged orchestration.
- **Version**: `0.1.0a3`; selfcheck `pha_harness_loop_pipeline_selfcheck`.
- **Iron law unchanged**: no auto-merge; do not write catalog; do not change routing.

---

## 2026-07-13 (Harness Loop α2 — Ring R reflect CLI + portable proposal validation)

- **Class**: P1 (Loop+Reflection β thin slice: ring R independent CLI + portable proposal/verdict shape check).
- **CLI**: `harness-loop reflect` (delegates `pha_reflection_critic.py`); `harness-loop proposal-check` (`loop_proposal/v2` / `promote_verdict/v1`).
- **Package**: `harness_loop.proposals` · version `0.1.0a2`.
- **Selfcheck**: `pha_reflection_critic_selfcheck.py` + suite selfcheck covers reflect/proposal-check.
- **Iron law unchanged**: ring R read-only attribution; no auto-merge; do not change routing.

---

- **Class**: P0 (contract): public name **Harness Loop (Alpha)** = offline evolution companion to harness-core; retire “Official Loop Suite / 官方套件产品族”.
- **Narrative**: component family (core + companion + domain adapter), not a commercial “official suite”.
- **Reach**: top-level README adds Core + Loop α quick start; protocol §11 / Core·Loop README / attach examples synced.

---

## 2026-07-13 (Harness Loop (Alpha) — installable harness-loop)

- **Class**: P1 (component-family α: installable companion + CLI + toy attach; do not extract PHA business implementation).
- **Packaging**: `packages/harness_loop` `0.1.0a1` · entrypoint `harness-loop` (version / eval-check / harvest / promote / adopt).
- **Portable**: `harness_loop.eval_set` (catalog_path injectable); PHA still `--plugin pha` reference-implementation delegate.
- **Toy**: `examples/loop_reference_toy/` non-health-domain catalog + golden.
- **CI**: `pip install -e packages/harness_loop` · selfcheck `harness_loop_suite`.
- **Iron law unchanged**: no auto-merge; adopt requires `--confirm YES`.

---

## 2026-07-13 (Loop A · 1E-d OCR/UI junk + alias_fuzz eval_set)

- **Class**: P1 (Loop A gate hardening · eval_set synthetic fuzz thin slice).
- **1E-d**: `gate_1e_d_ocr_ui_junk` — pure-Latin UI/OCR chrome (`Query`/`Cancel`/…) must not promote to catalog; already-curated English aliases (e.g. `steps`) exempt.
- **Wiring**: `classify_alias_phrase` · `validate_alias_proposals`; `pha_loop_keyword_conflict_selfcheck` covers Query.
- **eval_set**: new expect `alias_must_reject`; golden `evals/goldens/pha_alias_fuzz_v0.json`; `scripts/pha_eval_set_alias_fuzz_selfcheck.py` into manifest.
- **Acceptance**: `eval_set_alias_fuzz` · `loop_keyword_conflict` · harness changelog (this entry).

---

## 2026-07-13 (Harness Loop · harness.eval_set/v1 thin slice)

- **Class**: P1 (Loop Suite portable regression contract · offline thin slice; does not change online Core control flow).
- **Contract**: `harness.eval_set/v1` — schema doc [`docs/harness-eval-set-v1.md`](harness-eval-set-v1.md); protocol register [`docs/harness-core-protocol-v0.md`](harness-core-protocol-v0.md) §11.4.
- **Impl**: `pha/harness_eval_set.py` (load + shape/offline expects); golden `evals/goldens/pha_smoke_v0.json` (`pha.smoke.v0`); export `scripts/pha_eval_set_export_smoke.py`; selfcheck `scripts/pha_eval_set_selfcheck.py` hung on `selfcheck_manifest.json`.
- **Offline gate**: `catalog_alias` reads `rules/health_intent_catalog.json` directly (includes R2 `steps←多少步`); `live_*` expects reserved for a later runner.
- **Acceptance**: `pha_eval_set_selfcheck` · full `run_selfchecks.sh` · harness consensus (this changelog).

---

## 2026-07-05 (Wave 4a Path-B · v0.4.0-beta OSS release readiness)

- **Class**: OSS-compliance sweep (DOC-only + PII sterilization · zero production feature code).
- **PII red line**:
  - Delete and `.gitignore` `reports/chb/**/brief_*.json` (cold assets containing real lab/wearable numbers)
  - Synthetic fixture: `tests/fixtures/chb/synthetic_brief_demo.json` (2099 Demo dates · no PII)
  - `reports/p1_golden/` runtime reports not in Git
  - **Before maintainer first public release**: if historical commits ever contained PII, must `git filter-repo` (see `wave4a-open-source-readiness-spec.md` §3.4)
- **Wave 4a Spec**: [`docs/wave4a-open-source-readiness-spec.md`](wave4a-open-source-readiness-spec.md) v1.0 — localhost bind · unauthenticated personal edition · Release Audit Checklist
- **Enterprise Future RFC (zero vendor hardcode)**:
  - [`docs/rfcs/rfc-device-ingestion-adapter.md`](rfcs/rfc-device-ingestion-adapter.md) — two-layer labels · `DeviceIngestAdapter`
  - [`docs/rfcs/rfc-enterprise-multi-tenant.md`](rfcs/rfc-enterprise-multi-tenant.md) — compound `user_id` · Gateway RBAC · FSM zero change
- **Release tag**: `v0.4.0-beta` (OSS readiness · build marker still `pha-v2.3.32-full-import-only`)
- **UI i18n**: Dashboard default **English** (`PHA_UI_LANG=en`); top bar can switch Chinese; `pha/static/js/i18n.js`
- **Acceptance**: `run_selfchecks.sh` · `pha_chb_compiler_selfcheck` · P1 tier F regression

---

## 2026-07-05 (P2 · 4-β-2c ring B offline write trigger)

- **Class**: P2 (Stage 4-β-2c · async offline CHB recompile · does not block inside a Turn).
- **Script**: `scripts/pha_chb_compile_all_users.py` — walk `reports/chb/{user_id}/`, compare Live T0 `ledger_hash` vs latest `brief_{hash}.json`; when Stale, trigger `compile_chronic_health_brief` and write; old artifact kept (version backlog).
- **Library**: `pha/chb_compiler.py` — `compute_live_ledger_hash` · `chb_stale_status` · `recompile_chb_if_stale` · `list_chb_report_user_ids`.
- **Architecture contract**: `recompile_if_stale` Harness slot default **off**; ring B only Nightly/Cron/CLI offline trigger, **not** hung on PR blocking CI.
- **Acceptance**: default user T0 increment → stale detected → new-hash artifact on disk + old brief kept · `pha_chb_compiler_selfcheck` · `pha_p1_golden_gate_test --tier f` regression.

---

## 2026-07-05 (P1 Public Gate: E1/E2/E3/N HTTP sign-off chain · C-1/C-2 on disk)

- **Class**: P1-d/e/f (8788 HTTP state machine · multi-turn Session · anti-hallucination stress).
- **Orchestrator**: `scripts/pha_p1_golden_gate_test.py` — `--tier f` (offline) · `--tier h` (HTTP) · `--tier all` (Public Gate full).
- **P1-d (synthetic HTTP)**: `--tier h --assets synthetic` → `pha_e2e_6panel_realdevice.py` E1; PIL synthetic PNG OCR often misses → auto fallback to on-device pixel E1 (needs `PHA_P1_ASSETS_DIR`).
- **P1-e (on-device multi-turn)**: `--tier h --assets real` → `pha_e2e_jun11_realdevice_multiturn.py` E1/E2/E3; E2 same Session no-image follow-up HRV consistency · E3 new Session empty attachment “what is in the picture” → `lifestyle` weak answer, forbid inventing ms/bpm.
- **P1-f (seal)**: `--tier all --assets real` Exit 0; C-1/C-2 marked ✅; **not** hung on PR `selfcheck_manifest.json` (Weekly/Nightly physically isolated).
- **Assert lib**: `scripts/p1_http_e2e_lib.py` · expectation matrix `tests/fixtures/p1_golden/expectations_v1.json`.
- **Acceptance**: tier F offline 6/6 numerics + tier H real E1/E2/E3 all PASS · build `pha-v2.3.32-full-import-only`.

---

## 2026-07-04 (Stage 4-β-2a/b: USER_CONTEXT_BRIEF hung on a slot + LLM Interpretation Mock)

- **Class**: P0 (Harness Tier1 read-only extension · no Profile topology skeleton change).
- **4-β-2a Harness slot hang**:
  - Slot name **`USER_CONTEXT_BRIEF`** (Tier1 read-only)
  - Inject profiles: `lifestyle` · `combined_review` (catalog / non-catalog paths)
  - **Forbid** `attachment_grounded_review` (3H warehouse isolation)
  - Read disk: `reports/chb/{user_id}/brief_*.json` (latest mtime); no artifact → slot stays empty, does not block the Turn
  - Changes: `pha/harness_plan.py` · `pha/chat_turn_slots.py` · `pha/harness_tier0_assembly.py` (marker only)
- **4-β-2b LLM §Interpretation**:
  - `PHA_CHB_COMPILER=1` switch (**default off**)
  - `compile_interpretation_llm` BYOK + injectable `llm_fn` Mock
  - **Iron gate**: §Interpretation purely Advisory; forbid flowing back into numerics / Manifest / control flow
- **Not done (hung)**: 4-β-2c T0 Ingest async write · v3.0 CloudAgentBridge adopt
- **Acceptance**: selfcheck **46/46** · L1 **18/18** · registry manifest introspection synced

---

## 2026-07-05 (Stage 4-β core read-side seal · P0 Code Freeze)

- **Cold-asset refresh**: `default` user recompiled CHB → `reports/chb/default/brief_01f8ce8c7456b9d6.json` (28 T0 facts · `interpretation[].prov_type=stub` · `ADVISORY ONLY` banner aligned to 4-β-2b).
- **Cleanup**: delete stale `brief_2ba02f1afd6ee686.json`; keep only the latest artifact to avoid mtime misread.
- **Seal statement**: **Stage 4-β core read side sealed**; **4-β-2c async write / Compile trigger not in this round**; ring B currently only the read side (Harness `USER_CONTEXT_BRIEF` read-only hang + offline compiler).
- **Acceptance**: selfcheck **46/46** · L1 **18/18**.
- **Next campaign (P1)**: C-1/C-2 on-device 6-image CompareTable / numerics gold (write no new features until P1 starts).

---

## 2026-07-04 (Stage 4-α.1 Promote + Stage 4-β-1 CHB skeleton)

- **4-α.1 Promote**: `health_intent_catalog.json` v1.5 → `sleep` +「睡多久」· `steps` +「走了多少步」 (Tier-A human-review merge).
- **Tier-C intake**: [`rules/loop_slot_candidates.jsonl`](../rules/loop_slot_candidates.jsonl) (昨晚/日均).
- **4-β-1**:
  - Spec: [`docs/wave4b-chronic-health-brief-spec.md`](wave4b-chronic-health-brief-spec.md) v0.1
  - Encode: `pha/chb_compiler.py` (§Facts deterministic · §Interpretation stub · ledger_hash)
  - Selfcheck: `scripts/pha_chb_compiler_selfcheck.py`
- **Not done (4-β-2)**: Harness `USER_CONTEXT_BRIEF` attach · T0 Ingest write · LLM Interpretation default on.
- **Acceptance**: selfcheck **46/46** · L1 **18/18**.

---

## 2026-07-04 (Stage 4-α.1: layer alignment · three-column split + 1E three gates)

- **Class**: P0 (Loop quality gate · baseline-debt payoff; no Python routing state-machine change).
- **Layer-mismatch fix**: Distiller output `pha.loop_proposal/v2`:
  - `accepted_catalog` (Tier-A) · `accepted_schema` (Tier-B) · `slot_candidates` (Tier-C) · `rejected`
  - Tier-C (昨晚/日均 etc.) **must not** write `health_intent_catalog.json`
- **1E three-layer admission**:
  - **1E-a** layer denylist (time anchors / aggregate operators / affective templates)
  - **1E-b** substring inheritance (longer catalog proposals already covered by shorter schema bait → reject)
  - **1E-c** narrow-domain pollution probe (symptom compound sentences must not be hijacked by a new alias)
- **Baseline debt**: `wearable_bundle.schema.json` retires `睡得好` / `睡得怎么样`, replaced by clean core `睡多久`; `pha_chat_turn_fsm_selfcheck` weak-sentence probe becomes `睡眠呢`.
- **Second-pass clean result** (proposal-only, not merged into catalog):
  - Tier-A PR draft: `睡多久` · `走了多少步`
  - Tier-C: `昨晚` · `日均`
  - Rejected: `睡得好吗` (`gate_1e_a_affective`)
- **Acceptance**: selfcheck **45/45** · L1 **18/18**.

---

## 2026-07-03 (Stage 4-α: ring A alias distill Loop · Stage 1E)

- **Class**: P0 (offline Loop · proposal-only; no Python routing change).
- **Stage 1E** `pha/loop_keyword_conflicts.py`:
  - schema cross-asset trigger conflicts · catalog alias duplicates · cross-layer metric inconsistency · proposal-batch dedupe.
  - `scripts/pha_loop_keyword_conflict_selfcheck.py` registered in selfcheck manifest.
- **Telemetry Harvest** `scripts/pha_telemetry_harvest.py`:
  - Sources: Harness JSONL · question_manifest · e2e bank variant pools.
  - Output: `reports/loop/slow_round_candidates.jsonl`.
- **Alias Distiller** `scripts/pha_loop_alias_distiller.py`:
  - Cluster → deterministic alias extract (no LLM) → 1E gates → `reports/loop/proposals/alias_proposal_*.json`.
  - **Forbid auto-merge**; promote requires human-review PR + Nightly 148+164.
- **First distill**: bank pool scan 6 candidates → several sleep/steps proposals (see `reports/loop/proposals/`).
- **Acceptance**: selfcheck **45/45** all green.

---

## 2026-06-27 (Phase 0 wall-building: CI layers + D-3d-2 red/green table + Stage 4 dual-ring RFC)

- **Class**: P0 (rail laying · legal positioning; no business Python routing change).
- **0.1 CI layers**:
  - Add `scripts/pha_universal_attachment_lane_l1_selfcheck.py` (wrap `--skip-http`, 18 L1 probes, second-scale).
  - `selfcheck_manifest.json` registers `universal_attachment_lane_l1` (tags: stage3h, p0, nightly).
  - Add `.github/workflows/nightly-harness.yml`: PR-safe L1 job + optional full job (`PHA_NIGHTLY_ENABLED=true` + secrets).
  - Add `scripts/nightly_harness_regression.sh`: 148 mixed stress + Bank 164; on fail `anti-regression-constraints.md` auto-updated by the stress battery and snapshotted to the report dir.
- **0.2 On-device red/green table**: [`docs/rfcs/stage3d-wearable-e2e-checklist.md`](rfcs/stage3d-wearable-e2e-checklist.md) v1.0 (E1–E8 · G-Compare/G-Interp/G-Delta).
- **0.4 Dual-ring RFC**:
  - [`docs/rfcs/rfc-stage4-offline-loop-engineering.md`](rfcs/rfc-stage4-offline-loop-engineering.md) (ring A alias distill + three-layer constitution gates + CI layers).
  - [`docs/rfcs/rfc-stage4b-personalization-flywheel.md`](rfcs/rfc-stage4b-personalization-flywheel.md) (ring B: T0+CHB, forbid per-user registry).
- **Acceptance**: L1 selfcheck PASS; Nightly full must run locally/self-hosted (8788+LLM+assets) `bash scripts/nightly_harness_regression.sh`.

---

## 2026-06-27 (Stage 3H-δ: corrupt structure fallback + 148/148 stress closed loop)

- **Class**: P1 (3H long-tail routing gap targeted fix + acceptance).
- **Root cause**: hostile/odd screenshot `document_family` missed lab/unknown allowlist → `qa_mode=none` → first-turn lifestyle collapse (stress 145/148, 3 `[ERR_PROFILE_LIFESTYLE]`).
- **Fix**:
  - `perception_family.parsed_has_groundable_facts` — structure signal (metrics[] / vision_summary).
  - `resolve_attachment_qa_mode` — `has_attachment_paths` + parsed facts → force `grounded` (explicit cross-year lab still yields to lab_cross_year).
  - `chat_turn_routing` — pass paths + parsed_payload.
- **Stress**: `scripts/pha_universal_attachment_stress_battery.py` seed=20260626 → **148/148** (L1 18 + L2 130), `STRESS_EXIT=0`; `attachment_grounded_review` 6 times (including corrupt first turn).
- **Wrong-answer book**: active Fails zeroed; corrupt gap archived to [`docs/rfcs/anti-regression-constraints.md`](rfcs/anti-regression-constraints.md) “historically closed”.
- **Selfcheck**: `pha_universal_attachment_lane_selfcheck` **15/15 PASS**.

---

## 2026-06-27 (Stage 3H stress infrastructure + user-tone guardrail)

- **Class**: P1 (engineering acceptance + UX).
- **Add**: `scripts/pha_universal_attachment_stress_battery.py` — L1 in-process physically isolated probes + L2 HTTP 20× elastic long rounds; `try/except AssertionError` capture → auto-generate wrong-answer book.
- **Telemetry**: `done` SSE adds `harness.plan.profile` / `qa_mode` / `grounded_fallback_applied`.
- **Tone**: `polish_final_user_answer` last-pass clean for all profiles; skip_llm deterministic replies and status bars drop internal “定账/数仓” jargon; `grounded_answer_composer` warehouse-focus summary rewritten in natural language.

---

## 2026-06-26 (Stage 3G P2 wrap: narrow hint first + warehouse spoken weak sentences)

- **Class**: P2 (Bank seed=20260626 remaining 9 fail cluster wrap).
- **Root cause**: broad `infer_wearable_metrics` core fallback polluted narrow follow-ups; `_WORKOUT_HINT_RE` pair inject blocked by the 2-metric rule; `指标` regex too greedy; warehouse spoken weak sentences had no single-metric trigger.
- **Fix**:
  - `wearable_compare_table_v1.py`: `infer_single_metric_focus_ids` narrow hint returns first; workout pair-focus exception; `_COMPARE_ALL_METRICS_RE` narrowed.
  - `wearable_metric_registry.json`: heart-rate/workout hints refined; `睡眠总时长` replaces generic `时长`.
  - `wearable_bundle.schema.json`: `走路/走得多→steps`, `睡得好/睡得怎么样→sleep`.
- **Selfcheck**: `pha_wearable_compare_table_selfcheck` · `pha_chat_turn_fsm_selfcheck` · `pha_health_intent_catalog_selfcheck` all PASS.
- **Acceptance**: Bank seed=20260626 **164/164** (`20260626T033611Z`, wall 2147s, fails=0).

---

## 2026-06-26 (Stage 3H-γ: dedicated-lane fail fallback + declarative expand-class SOP)

- **Class**: P2 (RFC 3H-γ wrap).
- **Code**: add `pha/attachment_grounded_fallback.py` — when `wearable_screenshot_review` / `attachment_asset_qa` / `attachment_episodic_bridge` structured data is insufficient but `metrics[]`/`narratives[]`/`vision_summary` still exist, slot-assembly rebinds to `attachment_grounded_review` (SSE status hint); `harness_profile_registry._PROFILE_GROUNDED_FALLBACK` explicitly declares the fallback contract; `perception_family.attachment_parse_is_actionable` includes `metrics[]`.
- **Docs**: RFC §6.1 declarative expand-class SOP ops table; v2.3 §8.4 marks 3H-γ ✅.
- **Acceptance**: `pha_universal_attachment_lane_selfcheck` **12/12 PASS** (including 4 γ fallback cases); routing/fsm/profile_registry/compare/3a1 regression all PASS.

---

## 2026-06-26 (Stage 3H-α/β impl: universal attachment fallback lane lands)

- **Class**: P1 (routing-completeness root fix · RFC already approved → encode).
- **Flag**: `PHA_UNIVERSAL_ATTACHMENT_LANE=1` (already in env-8788; unset falls back to original lab→none→lifestyle).
- **Collapse A** (`attachment_asset_qa.resolve_attachment_qa_mode`): lab/medication/unknown/other actionable attachments no longer return `none`, return `grounded`; explicit cross-year lab intent (`_HARD_LAB_PIVOT_RE`) yields to `lab_cross_year`. Wearable still uses the dedicated lane.
- **Collapse B** (routing+plan): `chat_turn_routing.TurnRoutingDecision` adds `attachment_grounded_review`; `harness_plan.build_turn_evidence_plan` adds a grounded branch (profile=`attachment_grounded_review`, slots_tier0=[MASTER_ANCHOR, ATTACHMENT_LABEL, DATA_AVAILABILITY, TASK], `tools_allowed=[]`, forbidden physically seals all warehouse/history slots). Orchestrator wires the flag.
- **Collapse C** (`session_turn_focus.focus_summary_from_parsed`): when `metrics[]` non-empty and no label_ledger, serialize as an immutable deterministic fact table (this turn’s only number source), preferred over vision_summary/narratives. Pure additive; empty metrics behavior unchanged.
- **Assembly/validate**: `harness_tier0_assembly._PROFILE_CONFIG` + `harness_profile_registry` (known profiles / slot invariants `{ATTACHMENT_LABEL, TASK}` / probe) add grounded; `rules/harness_profile_registry.generated.json` regenerated.
- **Slots**: grounded injects read-only DATA_AVAILABILITY, suppresses warehouse background/RECALL, forces talk-about-this-image.
- **Constraint alignment**: TurnEvidencePlan before LLM; pure structure signal (`has_parse`+family) trigger, no phrase routing; warehouse physically isolated; Shadow/Reflection unchanged.
- **Rollback**: `unset PHA_UNIVERSAL_ATTACHMENT_LANE`.
- **Acceptance**: new `scripts/pha_universal_attachment_lane_selfcheck.py` (8/8 PASS, registered in manifest); regression routing/fsm/compare_table/catalog/3a1/3a2/profile_registry all PASS; **end-to-end talk-about-this-image measured**: liver/kidney lab payload → `profile=attachment_grounded_review`, Tier0 contains CO2/GFR/CREA fact table, `tools_allowed=[]`, all warehouse slots forbidden and Tier0 has no history data block.

---

## 2026-06-26 (Stage 3H RFC approved: universal attachment fallback lane)

- **Class**: P1 (consensus evolution · routing-completeness root fix) — this entry is RFC approval only, **no code changed**.
- **RFC**: new [`docs/rfcs/rfc-stage3h-universal-attachment-lane.md`](rfcs/rfc-stage3h-universal-attachment-lane.md) (Ratified).
- **Pain** (Telemetry): upload liver/kidney lab report + “analyze the lab results” → system answers warehouse historical lipids/HRV/sleep (wrong hat).
- **Diagnosis**: generalized parse layer is already generic (`results[]`/`narratives[]`), but last mile hard-wires by class — `resolve_attachment_qa_mode` kicks lab/unknown out → lands `lifestyle` warehouse.
- **Design**: two-layer lane constitution. Layer 1 `attachment_grounded_review` universal fallback (talk-about-this-image + warehouse physically isolated forbidden); layer 2 wearable/lipid dedicated enhancement (fail falls back to the universal layer, **never** lifestyle).
- **Design landing** (to be encoded in 3H-α/β): `resolve_attachment_qa_mode` (add grounded band; lab/medication no longer kicked), `chat_turn_routing`, `harness_plan` (new plan), `harness_tier0_assembly` (new assembly key), `focus_summary_from_parsed` (serialize `metrics[]` fact table), `harness_profile_registry` (slot invariants).
- **Constraints**: TurnEvidencePlan before LLM; `tools_allowed=[]` + forbidden seals warehouse; no Python phrase routing (trigger is `has_parse` structure signal); new types only add schema/registry; Shadow zero-adopt; Reflection R0/R1 unchanged.
- **Flag / rollback**: `PHA_UNIVERSAL_ATTACHMENT_LANE=1`; unset falls back to original lab→none→lifestyle.
- **Acceptance**: liver/kidney screenshot turn `profile=attachment_grounded_review` and the answer contains only this-image metrics, not warehouse history; new `pha_universal_attachment_lane_selfcheck.py`.

---

## 2026-06-25 (Stage 3G E2E fix: delta first + catalog spoken aliases)

- **P0** `chat_skip_llm`: `build_episodic_delta_focus_answer` **before** `build_weak_episodic_followup_answer`.
- **P1** `health_intent_catalog.json` v1.4: `episodic_delta_followup` + `metric_aliases` spoken expansion.
- **P1** `wearable_bundle.schema.json` / `wearable_metric_registry.json`: declarative trigger/hint synced.
- **P1b** `is_weak_episodic_followup` mutually exclusive with delta tokens.
- **Docs** `pha-architecture-evolution-v2.3.md` §8 · `stage3g-e2e-remediation-rfc.md`.
- **Consensus**: no Python phrase routing; Harness skip order adjusted; Plan unchanged.
- **Acceptance**: Baseline **70/70**; Bank seed=20260626 **155/164** (delta/weak fixed; alias/warehouse still 9 fails).

---

## 2026-06-25 (E2E dynamic question bank 20× + baseline contrast)

- **Bank** `rules/e2e_question_bank_v1.json` v1.0: 20 sets × 8–10 turns; `variant_pools` 7:3 spoken/written; `PHA_E2E_BANK_SEED` exploratory sample.
- **Loader** `pha/e2e_question_bank.py`: `resolve_bank_sessions` + `question_manifest` on disk.
- **Battery** `pha_e2e_browser_battery_20x.py`: `PHA_E2E_USE_QUESTION_BANK=1` wires dynamic lane checks; `weak_followup_skip` check.
- **Selfcheck** `pha_e2e_question_bank_selfcheck.py`; `seed_e2e_question_bank_v1.py` regenerates the bank.
- **Consensus**: variants only in the test bank; lane-level asserts; R0/R1 reflection docs layer does not change the product path.
- **Acceptance**: baseline fixed 20× → restart 8788 → bank seed full 20× + manifest.

---

## 2026-06-24 (20× E2E battery fixes: weak episodic skip + warehouse focus lazy path)

- **S13 weak follow-up skip-LLM** (catalog `advisory_followup` + `build_weak_episodic_followup_answer`):
  - Screenshot-session `weak_followup` / `advisory_followup` turns: close polite wrap or Top-3 caution brief; forbid refixture-medg the whole table.
  - `user_message_needs_wearable_session_reuse` includes `is_weak_episodic_followup` → reload session parse when not re-uploaded.
  - `chat_skip_llm` uses `wearable_compare_table_obj` as the main table; Arbiter weak close/advisory does not upgrade `combined_review`.
- **S07 warehouse single-metric lazy path**:
  - `is_warehouse_metric_focus_turn` — pure warehouse single-metric follow-up skips `WEARABLE_90D_SUMMARY` rescan and heuristic snapshot inject.
  - `try_warehouse_metric_focus_skip` filters the manifest to the single-metric row.
- **Selfcheck** `pha_chat_turn_fsm_selfcheck.py` extends weak follow-up + warehouse focus cases.
- **Consensus**: Harness skip-LLM veto; catalog declarative tokens; no phrase hardcoded routing; Shadow does not seize power.
- **Acceptance**: `PHA_E2E_SESSIONS=S07,S13` 20× battery subset.

---

## 2026-06-24 (Stage 3F-γ intent_scope clarify + 3F-δ Shadow goal telemetry)

- **3F-γ** (`PHA_CLARIFY_INTENT_SCOPE=1`, depends on `PHA_GOAL_CLASSIFIER=1`):
  - **Add** `goal_classifier.clarify_intent_scope_enabled()` — single-domain holistic goes `intent_scope`/`data_gap` clarify; when off, degrade to single-domain profile.
  - **Extend** `clarify_turns` — catalog chip parse (`wearable_only` etc.); session `parsed_json` persists pending clarify scope; orchestrator loads on chip follow.
  - **Selfcheck** H-δ8/H-δ9 (`pha_clarify_turns_selfcheck.py`).
- **3F-δ** (`PHA_SHADOW_ROUTING=1` + `PHA_GOAL_CLASSIFIER=1`):
  - **Extend** `shadow_routing.run_shadow_routing` — `goal_class` / `suggested_domains` telemetry (zero-adopt).
  - **Extend** `build_shadow_status_message` — lifestyle + holistic high-confidence non-blocking hint.
  - **Selfcheck** `pha_stage3f_delta_shadow_selfcheck.py`; `stage2d` validates goal fields.
  - **Docs** `telemetry-review-playbook.md` §4.5.
- **Consensus**: TurnEvidencePlan before LLM; Shadow does not seize power; Arbiter remains the only authoritative exit.
- **Rollback**: unset `PHA_CLARIFY_INTENT_SCOPE` / `PHA_SHADOW_ROUTING`.
- **Acceptance**: `run_selfchecks.sh` + clarify/body-age E2E API (browser same path).

---

## 2026-06-24 (Stage 3F-P2 combined_review SSE hard asserts)

- **P2 E2E hard asserts** (`pha/e2e_combined_review_assertions.py`):
  - combined_review turns: `done` event, no SSE error, Ollama 400 signature, `catalog_tool_loop`, `fetch_evidence_by_id` executed.
  - Wired into `pha_e2e_body_age_3f_multiturn.py`; offline `pha_e2e_combined_review_sse_selfcheck.py`.
- **Acceptance**: body-age E2E 8/8 + P2 SSE table.

---

## 2026-06-17 (Stage 3F-β focus_goal session anchor)

- **3F-β encode** (`PHA_GOAL_SESSION_ANCHOR=1`, depends on `PHA_GOAL_CLASSIFIER=1`):
  - **Extend** `session_turn_focus` / `HealthSessionFocus`: `focus_goal` + `focus_domains`.
  - **Arbiter** `episodic_goal_continue` — weak questions continue holistic → `combined_review`.
  - **record_health_turn_focus** — holistic upgrade writes goal; explicit metric clears goal.
  - **Harness** `episodic.focusGoal` / `focusDomains`.
  - **Selfcheck** H6/H7 folded into `pha_goal_arbiter_selfcheck.py`; E2E `pha_e2e_body_age_3f_multiturn.py`.
- **Rollback**: unset `PHA_GOAL_SESSION_ANCHOR`.

---

## 2026-06-17 (Stage 3F-α GoalClassifier + Harness Arbiter)

- **3F-α encode** (`PHA_GOAL_CLASSIFIER=1`):
  - **Add** `pha/goal_classifier.py`, `pha/harness_arbiter.py`.
  - **Extend** `rules/health_intent_catalog.json` v1.2 (`goal_markers` / `holistic_proxy_metrics` / `clarify_kinds`).
  - **Wire** `harness_plan.build_turn_evidence_plan(authoritative_profile=…)`, `chat_turn_orchestrator`, Harness report `goalClass` / `arbiterDecision`.
  - **Extend** `clarify_turns.resolve_scope_from_clarify_choice` — `intent_scope` chip.
  - **Selfcheck** `scripts/pha_goal_arbiter_selfcheck.py` (H5–H8); register `selfcheck_manifest.json`.
- **Consensus**: Resolver does not pick profile; Arbiter only upgrades holistic; Shadow not enabled (3F-δ backlog).
- **Rollback**: unset `PHA_GOAL_CLASSIFIER`.
- **Acceptance**: `pha_goal_arbiter_selfcheck.py` PASS + `run_selfchecks.sh`.

---

## 2026-06-17 (Stage 3F intent-resolution completeness · docs locked)

- **Architecture-completeness wave** (not a single E2E patch):
  - **Add** [`docs/stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) — GoalClassifier · Harness Arbiter · focus_goal · clarify `intent_scope` / `data_gap` · H5–H8.
  - **Join** [`docs/stage3c-multi-turn-episodic-focus-rfc.md`](stage3c-multi-turn-episodic-focus-rfc.md) §15; [`docs/pha-architecture-evolution-v2.3.md`](pha-architecture-evolution-v2.3.md) §7.5.
  - **Index**: `AGENTS.md`, `.cursor/rules/pha-mandatory-reads.mdc`, `docs/telemetry-review-playbook.md` §4.4.
- **Consensus alignment**: TurnEvidencePlan before LLM; Resolver does not pick profile; Shadow zero-adopt; catalog declarative expansion.
- **Encode status**: ⏳ waiting 3F-α (`PHA_GOAL_CLASSIFIER=1`); this entry is **design lock**, no runtime behavior change.

---

## 2026-06-22 (P0 harness_report + P2 registry generate)

- **P0 · Harness report emit split**:
  - **Add** `pha/chat_turn_harness_report.py`, `pha/chat_turn_routing.py`; orchestrator delegates; session anchor preferred over phrase routing.
  - **Acceptance**: `pha_chat_turn_routing_selfcheck.py` + Jun11 **7/7 PASS**.
- **P2 · Registry generate tool**:
  - `generate_profile_registry_manifest()` + `rules/harness_profile_registry.generated.json` + `scripts/pha_harness_profile_registry_generate.py`.
  - **Acceptance**: `pha_harness_profile_registry_selfcheck.py` + `generate --check` PASS.
- **Agent consensus**: `.cursor/rules/pha-mandatory-reads.mdc`, `AGENTS.md`.

---

## 2026-06-08

- Added cross-agent consensus baseline:
  - `docs/harness-consensus-opus48-2026-06-08.md`
- Added enforcement mechanisms:
  - `.cursor/rules/harness-consensus.mdc`
  - `.github/PULL_REQUEST_TEMPLATE/harness-consensus.md`
  - `scripts/ci/check_harness_consensus.py`
- CI wired to fail when harness-critical files change without updating this log.
- Consensus source anchored to user-provided Opus 4.8 harness review:
  - Deterministic L0 plan + Tier0 budget + C-layer numerics audit + Harness veto preserved as non-negotiable constraints.

## 2026-06-15

- **CONSENSUS_ACK: harness-opus48-v2026-06-08 read**
- **P1 · skip_llm architecture extension (driven by 20× on-device battery · does not break L0/L2 contract)**:
  - **Problem**: pure warehouse `wearable_only` had no `NUMERICS_MANIFEST` Tier0 slot → single-metric follow-up still went LLM (~55–70s); screenshot first-turn 6-image T1 repeated LLM whole-segment analysis (~180s).
  - **Design** (Harness in charge, LLM as synthesizer):
    1. `try_warehouse_metric_focus_skip()` — lazy `build_numerics_manifest` + `build_manifest_metric_focus_summary`; skip LLM when `wearable_only` and no screenshot.
    2. `build_compare_first_upload_answer()` — screenshot first turn (including attachment paths) uses `compare_table_to_user_summary` directly + optional exercise-advice template; skip LLM restatement.
    3. `build_catalog_followup_focus_answer()` — screenshot-session “睡眠呢” class catalog single-metric → CompareTable primary metric, preferred over warehouse mean.
    4. `infer_single_metric_focus_ids()` extends `_EPISODIC_SHORT_METRIC_RE` (“睡眠呢”“步数呢”) and deep-sleep hints.
  - **Changed files**: `pha/chat_service.py`, `pha/grounded_answer_composer.py`, `pha/wearable_compare_table_v1.py`
  - **Unchanged (aligned with consensus)**: TurnEvidencePlan contract, CompareTable schema/verdict, C-layer audit path, Shadow default does not seize power.
  - **Rollback**: delete the three function calls above; restore original `numerics_manifest is not None` guard inside the `wearable_only` block.
  - **Acceptance**:
    - `run_selfchecks.sh` **33/33 PASS**
    - `pha_e2e_jun11_realdevice_multiturn.py` **7/7 PASS** (T1 CompareTable skip_llm; T3–T6 focus)
    - `pha_e2e_browser_battery_20x.py` S07 warehouse HRV **3/3 PASS** (68s→3–11s)
  - **Report**: `docs/stage3c-browser-e2e-report-2026-06-15.md`
  - **Known backlog**: skip_llm does not emit Composer `fact_card`; “深睡多久” still falls to LLM when CompareTable has no snapshot (S05 T4).
- **P0/P1 wrap (follow-up parse reuse + harness correction)**:
  - **Root cause**: follow-up turn `_reuse_parse` did not cover single-metric / episodic delta / exercise advice → `wearable_screenshot_review=False`, the whole skip_llm path did not run.
  - **Fix**:
    1. `user_message_needs_wearable_session_reuse()` — unified judge of whether the session should reload `parsed_payload`.
    2. `chat_service.py` computes `_prior_user_msg` earlier; `_reuse_parse` calls the helper above.
    3. `build_single_metric_focus_answer()` — when deep/REM has no snapshot, deterministic “stage not recognized” reply (no invention, no LLM).
    4. `pha_e2e_browser_battery_20x.py` — `only_turns` / `only_with_upload_metrics` fix harness false reports.
  - **Changed files**: `pha/chat_service.py`, `pha/wearable_compare_table_v1.py`, `scripts/pha_e2e_browser_battery_20x.py`
  - **Acceptance (2026-06-15 final)**:
    - Jun11 gold **7/7 PASS** (`/tmp/pha-jun11-final2.log`)
    - Battery slim 6 sessions (S01,S04,S05,S07,S14,S20) **32/32 PASS, 0 fail** (`battery_20x_20260615T150347Z.md`)
    - S04 “和上周比呢” T4: 36.8s LLM → **0.1s** episodic skip_llm
    - S05 “深睡多久” T4: 35.9s LLM → **0.1s** no-snapshot deterministic reply
    - S14 “明天适合运动吗” T6: **0.2s** exercise-advice template
  - **Remaining backlog**: first-turn 6-image OCR ~120–135s; S20 T5/T6 broad follow-ups still go LLM (~30–40s, out of P1).
- **P2 · Perception parallel + wearable_only Manifest slot (consensus Registry direction · main path)**:
  - **Problem**: 6-image first-turn OCR serial ~120–135s; `wearable_only` plan missing `NUMERICS_MANIFEST` Tier0 slot; steps-class single-metric depended on lazy build.
  - **Fix**:
    1. `perceive_chat_attachment_paths()` + `ThreadPoolExecutor` parallel per-image OCR (`PHA_PERCEPTION_PARALLEL=1` default on; `PHA_PERCEPTION_PARALLEL_WORKERS` default 6).
    2. `chat_service.py` multi-image send calls `perceive_chat_attachment_paths` (drop duplicate merge logic).
    3. `_wearable_only_turn_plan` adds `NUMERICS_MANIFEST`; `harness_tier0_assembly` protects that slot.
  - **Changed files**: `pha/perception_worker.py`, `pha/chat_service.py`, `pha/harness_plan.py`, `pha/harness_tier0_assembly.py`
  - **Rollback**: `PHA_PERCEPTION_PARALLEL=0` restores serial; remove `NUMERICS_MANIFEST` slot from `wearable_only` plan.
  - **Not done (do not fix corner cases)**: S20 broad follow-up LLM path; deep-sleep OCR stage extract; sub-agent protocol.
  - **Acceptance**: `pha_stage3c_wearable_selfcheck.py` PASS; Jun11 + full 20× battery rerun (see `stage3c-browser-e2e-report`).
- **P0 · `stream_pha_chat_events` state-machine split (consensus §4 P0 · does not break profile contract)**:
  - **Problem**: ~1850-line single function, orchestration not unit-testable; consensus hard constraint “TurnEvidencePlan before LLM” had no runtime guard.
  - **Design**:
    1. `pha/chat_turn_fsm.py` — `ChatTurnPhase` enum + `ChatTurnPhaseRecorder` (`plan_precedes_compose` assert).
    2. `pha/chat_skip_llm.py` — `evaluate_skip_llm_path()` unit-testable skip_llm decision.
    3. `pha/chat_turn_orchestrator.py` — `orchestrate_chat_turn_events()` carries original SSE orchestration + phase telemetry.
    4. `pha/chat_service.py` — thin wrap `yield from orchestrate_chat_turn_events(...)`.
  - **Changed files**: `pha/chat_turn_fsm.py`, `pha/chat_skip_llm.py`, `pha/chat_turn_orchestrator.py`, `pha/chat_service.py`, `scripts/pha_chat_turn_fsm_selfcheck.py`, `scripts/selfcheck_manifest.json`
  - **Rollback**: `PHA_CHAT_TURN_FSM=0` turns off strict phase asserts; restore monolith `chat_service.py` (git revert).
  - **Unchanged**: TurnEvidencePlan slot contract, C-layer audit, Shadow default does not seize power, profile routing logic.
  - **Incidental fix**: `attach_client_reuse` replaces the deleted `_use_client` reference.
  - **Acceptance**: `pha_chat_turn_fsm_selfcheck.py` + `run_selfchecks.sh`; Jun11 API E2E **7/7 PASS**.
- **P1 · Broad-intent template skip_llm (Harness in charge · not a corner case)**:
  - **Scope**: screenshot-session “明天能跑步吗”“跑多久合适”“总结一下我的健康数据” → deterministic CompareTable templates, no LLM long answer.
  - **Change**: `wearable_compare_table_v1.py` (extend `_EXERCISE_ADVICE_ONLY_RE`, `build_health_summary_followup_answer`); `chat_skip_llm.py` wires it.
  - **Not done**: S20 single-word “锻炼”“血脂” without a narrow intent still go LLM.
  - **Rollback**: delete `build_health_summary_followup_answer` call; restore old `_EXERCISE_ADVICE_ONLY_RE`.
- **P1 · Catalog two-phase generalize to a controlled N-step pick loop (consensus §4 P1)**:
  - **Goal**: not depend on scene-specific hardcode; support multi-turn `fetch_evidence_by_id` picks while keeping Harness fallback veto.
  - **Change**:
    1. `chat_agent_runtime.py`: `_run_catalog_fetch_phase()` becomes controlled N steps (`PHA_CATALOG_MAX_FETCH_ROUNDS`, default 3).
    2. When picks do not cover `all_required_ready`, Harness force-fills fallback (`catalog_partial_fill`).
  - **Constraints kept**: TurnPlan still decides the tool allowlist; only `fetch_evidence_by_id` allowed; decision power is not given to the LLM.
  - **Rollback**: `PHA_CATALOG_MAX_FETCH_ROUNDS=1` restores single round; or revert that function.
  - **Acceptance**: `pha_catalog_registry_selfcheck.py`, `pha_harness_golden_run.py`, S03/S15 battery subset **5/5 PASS**.
- **P1 · Catalog routing generalize strengthen (not scene-specific hardcode)**:
  - **Change**:
    1. `chat_agent_runtime.py` adds per-turn state and `catalog_round` observation fields for auditing N-step pick behavior.
    2. Add `scripts/pha_catalog_multistep_selfcheck.py`: simulated provider with two rounds of different ids verifies “not scene-hardcoded” multi-step pick closed loop.
    3. `scripts/selfcheck_manifest.json` registers `catalog_multistep`.
  - **Rollback**: delete `catalog_round` field and `catalog_multistep` selfcheck registration.
  - **Acceptance**: `catalog_multistep + catalog_registry + harness_golden_run + stage2d` **4/4 PASS**.
- **P2 · Harness Profile/Registry validation tool (consensus §4 P2)**:
  - **Add** `pha/harness_profile_registry.py`:
    1. `validate_representative_routes()` — generic routing probes (not battery-scene hardcode).
    2. `validate_plan_invariants()` — profile slot/tool contracts (e.g. `wearable_only` must contain `NUMERICS_MANIFEST`).
    3. `validate_schema_assets()` — schema catalog.profiles and adapter importability.
    4. `validate_tier0_assembly_coverage()` — Tier0 assembly config coverage.
  - **Selfcheck**: `scripts/pha_harness_profile_registry_selfcheck.py`; register `selfcheck_manifest.json`.
  - **Rollback**: delete the module and selfcheck registration.
  - **Acceptance**: `harness_profile_registry` + `run_selfchecks.sh` full PASS.
- **P2 · Sub-agent protocol v1 (zero-adopt)**:
  - **Docs**: `docs/harness-subagent-protocol-v1.md`
  - **Code**: `pha/harness_subagent_protocol.py` (tool Veto, SSE boundary, Shadow zero-adopt, C-layer path check)
  - **Catalog integration**: `chat_agent_runtime.py` protocol check before catalog tool calls
  - **Selfcheck**: `scripts/pha_harness_subagent_protocol_selfcheck.py`
  - **Rollback**: `PHA_HARNESS_SUBAGENT_PROTOCOL=0`
- **P0 deepen · perception phase split**:
  - **Add** `pha/chat_turn_perception.py` (`iter_attachment_upload_phase` / `iter_session_parse_reuse_phase`)
  - **orchestrator** delegates to the above phase module (behavior-zero change)
  - **Acceptance**: `stage3c_wearable` + Jun11 + 20× battery
- **P1 · Shadow low-confidence strengthen (zero-adopt)**:
  - **Change**:
    1. `shadow_routing.py` adds `build_shadow_status_message()`, hints only on high-priority disagreement.
    2. `chat_turn_orchestrator.py` appends a telemetry hint at turn end; does not rewrite the current answer.
  - **Rollback**: delete the status-hint call or turn off `PHA_SHADOW_ROUTING`.
  - **Acceptance**: `pha_stage2d_selfcheck.py` PASS; `run_selfchecks.sh` full PASS.
- **P0 deepen · SLOT_ASSEMBLY / COMPOSE module split (consensus §4 P0)**:
  - **Add**:
    1. `pha/chat_turn_slots.py` — `TurnSlotContext` + `iter_turn_harness_assembly_phase()` (SLOT_ASSEMBLY → TIER0 → message stack).
    2. `pha/chat_turn_compose.py` — `TurnComposeContext` + `iter_compose_response_phase()` / `iter_post_compose_audit_phase()`.
  - **orchestrator** delegates to the above modules; `ChatTurnPhaseRecorder` phase telemetry unchanged; behavior-zero change.
  - **Rollback**: git revert the two modules + orchestrator wiring.
  - **Acceptance**: `pha_chat_turn_fsm_selfcheck.py` + `run_selfchecks.sh`.
- **P2 · Registry validation into CI gate**:
  - **Change**: `scripts/ci/check_harness_consensus.py` calls `validate_harness_profile_registry()` when harness changes and the changelog is already updated; extend `pha/chat_turn_` prefix watch.
  - **Rollback**: remove the `run_registry_validation()` call.
  - **Acceptance**: `python scripts/ci/check_harness_consensus.py` (skip when no harness change; when there is a change, need changelog + registry PASS).
- **P0 deepen · post-split regression fix + E2E retest (2026-06-22)**:
  - **Fix**: `chat_turn_slots.py` mistakenly imported `focus_summary_from_parsed` from `attachment_asset_qa` → change back to `session_turn_focus` (runtime ImportError caused empty replies).
  - **Acceptance**:
    - Jun11 gold **7/7 PASS** (T1 ~29.5s skip_llm CompareTable)
    - Battery subset S04/S05/S07 **11/11 PASS, 0 fail** (wall ~106s)
- **P1 · Session-anchor cross-domain arbitration (not hardcoded per-sentence rules · consensus routing brittleness)**:
  - **Problem**: screenshot-session short ask “血脂怎么样” falsely hit `lab_year` clarify; the rule layer did not prefer session focus.
  - **Design** (Harness in charge):
    1. `session_anchor_profiles` + `explicit_lab_record_request()` — only judge “explicitly wants lab records” vs “session continue-focus”.
    2. Short-sentence cross-domain → auto continue-focus; long-sentence cross-domain → `intent_scope` clarify (continue session / pick lab year).
    3. catalog declares `wearable_screenshot_review.episodic_continue`; forbid adding if-else for one sentence.
  - **Change**: `health_turn_resolver.py`, `health_intent_catalog.py`, `rules/health_intent_catalog.json`, `clarify_turns.py`, `harness_plan.py`
  - **Rollback**: revert the above files; `PHA_HEALTH_INTENT_CATALOG=0` turns off inheritance assist.
  - **Acceptance**: `pha_health_turn_resolver_selfcheck` H5/H5b + Jun11 T2 no longer false-hits lab_year.

## 2026-06-09

- **CONSENSUS_ACK: harness-opus48-v2026-06-08 read**
- Wave 3d-perception-v1 (P2 Registry/validation-tool direction · perception ledger subset):
  - Added `pha/wearable_metric_candidates.py`: `MetricCandidate` IR, screen-scoped extractors, scored global merge (replaces `source_line` length tie-break).
  - HRV: hero `AVERAGE … ms` parser with split-digit join; HRV only on `screen_type=hrv`; chart-axis candidates down-ranked.
  - `merge_wearable_parts` emits `candidates` in `merge_trace`; `hrv_snapshot_low_confidence` warning when snapshot below 12 ms.
  - F-layer: `hrv_regression_cases` in `golden_ocr.json`; PNG manifest + `scripts/pha_wearable_perception_regression.py`.
  - Rollback: `PHA_WEARABLE_CANDIDATE_MERGE=0` restores legacy regex merge.
- **Unchanged (aligned with consensus)**: Lane-O still skips VLM; CompareTable contract unchanged; TurnEvidencePlan / C-layer audit untouched.
- **Product extension (non-conflicting)**: merge defect where long explanatory text overpowered Hero KPI — continues stage3d-wearable-merge-and-gates-spec §2 coerce spirit.

# PHA bilingual stress plan (50× Chinese + 50× English multi-turn)

> **Language / 语言**：English (this document) · [中文](pha-bilingual-stress-plan.md)

> Local-test only. Uses the local warehouse and attachment assets; does not send personal data externally.

## Goals

| Dimension | How to verify |
|------|----------|
| Multi-turn continuity | Independent `session_id` per session, ≥8 turns; weak followups do not re-spam the full table |
| Memory / context | Same-session follow-up, correction, warehouse + screenshot combined lanes |
| Data honesty | Turn1 wearable ingest jun11 metrics reconcile; warehouse lipid/steps lanes |
| Loop mechanism | Failed-turn JSONL → `harness-loop harvest` produces candidates (offline evolution input) |
| Reply quality | Five-dimension rule score + **semantic LLM judge** (evidence grounding / professional tone / clarity / non-diagnosis boundary / locale naturalness) |

## Assets

- **English bank**: `rules/e2e_question_bank_en_v1.json` (50 sets, seed random)
- **Chinese bank**: `rules/e2e_question_bank_zh_50_v1.json` (50 sets; ZS01–ZS20 reuse original ZH v1 rich checks)
- **Attachments**: `PHA_JUN11_ASSETS` `IMG_690*.png` (six-panel wearable screenshots); optional `IMG_0313*` lab images
- **Warehouse**: finish Apple Health / lab ingest first so warehouse lanes have real data

## Run

### 1. Start PHA (another terminal)

```bash
cd agent-harness
source .venv/bin/activate   # if present
PYTHONPATH=. python -m pha.main
```

Confirm Ollama is available; default model `qwen2.5:7b-instruct` (override with `PHA_E2E_MODEL`).

### 2. Smoke (2 sessions each, a few minutes)

```bash
PHA_BILINGUAL_SMOKE=1 python3 scripts/pha_bilingual_stress_battery.py
```

### 3. Full (50 sessions each, expected hours)

```bash
PHA_PORT=8788 python3 scripts/pha_bilingual_stress_battery.py
```

Optional fixed seeds (reproducible):

```bash
PHA_E2E_EN_SEED=20260716 PHA_E2E_ZH_SEED=20260716 \
  python3 scripts/pha_bilingual_stress_battery.py
```

### 4. One locale only

```bash
python3 scripts/seed_e2e_question_bank_zh_50_v1.py
PHA_PORT=8788 PHA_E2E_BANK_SEED=20260716 \
  python3 scripts/pha_e2e_zh_stress_50x.py

PHA_PORT=8788 PHA_E2E_BANK_SEED=20260711 \
  python3 scripts/pha_e2e_en_stress_50x.py
```

### 5. Semantic professionalism review (LLM judge)

The stress orchestrator runs this after the battery by default (`PHA_SEMANTIC_JUDGE=1`). You can also run it on existing JSONL:

```bash
PYTHONPATH=. python3 scripts/pha_e2e_semantic_judge.py \
  --jsonl reports/e2e/bilingual_stress_full_20260716/en/en_stress_50x_....jsonl \
  --locale en \
  --out-dir reports/e2e/bilingual_stress_full_20260716/semantic/en \
  --max-turns 40

PYTHONPATH=. python3 scripts/pha_e2e_semantic_judge.py \
  --jsonl reports/e2e/bilingual_stress_full_20260716/zh/zh_stress_50x_....jsonl \
  --locale zh \
  --out-dir reports/e2e/bilingual_stress_full_20260716/semantic/zh \
  --max-turns 40
```

| Env var | Default | Meaning |
|----------|------|------|
| `PHA_SEMANTIC_JUDGE` | `1` | Whether to run judge at orchestrator end; `0` skips |
| `PHA_SEMANTIC_MAX_TURNS` | smoke 12 / full 40 | Max reviewed turns per locale (stratified sample, not all ~800 turns) |
| `PHA_SEMANTIC_MODEL` | same as `PHA_E2E_MODEL` | Judge model (local Ollama) |
| `PHA_SEMANTIC_MIN_ANSWER_LEN` | `80` | Short replies (thanks/ok) skipped by default; prefer substantive answers |

Score dimensions (each 0–100): `evidence_grounding` · `professional_tone` · `clarity_structure` · `non_diagnostic_boundary` · `locale_naturalness` · `overall`.

**Boundary**: the judge scores “discourse professionalism and citation habit”, **not** medical correctness; it is not a diagnosis gold standard.

## Outputs

Default directory: `reports/e2e/bilingual_stress_<UTC>/`

| File | Notes |
|------|------|
| `plan.json` | This run’s EN/ZH random seeds and commands |
| `en/*stress_50x*.jsonl` | English per-turn records (harness_profile, checks, metrics) |
| `zh/*stress_50x*.jsonl` | Chinese per-turn records |
| `quality_report.md` | Rule-quality means and lowest 10 turns |
| `semantic/{en,zh}/semantic_report_*.md` | **Semantic professionalism** reports |
| `semantic/{en,zh}/semantic_judge_*.jsonl` | Per-turn judge scores and flags |
| `loop_harvest/*/candidates.jsonl` | Failed-sample harvest results |
| `summary.json` | Overview exit code and paths |

## Loop follow-on (human; do not auto-write catalog)

```bash
# Example: run reflection critic on English fails (JSONL must exist)
PYTHONPATH=. python scripts/pha_reflection_critic.py \
  --e2e-jsonl reports/e2e/bilingual_stress_.../en/en_stress_50x_....jsonl
```

Human-review proposals per [`docs/loop-evolution-human-in-the-loop-sop.en.md`](loop-evolution-human-in-the-loop-sop.en.md); **forbid** auto-merging catalog.

## Pass standard (suggested)

- Automated checks: `failed turns = 0` (each runner exit 0)
- Rule quality: bilingual `mean_total` ≥ 70 (`quality_report`)
- **Semantic quality**: bilingual `mean_overall` ≥ 70; `diagnosis_language` / `invented_number` flags need human spot-check
- Loop: harvest having signal proves failed JSONL can be consumed offline; whether to adopt a patch is a human decision

## Semantic debt (Track 3)

After full bilingual stress, semantic judge emits `diagnosis_language` / `invented_number` flags. They are **not all product defects**: some are wrong-domain answers or diagnosis tone (real debt); some are warehouse templates mislabeled (judge false positive). The process is four fixed steps; do not skip classification and jump to prompt edits.

### Process

| Step | Do | Output (local, not in git by default) |
|------|--------|---------------------------|
| **3.1** | Extract flagged turns from `semantic_judge_*.jsonl` | `reports/e2e/track3_*/flagged_turns.jsonl` |
| **3.2** | Human label **A / B / C** (can stack) | `classification_*.md` |
| **3.3** | Change product or judge by priority (table below) | code + selfcheck / live spot-check |
| **3.4** | Rerun live + judge on the flag-source session subset | `track3_4_respot_*`; expect `diagnosis_language` / `invented_number` ↓, `mean_overall` not down |

### A / B / C definitions

| Class | Meaning | How to change |
|------|------|------|
| **A** | Real: invented/wrong numbers, or answering off-topic with specific values | skip-LLM / warehouse single-metric focus / weak intent must not pull labs / POST_AUDIT |
| **B** | Real: diagnosis tone (`Differential diagnosis`, confirmed-diagnosis implication) | Soul non-diagnosis hard constraint + presentation rewrite titles |
| **C** | Judge false positive: numbers from warehouse/screenshots, or clarify questions | tighten judge prompt; drop `invented_number` after `numerics_manifest` / warehouse-template cross |

### 3.3 Landed fix strategies (对照)

| Debt | Strategy | Main landing |
|------|------|----------|
| B: EN diagnosis sections | Forbid Differential / 鉴别诊断 titles; use “Related markers / 相关指标对照” | `chat_message_stack` Soul; `presentation_filter` / `wearable_presentation` |
| A: weak intent “use Chinese from now on” | Locale preference only → skip-LLM, no lab narrative inject | `response_language.is_locale_preference_only`; `chat_skip_llm` |
| A: boundary confirm “this is not medical advice, right?” | Fixed non-diagnosis statement; forbid diagnosis sections | `chat_skip_llm` |
| A: warehouse wrong metric (steps / SpO2) | EN spoken triggers + single-metric focus | `wearable_bundle.schema.json`; `infer_single_metric_focus_ids` |
| C: warehouse mean mislabeled invented | judge prompt + post-filter | `pha_e2e_semantic_judge.py` |

### 3.4 Respot (reproducible)

Rerun the session subset from the 3.2 table (needs local PHA + Ollama), then semantic-judge the output JSONL (`--max-turns` covers all substantive turns in the subset):

```bash
# Example: flag-source sessions (adjust with the 3.2 table)
PHA_PORT=8788 PHA_E2E_BANK_SEED=20260716 \
  PHA_E2E_SESSIONS=EN07,EN16,EN21,EN22,EN23,EN28,EN38,EN42,EN43,EN47 \
  PHA_E2E_REPORT_DIR=reports/e2e/track3_4_respot_<date>/en \
  python3 scripts/pha_e2e_en_stress_50x.py

PHA_PORT=8788 PHA_E2E_BANK_SEED=20260716 \
  PHA_E2E_SESSIONS=ZS31,ZS38 \
  PHA_E2E_REPORT_DIR=reports/e2e/track3_4_respot_<date>/zh \
  python3 scripts/pha_e2e_zh_stress_50x.py

PYTHONPATH=. python3 scripts/pha_e2e_semantic_judge.py \
  --jsonl reports/e2e/track3_4_respot_<date>/en/en_stress_50x_....jsonl \
  --locale en --out-dir reports/e2e/track3_4_respot_<date>/semantic/en \
  --max-turns 200

PYTHONPATH=. python3 scripts/pha_e2e_semantic_judge.py \
  --jsonl reports/e2e/track3_4_respot_<date>/zh/zh_stress_50x_....jsonl \
  --locale zh --out-dir reports/e2e/track3_4_respot_<date>/semantic/zh \
  --max-turns 200
```

**Pass bar (vs same-seed full baseline spot-check)**: subset `diagnosis_language` + true `invented_number` (excluding already post-filtered C) should drop clearly; `mean_overall` not below the full baseline (EN≈91 / ZH≈94 magnitude; small fluctuation OK).

**3.4 live (2026-07-17, `PHA_E2E_BANK_SEED=20260716`, dir `reports/e2e/track3_4_respot_20260717/`)**:

| Item | Baseline (full spot-check 40+40) | Respot (flag-session subset) |
|------|---------------------------|------------------------|
| Live fails | — | EN 80 / ZH 17 turns, **fails=0** |
| `Differential` / 鉴别诊断 titles | many turns | full-subset JSONL **0 hits** |
| Judge `diagnosis_language` | EN 5 / ZH 1 | **EN 0 / ZH 0** |
| Judge `invented_number` | EN 7 / ZH 2 | EN 4 / ZH 2 (mostly warehouse truth, leftover C) |
| `mean_overall` | EN 91.2 / ZH 94.6 | **EN 95.6 / ZH 95.3** (not down) |
| Original 12 flagged turns product check | — | **12/12 PASS** (incl. ZS31 locale confirm, ZS38 boundary statement, EN47 SpO2, EN21 steps) |

> `reports/e2e/` contains dialog and metric excerpts and is **gitignore for the whole tree**; semantic-debt tables and respot reports stay local.

## New scripts

| Script | Role |
|------|------|
| `scripts/seed_e2e_question_bank_zh_50_v1.py` | Generate Chinese 50-set bank |
| `scripts/pha_e2e_zh_stress_50x.py` | Chinese 50× live stress |
| `scripts/pha_e2e_quality_score.py` | Rule-quality scoring |
| `scripts/pha_e2e_semantic_judge.py` | **Semantic professionalism LLM judge** |
| `scripts/pha_bilingual_stress_battery.py` | Bilingual orchestration + reports + (default) semantic review |

English 50× reuses existing `scripts/pha_e2e_en_stress_50x.py`.

# Stage 3C live regression E2E Report (2026-06-15)

> **Language / 语言**：English (this document) · [中文](stage3c-browser-e2e-report-2026-06-15.md)

- **Build**: `pha-v2.3.32-full-import-only`
- **Endpoint**: `http://127.0.0.1:8788`
- **Model**: `qwen2.5:7b-instruct`
- **Flags**: `PHA_GROUNDED_COMPOSER=1`, `PHA_CLARIFY_TURNS=1`, `PHA_HEALTH_TURN_RESOLVER=1`, `PHA_EPISODIC_ALL_PROFILES=1`
- **Prerequisite**: 2026-06-10 wearable OCR / single-metric focus fix + this round **skip_llm architecture extension** + **P0/P1 wrap-up** (see `harness-change-log.md` 2026-06-15)

## Task #1 — 20× multi-turn Battery

Script: `scripts/pha_e2e_browser_battery_20x.py`  
Compare baseline: `battery_20x_20260615T050322Z.md` (pre-fix, 12/70 fail)

### Evolution

| Stage | Failed turns | Key fix |
|------|----------|----------|
| Pre-fix (20 sessions) | **12/70** | — |
| P1 wrap-up (6-session subset) | **0/32** | parse reuse, harness correction |
| P2 parallel OCR (20 sessions) | **1/70** (S09 harness false fail) | OCR parallel + NUMERICS_MANIFEST slot |

### Final subset (2026-06-15T150347Z)

- **Sessions**: S01, S04, S05, S07, S14, S20 (`PHA_E2E_SESSIONS=...`)
- **Result**: **32/32 PASS, 0 fail**, wall clock **713.9s**
- Report: `/tmp/pha-e2e-20x/battery_20x_20260615T150347Z.md`
- Log: `/tmp/pha-battery-subset2.log`

| Scene | Pre-fix | Final | Verdict |
|------|--------|------|------|
| S07 warehouse-only HRV | 68.6s LLM | **2.3–2.7s** manifest | **PASS** |
| S04 “vs last week?” T4 | 36.8s LLM | **0.1s** episodic skip_llm | **PASS** |
| S05 “how long deep sleep” T4 | 35.9s LLM invented | **0.1s** no-snapshot deterministic reply | **PASS** |
| S14 “ok to exercise tomorrow?” T6 | — | **0.2s** workout-advice template | **PASS** |
| S20 “how about sleep” T3 | warehouse 8.09h mixed in | **CompareTable 6h32** | **PASS** |
| First-turn 6 images T1 | ~187s LLM | ~122–135s OCR + CompareTable skip_llm | numbers correct; time is mostly OCR |

> Optional full 20-session rerun: `PHA_PORT=8788 python3 scripts/pha_e2e_browser_battery_20x.py` (about ~60min)

## Task #2 — Jun11 seven-turn golden E2E

Script: `scripts/pha_e2e_jun11_realdevice_multiturn.py`  
Log: `/tmp/pha-jun11-final2.log`  
**Result: PASS all 7 turns**

| Turn | Message | Latency | Channel | Points |
|------|------|------|------|------|
| T1 | 6 images + workout advice | 136.6s | **CompareTable first-turn skip_llm** | sleep 6hr32min, HRV 34, workouts 20 |
| T2 | how are lipids | 0.0s | clarify chips | 2023/2025 |
| T3 | how is HRV | 0.1s | single-metric focus | 34 ms |
| T4 | please verify sleep | 0.1s | correction focus | 6h32 + Awake note |
| T5 | workout-count source | 1.0s | correction focus | 20 days / 4 weeks |
| T6 | re-parse sleep | 0.1s | remerge, no re-upload | 6h32 |
| T7 | recent steps | 0.1s | manifest focus | 14553 steps |

## Task #3 — Browser CDP three-scene sample

| Scene | Browser action | Verify | Result |
|------|------------|----------|------|
| **B1 warehouse-only HRV** | new session + pick `qwen2.5:7b-instruct` + send “how is my recent HRV?” | same API path + S07 rerun | **PASS** (warehouse focus `32.95ms`) |
| **B2 first-turn 6-image upload** | same path as T1 (`app.js` → `/api/chat`) | Jun11 T1 status=`screenshot first turn: CompareTable ledger summary` | **PASS** |
| **B3 sleep correction** | load historical session | Jun11 T4 + S05 T3 | **PASS** (0.1s, `6 hours 32 minutes` + TIME ASLEEP note) |

Browser CDP note: during concurrent battery, `#chat-stream` occasionally did not render history (empty accessibility snapshot); same source as `GET /api/chat/sessions/{id}/messages`. Accept on API E2E + Jun11 golden.

## Alignment with consensus / design

| Hard constraint (harness-consensus) | This round |
|---|---|
| TurnEvidencePlan before LLM | ✅ skip_llm after `plan_pre_llm`, before LLM stream |
| CompareTable is wearable-number SSO | ✅ first turn / correction / single-metric all from CompareTable |
| C-layer numbers auditable | ✅ skip_llm path does not invent via LLM |
| Forbid LLM computing Raw | ✅ manifest / CompareTable deterministic aggregation |
| Composer fact_card | ✅ skip_llm path emits `meta` / `fact_card` / `follow_ups` (P1-7) |

## P2 Backlog (part landed 2026-06-16)

- ✅ First-turn 6-image OCR parallelized (T1 **136s → 55s**, Jun11 golden 7/7 PASS)
- ✅ `wearable_only` official `NUMERICS_MANIFEST` Tier0 slot (steps etc. registry-auditable inject)
- ⏳ Full 20× battery rerun (P2 accepting)
- Not done (no corner-case fix): S20 broad follow-up LLM ~30–40s; deep-sleep OCR staged extract

### P2 full 20× rerun (2026-06-16T061131Z)

- **69/70 PASS**; only fail **S09 T1** harness applying `check_metric_focus` to first-turn 6-image full table (fixed `only_turns(2,3)`)
- Wall clock **1910s** (**58%** down from pre-fix 4563s); typical first-turn T1 **~52–60s** (**~55%** down from ~130s)
- Report: `/tmp/pha-e2e-20x/battery_20x_20260616T061131Z.md`

## Rollback

- Remove `user_message_needs_wearable_session_reuse` call and episodic/deep-sleep/workout helpers to restore the old `_reuse_parse` guard.
- No destructive schema / env changes.

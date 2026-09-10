# PHA iOS / proactive agent plan

> **Language / 语言**：English (this document) · [中文](pha-ios-proactive-roadmap.md)

> Upstream: [PHA constitution](pha-pm-constitution.en.md) (anti-hardcode, telemetry-driven, deterministic harness)  
> Product source of truth: [PRD](prd-pha-ios-proactive-agent-v1.en.md)  
> Metric allowlist: [wearable registry](wearable-metric-registry-v1.md)  
> Startup: [stability plan](stability-remediation-plan-2026-06-10.md) — `main.py` / bind / restart only via official `bash scripts/pha_restart_accept.sh`

On conflict: **numeric honesty and fail-closed beat “more proactive” or “more coach-like”.**  
M1-P6 (sleep rows + HRV SDNN) T9 passed 2026-09-10. Do not start Watch App / APNs / cloud before M2.

---

## Done (through 2026-09-06)

| Card | Result |
|------|--------|
| M0-P0–P2 | ingest + real-device steps + time-slot/empty-window fail-closed + Hero point-day bind |
| M1-P0–P2 | no-LLM fact-card JSON + iPhone Shortcut notification + assessment layer |
| M1-P3 | short lock-screen note + `GET /proactive/fact-card/view` full card (Shortcut “Open URL”) |
| M1-P4 | metrics = registry `fact_card.eligible` + user checks; no Python dead list |
| M1-P5 | quantity real-device ingest: 2026-09-06 active energy **701.69** kcal + RHR **60** |
| M1-P6 | 2026-09-10 T9: maintainer confirmed 9/8–9/10 Health.app vs daily table (asleep/awake/core/deep/REM); HRV already matched |

Public README first screen stays harness-first. Do not change `packages/harness_core`.

---

## Next cuts (in order, do not skip)

### 1. M1-P6 device: PHA sync sleep · DONE 2026-09-10

T9 verbal confirm 9/8–9/10 roughly matches. Task card [`pha-healthkit-sleep-hrv.md`](pha-healthkit-sleep-hrv.md).

### 1b. M1-P7 progressive baseline + reference layer (no LLM) · DONE 2026-09-07

- Per metric 90d → 365d → all; card writes “vs your last 12 months N nights/days”
- Registry `reference_range` (sleep total / RHR / steps) → T1 disclosure; no HRV population range; deep/REM % not in v1 (2026-09-10)
- Card composite three bands; missing inputs → “not combined”

### 1c. M1-P8 HRV column semantics (plus harness ACK) · DONE 2026-09-07

- Copy daily history into `hrv_sdnn_ms`; samples `hrv`→`hrv_sdnn`; registry primary = SDNN
- Script: `scripts/pha_migrate_hrv_rmssd_to_sdnn.py` (`--dry-run` first)

### 1d. M1-P9 assessment prompt + tap-to-interpret (FR-2.9 / FR-6) · DONE 2026-09-07

- prefs `assessment_prompt` save/echo; `POST/GET /proactive/fact-card/interpret` async cache; `chat_service` + atom audit; separate full-card block
- No bare Ollama, no pre-generate, not in the notification; M3 App only wires the same endpoint

### 1e. M1-P9.1 → P10 → P11 → P9.2 → P9.3 (handoff: [`handoff-2026-09-08-fact-card-interpret-v2.md`](handoff-2026-09-08-fact-card-interpret-v2.md))

- **P9.1** interpret-only harness profile `fact_card_interpret`: manifest from the card; dates are their own audit class; off-card numbers only inside T1 blocks; revert the 9/7 “only block ≥100” relaxation
- **P10** registry `temporal.kind` (accrual / daily_lagged / overnight / rolling_mean): morning card can show “RHR 60 (Sep 7, latest)”; in-progress accrual unbanded; empty Find skips POST
- **P11** checkboxes = what you see + Shortcut syncs the full pack (**maintainer 9/8 08:27, PRD v1.7 FR-1.5 / FR-2.7**): no implicit sleep-stage expand; Shortcut Find from registry universe, ignores prefs; changing checks refreshes without reinstall. **Same agent as P10, one reinstall**
- **P12** priority pack phase 1: SpO2 / respiratory rate / VO2max on device; Find catalog. Wrist temp deferred to the second checkbox batch (2026-09-10). Zip is final truth.
- **P9.2** local TZ + locale dates + plain text + cache key + numeric-direction band labels (DONE 2026-09-08)
- **P9.3** device + edge acceptance **DONE 2026-09-09**: cross-day cache isolation; Ollama down → `model_unavailable` (see change-log)

### 2. M2 thin App (when Shortcut sync is no longer tolerable)

- HealthKit auth, server URL, token, last-sync time
- Foreground “sync now” = successful Shortcut path
- **Fact-card page** (openable from a notification; no Safari + query token)
- Settings write the same prefs
- Meds/supplements: user registry only → local notifications
- Best-effort background sync; failures visible

### 3. M3 / M4 (do not open until triggers exist)

- M3: App talks to the **same** interpret/chat endpoint (capability already on the full-card page via M1-P9); proactive path still forbids LLM assessment/fill; a tap = spoken request, not proactive
- M4: on-device inference needs a device + model plan

---

## Always on this track

- Watch data only via iPhone HealthKit → ingest → Mac ledger
- Proactive path does not fill numbers with an LLM; ingest is fail-closed
- New metrics: registry row + daily column first, then user checks; no special `if` in `fact_card.py`
- Restart via the official script; do not change the public README narrative

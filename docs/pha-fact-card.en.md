# PHA fact card (M1)

> **Language / 语言**：English (this document) · [中文](pha-fact-card.md)

Mac builds JSON from `wearable_daily` with **no LLM**. The iPhone Shortcut shows a short notification, then **opens the full-card web page**.  
Not chat, not diagnosis, not APNs.

```bash
python scripts/pha_fact_card_selfcheck.py
python scripts/pha_fact_card.py          # print the card for user_id=default
```

## Two reach layers

| Layer | Use |
|-------|-----|
| Lock-screen notification | as-of / today? / coverage / “open full card”. iOS truncates; do not stuff the metric list into the body |
| Full card | `GET /proactive/fact-card/view`: selected metrics + assessment + advice + checkboxes |

## Two JSON layers

| Layer | Fields | Meaning |
|-------|--------|---------|
| Numbers | `facts.as_of` / `facts.stale` / `facts.metrics` | `as_of = MAX(day)`; each row uses registry `temporal` and writes the real `day` / `freshness` / `partial_day`. **Do not label a non-today value as today** |
| Freshness | `metrics[].freshness` / `partial_day` / `as_of_time` | `accrual` in progress today is unbanded; `daily_lagged` / `overnight` look back within `freshness_days` (overnight default 2 days; zip still not remapped to wake day); `latest` is the most recent sample (VO2max 90 days) and does not count toward coverage. **M1-P10 / P12 shipped** |
| Selection | `facts.selection.enabled_metric_ids` | User-checked; allowlist is the registry, not a Python list |
| Assessment | `assessment.advice` | Rule bands vs a **progressive personal baseline** (90d → 365d → all history, first window with n ≥ 7; JSON writes `baseline_window` / `baseline_n`) + **fixed templates**. Only if all three windows have n&lt;7: “history short n/7”. **M1-P7 shipped** |
| Reference | `metrics[].reference` inside `assessment` | Selected metrics with registry `fact_card.reference_range` get one `【参考标准】…（来源：…，请自行查证，非医疗建议）` line plus in/out of range. No population range for absolute HRV. **M1-P7 shipped** (sleep total / RHR / steps; deep/REM % not in v1) |
| Interpretation | `interpretation` (only after the user taps) | `chat_service` + the **single** harness `fact_card` numerics audit (personal/decimals must match; population integers may pass with telemetry; T1 zh/en equal); `POST/GET /proactive/fact-card/interpret` async cache; separate block on the full card. **M1-P9 / P9.4 shipped** (FR-6) |

`notification.body` is the lock-screen teaser; `notification.open_path` points at the full card.

**After M1-P7/P8/P10/P11**: assessment uses progressive windows; HRV primary column is `hrv_sdnn_ms`; metrics take values by registry `temporal` and write the real date. The card set = the checkbox set.

**Shortcuts vs checkboxes (PRD v1.9 FR-1.5)**: “PHA 同步健康” is generated from Find catalog `device_verified` (steps, active energy, RHR, HRV, SpO2, respiratory rate, VO2max), independent of checkboxes. Wrist temperature is not in the Shortcut yet. JSON carries `pack_version`; reinstall only when the pack changes. Checkboxes only control what the card shows. New metrics must be added to [`shortcut_health_find_catalog.json`](../storage/registry/shortcut_health_find_catalog.json) first — never guess Find labels. A zip import overwrites same-day Shortcut increments.

**M1-P12**: VO2max is last reading (180-day window), not in coverage. Full-card checkboxes group as Sleep / Heart / Activity / Respiration & SpO2 / Fitness.

**M1-P9.2 / P9.3**: full-card dates and chrome follow prefs `locale` (`zh-CN` / `en-US`); **git default is en-US**. Machine JSON dates stay ISO. There is no separate date-format control. iPhone Safari interpretation is proven. Stopping Ollama / cross-day cache is a maintainer check.

## How to change metrics (no code)

1. **User**: open “Metrics I want to see” at the bottom of the full card, check, save. Prefs live in gitignored `data/fact_card_prefs.json`.
2. **New optional metric**: daily column already exists → set `fact_card.eligible` in `storage/registry/wearable_metric_registry.json`. Do not add `if` in `fact_card.py`.
3. **Ingest allowlist** is still PRD FR-1.4; visible ≠ POST-able from HealthKit.

```text
GET/PUT /proactive/fact-card/prefs?user_id=default
Header: X-PHA-Ingest-Token
```

## HTTP

```text
GET /proactive/fact-card?user_id=default
GET /proactive/fact-card/view?user_id=default
Header: X-PHA-Ingest-Token: <same token as ingest>
```

Safari opened from a Shortcut may use query `token=` (header or query). Token unset → 503; wrong token → 401.

## How the iPhone gets a card every day

Clone onboarding: **[Mac + iPhone LAN handbook](pha-fact-card-lan.md)** ([中文](pha-fact-card-lan.zh.md)). The public repo ships one template with **no token**: [shortcuts/pha-daily.shortcut](../shortcuts/pha-daily.shortcut) (import asks for Mac URL and token). Maintainer short path below (outputs are gitignored).

1. Generate Shortcuts locally (token only under gitignored `data/local_shortcuts/`):

```bash
python scripts/macos/build_pha_ingest_shortcuts.py
```

You get `pha-daily.shortcut` (“PHA Daily”, URL + token baked). Debug builds still emit the split sleep / health / fact-card Shortcuts. **AirDrop again**; old Shortcuts will not open the full card.

2. Run **PHA Daily** once: short notification, then Safari full card (Mac PHA must be listening; the phone must reach LAN / `.local`). Notification only and “no URL” means a stale Shortcut.

3. **Daily**: Shortcuts app → Automation → Time of Day → run **PHA Daily** → **Run Immediately**.

4. Stock lock-screen banners usually **cannot** open a custom URL. Re-run the Shortcut (or wait for the M2 app).

If today’s HealthKit is not synced, copy says “as of yesterday (not today)”. Numbers stay the ledger’s last day; they are never pretended to be today.

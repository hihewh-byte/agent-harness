# HealthKit ingest (M0)

> **Language / 语言**：English (this document) · [中文](healthkit-ingest.md)

Push Watch samples from iPhone Health onto this Mac’s PHA: `POST /ingest/healthkit`.  
**Not** zip import (`POST /data/upload`). A Mac **cannot** talk to the Watch directly.

Clone onboarding: [pha-fact-card-lan.md](pha-fact-card-lan.md) ([中文](pha-fact-card-lan.zh.md)) — same Wi-Fi, one **PHA Daily** Shortcut, no LLM for the daily card. Public template: [shortcuts/pha-daily.shortcut](../shortcuts/pha-daily.shortcut) (import asks for URL and token; no secrets in git).

Self-check (fake data, temp DB):

```bash
python scripts/pha_healthkit_ingest_selfcheck.py
```

Do not claim “the proactive agent is live” until this is green. A real-device Shortcut (M0-P1) is what proves the pipe.

---

## 0. Maintainer machine (do not commit values)

Configure gitignored `.env` and restart with official `scripts/pha_restart_accept.sh` (launchd):

| Item | Rule |
|------|------|
| Bind | `0.0.0.0:8788` so the phone can connect |
| Hostname | `http://<LocalHostName>.local:8788` (survives DHCP). **Never write the real name in git** |
| LAN IP | changes; old IPs inside Shortcuts time out |
| Token | `.env` `PHA_INGEST_TOKEN` (never commit) |
| Timezone | `PHA_INGEST_TZ` (example `Asia/Shanghai`) |
| Health access | Quantity pack: steps, active energy, RHR, HRV, SpO2, respiratory rate, VO2max. Sleep is a separate Shortcut. Wrist temperature is not in the current pack |

Signed Shortcuts (URL + token) stay under gitignored `data/local_shortcuts/`. Generator: `scripts/macos/build_pha_ingest_shortcuts.py`.

On the iPhone, delete older PHA Shortcuts before importing. Timeouts: Settings → Privacy & Security → Local Network → Shortcuts ON.

---

## 1. Mac prep

1. In `.env` (**do not commit a real token**):

```bash
PHA_INGEST_TOKEN='replace-with-a-long-random-string'
PHA_INGEST_TZ=Asia/Shanghai
```

2. Default PHA binds `127.0.0.1` — **the phone cannot hit that**. Same Wi-Fi or Tailscale:

```bash
PHA_HOST=0.0.0.0
```

Then restart PHA as usual. Expose ingest only on your LAN/VPN, not the public internet.

3. Probe:

```bash
curl -sS -X POST "http://<Mac-Tailscale-or-LAN-IP>:8788/ingest/healthkit" \
  -H "Content-Type: application/json" \
  -H "X-PHA-Ingest-Token: $PHA_INGEST_TOKEN" \
  -d @scripts/fixtures/healthkit_ingest_sample.json
```

Success: `{"ok": true, "inserted": ..., "source": "healthkit", ...}`.  
Token unset → 503; wrong token → 401.

---

## 2. JSON contract

```json
{
  "user_id": "default",
  "pack_version": "2026.09.08.priority-1",
  "token": "optional; Header preferred",
  "samples": [
    {
      "metric_type": "hrv",
      "timestamp": "2026-08-30T08:15:00+08:00",
      "value": 42.0,
      "unit": "ms",
      "source": "healthkit"
    }
  ]
}
```

| Field | Rule |
|-------|------|
| `metric_type` | `hrv` `hrv_sdnn` `rhr` `steps` `sleep_hours` `sleep_core` `sleep_deep` `sleep_rem` `sleep_in_bed` `sleep_awake` `active_energy` **`spo2` `respiratory_rate` `vo2max` `wrist_temp` (M1-P12)**. SDNN does not write RMSSD. Sleep hours must be in (0, 16]. Unknown type: **drop that sample**, do not guess. |
| `timestamp` | ISO-8601. Mapped to the local calendar day via `PHA_INGEST_TZ`. Unparseable → **drop the batch** (400). |
| `value` | Finite number. Unknown unit or magnitude out of range → **whole batch 400**. Server normalizes SpO2 fraction→%, respiratory `count/s`→bpm, wrist °F→°C. |
| `pack_version` | Shortcut pack (`shortcut_pack_version` in the registry). Full card prompts reinstall when stale. |
| `source` | Must be `healthkit`. |
| Auth | Header `X-PHA-Ingest-Token` or body `token`. |

**Units (POST `unit` with the value; unknown unit rejected):**

| Metric | Value |
|--------|--------|
| `hrv` | milliseconds (warehouse RMSSD / legacy zip). Do not use this key for watch SDNN. |
| `hrv_sdnn` | milliseconds (HealthKit SDNN day mean) |
| `rhr` | bpm |
| `steps` | day total (one cumulative row per day; do not POST the same cumulative hourly) |
| `sleep_hours` | **hours** (not seconds) |
| `active_energy` | kcal |
| `spo2` | percent or 0–1 fraction (server → %) |
| `respiratory_rate` | breaths/min; `count/s` × 60 |
| `vo2max` | mL/kg/min |
| `wrist_temp` | °C; °F converted |

Idempotency key: `healthkit|{user}|{metric}|{local-iso}|healthkit`. Same second + metric → `INSERT OR IGNORE`.

---

## 3. iPhone Shortcuts (M0-P1)

Prefer the generated **PHA Daily** template (or local signed copies). iPhone and Mac on the same Wi-Fi; run once; allow Health.

Manual build (debug only):

1. Shortcuts → new Shortcut, name e.g. `PHA Sync Health`.
2. **Find Health samples** per metric (or one metric first): HRV / RHR / steps / sleep / active energy; range today (or last 24h).
3. Repeat / Dictionary into:
   - `metric_type`: English names from the table
   - `timestamp`: sample start ISO string
   - `value`: number (Quantity: Calculate + 0; do not stuff `16 count` into JSON)
   - `source`: `healthkit`
4. Get Contents of URL: `POST` `http://<Mac-IP>:8788/ingest/healthkit` with `Content-Type` + `X-PHA-Ingest-Token` and body `{"user_id":"default","samples":[...]}`.
5. Automation (optional): once an evening. Background runs may miss; v1 trusts ledger `as_of`.

Pass criteria (on the Mac):

```bash
sqlite3 data/pha_storage.db \
  "SELECT metric_type, timestamp, value, sample_id FROM wearable_data WHERE sample_id LIKE 'healthkit|%' ORDER BY timestamp DESC LIMIT 20;"
sqlite3 data/pha_storage.db \
  "SELECT day, steps, resting_heart_rate_bpm, hrv_rmssd_ms, sleep_hours, active_energy_kcal FROM wearable_daily ORDER BY day DESC LIMIT 5;"
```

`as_of` (daily `day`) must be the **same calendar day** as Health.app, with sane magnitude (HRV tens of ms, not 0.04).

If the phone cannot reach the Mac: Tailscale up on both, firewall allows 8788, PHA restarted with `PHA_HOST=0.0.0.0`.

---

## 4. Red lines

- Do not send health JSON to a project server; only your Mac / VPN.
- Failed ingest does not backfill samples and does not use an LLM to invent numbers.
- Zip import stays on its own path. A full zip **does not delete** `sample_id` rows starting with `healthkit|`; after import, daily rebuilds; steps take **max** across sources.

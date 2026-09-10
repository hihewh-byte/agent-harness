# PHA web-service availability remediation plan (2026-06-08)

> **Language / 语言**：English (this document) · [中文](startup-availability-remediation-plan-2026-06-08.md)

> Status: pending implementation (design + execution checklist)  
> Scope: only “fails to start / cannot stay available”  
> Related: `startup-stability-2026-06-07.md`, `incident-analysis-chat-hero-2026-06-07.md`, `pha-architecture-evolution-v2.3.md`

---

## 1. Problem definition (what to fix)

The user-facing pain is not “an endpoint occasionally errors”. It is:

1. Startup is sometimes slow or looks like it never opens (health check stays unreachable).
2. Even after a successful start, the service can die later (no keep-alive policy).
3. Start entries (script / App / manual) behave inconsistently, so diagnosis is expensive.

---

## 2. Confirmed root causes (code layer)

### R1. Startup path includes heavy work that slows / blocks availability

- `pha/main.py` lifespan start also triggers data audit, memory hydrate, and index backfill.
- `store.hydrate_from_sqlite()` itself triggers another backfill — duplicate heavy work risk.

Impact: as the database grows, time-to-first `/health` rises sharply and is misread as “the service won’t open”.

### R2. Background start is “single process + no supervisor”

- `scripts/pha_restart_accept.sh` uses `nohup python -m pha.main`; after accept there is no keep-alive.

Impact: the process is not pulled back up after exit — “it opened, then it didn’t”.

### R3. Start entries and port policy were historically inconsistent

- Main flow already uses `.env` `PHA_PORT=8788`, but some historical generators/scripts default to 8787.

Impact: the service may be healthy while the user hits the wrong port — a false “won’t open”.

### R4. Startup duty boundary drifted from the blueprint layers

- The blueprint wants layers, observability, and progressive enhancement; data-governance work currently sits on the synchronous start path, which hurts availability.

---

## 3. Fix goals (acceptance)

### G1. Start reachability

- After a cold start, `GET /health` is reachable within the target window (suggest < 5s, latest < 15s).

### G2. Sustained availability

- Without human intervention, the service stays reachable (at least a 24h accept window).

### G3. Start-entry consistency

- All official entries (script, macOS launcher, documented commands) share the same port and env behavior.

### G4. Rollback-able

- Each change batch can roll back independently without touching data files or existing API contracts.

---

## 4. Batched implementation (suggest 3 small PRs)

## PR-A (P0): Slim startup (restore “opens reliably” first)

### Changes

1. Move start-time heavy work off the blocking path: `run_startup_data_audit()`, `backfill_wearable_data_from_daily()` become background tasks or ops commands.
2. Eliminate duplicate backfill: keep one backfill entry (`main.py` or `store.py`, not both).
3. Layer start logs: print `startup_phase=core_ready` and `startup_phase=maintenance` clearly.

### Risk

- For a short window after start, some auxiliary indexes may not be ready.

### Rollback

- Restore old behavior with a feature flag (e.g. `PHA_STARTUP_MAINTENANCE_SYNC=1`).

### Acceptance

- 10 consecutive restarts: `/health` returns 200 within the threshold every time.

---

## PR-B (P0): Unify keep-alive (restore “stays up” first)

### Changes

1. Name one official keep-alive policy (pick one):
   - Dev default: foreground `PHA-Serve.command`;
   - Background: one controlled supervisor (`launchd` or `supervisord`; no mixed script watchdogs).
2. `pha_restart_accept.sh` only does “restart + accept”; it no longer implies daemon semantics.
3. Docs must distinguish “process exit = unavailable” vs “keep-alive mode”.

### Risk

- Switching supervisor needs a one-time migration note.

### Rollback

- Keep current `nohup` as fallback (labeled “no keep-alive”).

### Acceptance

- After a simulated process exit, keep-alive mode restores the listen port and `/health`.

---

## PR-C (P1): Converge entries and config (cut false alarms)

### Changes

1. All launchers read `.env` (port, log path, host).
2. Remove or mark historical 8787 script templates so new generators do not spread the old default.
3. On successful start, print one “unique access URL” (with port) and the build id.

### Risk

- Users with old habits may still hit 8787.

### Rollback

- Optionally keep a 8787 compatibility hint page or redirect.

### Acceptance

- After any official entry starts, the actual listen port matches the printed URL and the docs.

---

## 5. Alignment with the design blueprint

Against the “layer constitution” and “progressive enhancement” in `pha-architecture-evolution-v2.3.md`, add two execution constraints:

1. **Minimal start path**: L0/L1 availability first; maintenance work must not block reachability.
2. **Single ops source of truth**: port, entry, logs, and keep-alive are driven by one config source (`.env` + one supervisor).

---

## 6. Suggested order

1. PR-A first (fastest improvement on “won’t open”).
2. Then PR-B (“won’t stay up”).
3. Then PR-C (cut misreports and ops noise).

---

## 7. Suggested accept scripts (after implementation)

1. Cold-start stress: 10 consecutive restarts; record `/health` ready-time distribution.
2. Keep-alive stress: run 24h, probe every 30s, compute availability.
3. Entry consistency: `PHA-Serve.command` vs `pha_restart_accept.sh` (`PHA-Restart.command` is retired).

---

## 8. Current conclusion

“Always won’t open / always won’t stay” is not one bug. It is **heavy start + no supervisor + forked entries**.  
Fix startup slim-down and keep-alive unification first. Do not go back to mixed script watchdogs.

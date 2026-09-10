# Rollback note: v2.3.29 ← v2.3.30 / v2.3.31 (2026-06-07)

> **Language / 语言**：English (this document) · [中文](rollback-v2.3.29-architecture-diff.md)

> **Currently running build**: `pha-v2.3.29-wave4a-onboarding-ui-docker`  
> **Git**: `3c4a8ed` (tag `v2.3.29`)  
> **Why rollback**: uncommitted v2.3.30+ changes (daemon keep-alive, chat-crash fix) made the service unstable; page/chat intermittently unavailable.

---

## 1. Version timeline

| Version | Git | Status |
|------|-----|------|
| **v2.3.29** (current) | `3c4a8ed` / tag `v2.3.29` | Accepted; **production rollback target** |
| v2.3.30 | `3c801de` | Committed: `health_education` dual lane |
| v2.3.31 | uncommitted | Chat `UnboundLocalError` fix + `pha_daemon.sh` experiment |

---

## 2. Architecture diff overview

```text
v2.3.29                          v2.3.30                         v2.3.31 (unmerged)
─────────────────────────────────────────────────────────────────────────────────
lifestyle fallback               + health_education profile      same as v2.3.30
education via lifestyle+Patient State  pure education, no ledger  + chat_service import fix
                                                                
pha_restart_accept.sh             same                           depends on pha_daemon.sh
  lsof kill → nohup pha.main        same                           stop/start daemon
no watchdog                       no watchdog                    watchdog while-true (crash restart only)
                                                                
23 selfchecks                     24 (+health_education)         same 24
Wave 5 docs commit 03e0c88         included before 3c801de        —
```

---

## 3. Routing / Harness (added in v2.3.30; gone after rollback)

### v2.3.29 — education-class questions

- Schema fallback → **`lifestyle`**
- Inject: `SUPPLEMENT_BG` + `PATIENT_STATE_LAB` (Tier1)
- Soul: **full PHA three-step consult** medical soul
- Risk: generic pharmacology questions also carry personal-ledger context; the model may invent user numbers

### v2.3.30 — `health_education` dual lane (rolled back)

| Dimension | Not personal (education) | Personal |
|------|------------------|----------|
| Profile | `health_education` | `lifestyle` (unchanged) |
| Gate | `personal_relevance_gate` Level-1 text (zh/en symmetric) | Hits “I / my / my report” etc. |
| Tier0 | `MASTER_ANCHOR` + `TASK` | original lifestyle |
| Tier1 | **empty** (no Patient State / supplement background) | original lifestyle |
| Soul | `PHA_EDUCATION_SOUL` (bilingual; forbids three-step consult) | medical soul |
| Feature flag | `PHA_HEALTH_EDUCATION_GATE=1` (on by default) | — |

Insert point: `schema_intent_router.resolve_intent_route` calls `is_pure_health_education()` before the `lifestyle` fallback.

---

## 4. Process / ops model (v2.3.31 experiment, deleted)

### v2.3.29 (current)

```text
pha_restart_accept.sh
  → lsof -ti :8787 | kill -9
  → nohup .venv/bin/python -m pha.main
  → curl accept
```

- **Single process**, no auto-respawn; after Terminal/crash, restart by hand.
- macOS `PHA-Restart.app`: same kill-port + bare `pha.main` (matches the script).

### v2.3.31 experiment (removed via git clean)

- `scripts/pha_daemon.sh`: bash watchdog + `while true`; restarts 2s after **pha.main exits** (not a timed kill).
- `pha_restart_accept.sh` changed to `daemon stop/start`.
- `scripts/pha_install_service.sh`: LaunchAgent KeepAlive (failed with **Operation not permitted** under `~/Documents` because of macOS permissions).
- **Conflict**: old `PHA-Restart.app` killed 8787 but not the watchdog → raced the daemon for the port; later unified onto daemon in the experiment, then rolled back before it was stable.

---

## 5. Chat path (v2.3.31 fix; may still exist after rollback)

| Issue | v2.3.29 | v2.3.31 fix |
|------|---------|--------------|
| Wearable questions SSE drop `HTTP 0` | **Duplicate** `import user_message_needs_wearable_query` inside `stream_pha_chat_events` → `UnboundLocalError`, process crash | Remove the in-function duplicate import |
| Repro sentence | “Based on my body metrics over the past half year, give me some exercise suggestions” → `wearable_only` | After fix, curl E2E passes |

**After rollback**: if wearable chat `Failed to fetch` returns, cherry-pick the one-line duplicate-import deletion in `chat_service.py`. **Do not** bring in the daemon.

---

## 6. Doc diff (historical commits stay on remote; rollback does not delete them)

| File | Introduced in | Content |
|------|----------|------|
| `docs/wave5-harness-evolution-plan.md` | `03e0c88` | Wave 5 Harness evolution (TurnOrchestrator, ControlledFetchLoop) |
| `docs/pha-architecture-evolution-v2.3.md` §8 | `03e0c88` | PHA vs Claude Code, education FAQ |

After rollback to `v2.3.29` the worktree **does not contain** those docs (they live in `03e0c88`); for read-only reference: `git show 03e0c88:docs/wave5-harness-evolution-plan.md`.

---

## 7. Restore / forward path

```bash
# Stay on v2.3.29 (current)
bash scripts/pha_restart_accept.sh

# Restore education dual lane only (no daemon)
git cherry-pick 3c801de

# Fix wearable chat crash only (minimal patch)
# Delete the duplicate import of user_message_needs_wearable_query inside
# stream_pha_chat_events in chat_service.py

# Retry daemon (needs its own PR + unified macOS launcher)
# Restore pha_daemon.sh from before revert and soak 24h
```

---

## 8. Acceptance commands (v2.3.29)

```bash
cd agent-harness
bash scripts/pha_restart_accept.sh   # → Acceptance PASSED
bash scripts/run_selfchecks.sh       # 23/23
open http://127.0.0.1:8787
```

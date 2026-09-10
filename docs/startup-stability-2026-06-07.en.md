# PHA startup and keep-alive root causes (2026-06-07)

> **Language / 语言**：English (this document) · [中文](startup-stability-2026-06-07.md)

> **Current recommended start**: `bash scripts/pha_restart_accept.sh` or double-click `scripts/macos/PHA-Serve.command` (foreground)  
> **Build**: `pha-v2.3.29.1-wearable-chat-steps-fix`  
> **Deliberately not restored**: `pha_daemon.sh` / LaunchAgent (see §3)

---

## 1. Symptom timeline

| Stage | Symptom | Root cause |
|------|------|------|
| v2.3.29 @ 8788 | Page opens; wearable chat HTTP 0 | `chat_service.py` duplicate import → `UnboundLocalError` (unrelated to the process model) |
| v2.3.31 experiment | After the chat fix, “page won’t open after restart” | `pha_daemon.sh` watchdog raced with bare `pha.main` / old Restart.app for **port 8787** |
| v2.3.31 experiment | Service exits a few seconds after start | watchdog child `exec` replaced the shell; multi-instance kill loop; logs in `/tmp/pha-8787.log` show repeated `watchdog started` |
| LaunchAgent | `Operation not permitted` | macOS restricts KeepAlive under `~/Documents` |
| nohup background | Sometimes “acceptance passed but later unavailable” | No watchdog; process is not auto-restarted after OOM/crash (by design) |

---

## 2. Current stable model (v2.3.29.1)

```text
pha_restart_accept.sh
  → read .env (PHA_PORT, default 8787; this project commonly uses 8788)
  → lsof kill :PORT + clean leftover watchdog.pid
  → nohup python -m pha.main
  → after 1s, kill -0 to catch “instant exit”
  → curl /health accept + kill -0 again after accept

PHA-Serve.command (recommended for long-running)
  → foreground exec pha.main | tee log
  → most stable while Terminal stays open
```

**Do not** run at the same time: daemon watchdog + `pha_restart_accept` + multiple Terminal `pha.main` processes.

---

## 3. Why not reintroduce pha_daemon.sh

1. **Port conflict**: Restart.app only killed 8787; daemon watchdoged 8787; `.env PHA_PORT=8788` forked the story.
2. **Double instance**: watchdog restart and manual `nohup` can coexist; lsof-killing the port only kills the listener, then watchdog immediately starts another.
3. **Complexity > benefit**: chat bug and steps bug are **orthogonal** to daemon; a foreground Terminal or the acceptance script is enough for local development.

---

## 4. Ops checklist

```bash
# 1. Who is listening?
lsof -nP -iTCP:8788 -sTCP:LISTEN

# 2. Healthy?
curl -sf http://127.0.0.1:8788/health

# 3. Crash in logs?
tail -50 /tmp/pha-8788.log | grep -E 'Error|Traceback|UnboundLocal'

# 4. Acceptance restart
cd personal_health_agent && bash scripts/pha_restart_accept.sh
```

---

## 5. Code fixes in this batch (unrelated to startup, same delivery)

| Item | File | Notes |
|------|------|------|
| Wearable chat crash | `chat_service.py` | Remove duplicate import inside the function |
| Steps inflation (new import) | `data_importer.py` | Sum by source then take **max**, not add across sources |
| Same-day merge | `store.py` | Steps merge changed to max |
| Snapshot warning | `data_integrity.py` | >20k steps + abnormal steps/activity-energy ratio → Tier0 warning |
| Restart.app | retired | Unify on the script entry to avoid launcher fork |
| Acceptance script | `pha_restart_accept.sh` | Clean leftover watchdog; pid-alive check after accept |

**Existing SQLite steps are still inflated**: re-upload `export.zip` (default `clear_before_import=True` clears then re-imports).

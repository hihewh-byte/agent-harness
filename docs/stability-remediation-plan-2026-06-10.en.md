# PHA stability emergency remediation plan (v2026-06-10)

> **Language / 语言**：English (this document) · [中文](stability-remediation-plan-2026-06-10.md)

> Status: P0-0～**P0-5 implemented** (2026-06-10); P1 onward pending (this document is the sole execution source of truth)
> Overall goal: this week, solve the two P0 problems “import hangs” + “service will not stay up”.
> Execution principles: hold the M4 Air floor (import RSS peak < 1GB, no extra resident process); do not break the A+ constitution (Harness / TurnEvidencePlan / C-layer audit zero change).
> Related docs: `startup-availability-remediation-plan-2026-06-08.md` (PR-A/B/C frame), `startup-stability-2026-06-07.md`, `startup-change-log.md`
> Mandatory: every coding agent that touches PHA, before changing startup / import / process-lifecycle code, **must** fully read this document and obey §6 behavior red lines. Gate: `.cursor/rules/startup-consensus.mdc`.

---

## 0. Background: 2026-06-10 audit conclusions (evidence summary)

1. **Import hang**: full import of `export 3.zip` ran 17 hours unfinished. Runtime stack sampling (macOS `sample`, pid 82831) showed 100% of time in `gc_collect` (mainly `set_traverse` / `element_gc_traverse`). Root cause: `data_importer._seen_samples` in-memory dedupe set grew without bound (2.83M+ strings) × `WearableDataBatchWriter` calling `gc.collect()` on every commit → GC thrash, throughput → 0. That process was manually killed on 06-10.
2. **Service will not stay up**: structural, not frequent crashes. ① The whole repo has no launchd plist, `launchctl` has no entries, so after reboot/logout/stop there is no self-heal; ② keepalive itself is an unsupervised single point; ③ **suicidal restart**: `pha_restart_accept.sh:34` always calls `pha_stop.sh` first to kill the whole chain then starts; if start fails, the service sits in a dead zone of “already killed, never brought up” (see §1).
3. **Exclusions**: no cron / launchd / external script auto-killing PHA processes; no evidence of SQLite locked or OOM. The only kill-process code in-repo is `pha_stop.sh`.

---

## 1. P0-0 “suicidal restart” detailed solution (highest priority)

### 1.1 Problem definition

Current `pha_restart_accept.sh` order:

```
L34: bash pha_stop.sh        ← kill keepalive → kill app → lsof -ti :PORT | xargs kill -9
L36+: start new keepalive/app → wait /health → accept
```

Three defects:

- **D1 dead zone**: stop runs before any preflight. If the subsequent start fails (missing venv, module import error, disk full, port occupied abnormally), the script `set -euo pipefail` `exit 1`s immediately — old instance dead, new instance never up, keepalive also killed — service enters an unrecoverable down state. Historical circular-import start failures hit this window.
- **D2 indiscriminate port kill**: `lsof -ti :${PORT} | xargs kill -9` does not check process identity; any process occupying 8788 (including non-PHA processes, or a new instance just spawned by a concurrent restart) gets SIGKILL.
- **D3 no concurrency mutex**: two restarts at once kill each other’s newly spawned processes — “restart always fails”.

### 1.2 Target semantics

> **Restart must be “prove the new instance can start, then replace the old instance”; if that cannot be done, it must “fail and automatically restore the old keepalive chain”. No path may produce an unrecoverable dead zone.**

### 1.3 Two-phase plan

**Phase B (transition, do immediately, no launchd dependency) — reorder `pha_restart_accept.sh`:**

1. **Preflight first (finish all checks before killing processes)**:
   - venv python exists and is executable;
   - Dry-run import check: `$PY -c "import pha.main"` (catch circular import / syntax errors — historically the most frequent start failure);
   - `build_marker` readable;
   - Port occupant identity: PID from `lsof -i :PORT` checked via `ps -o command` that the command line contains `pha.main` / `pha_keepalive`; otherwise **error-exit and do not kill** (eliminate D2);
   - Any preflight failure → abort immediately, old instance and keepalive left intact, clearly print “old service unaffected”.
2. **Minimize kill scope**: only kill processes recorded in pidfile / watchdog pidfile whose command line matches PHA; port fallback cleanup also identity-checks first.
3. **Fail-restore path**: `trap` ERR/EXIT — if stop already ran but the new instance never reached ready, automatically re-spawn keepalive with the same spawn command as the happy path (keepalive then brings up app), and use a distinct exit code (e.g. 70) to mean “restart failed but keepalive restored”; if restore also fails, print a loud “service is currently stopped” + human instructions.
4. **Concurrency mutex**: wrap the whole restart in a lock (`/tmp/pha-${PORT}.restart.lock`; on macOS without flock use atomic `mkdir` lock + stale-lock timeout reclaim), eliminate D3.
5. Tighten `pha_stop.sh` in sync: reuse the same “identity-check then kill” logic; keep it as the only manual stop entry.

**Phase A (end state, merge with P0-4 launchd task):**

- After launchd owns the lifecycle: restart = `launchctl kickstart -k` (launchd atomically replaces the process, crash auto-restarts, no dead zone); stop = `launchctl bootout` (otherwise KeepAlive immediately brings a killed process back and stop appears to fail).
- `pha_restart_accept.sh` degrades to a “kickstart + wait /health + accept” wrapper and **contains no kill logic at all**; Phase B preflight and mutex stay.

### 1.4 Effort / risk / acceptance

- **Estimated time**: Phase B 0.5 day (script reorder + fault-injection drill); Phase A folds into P0-4.
- **Risks**: trap-restore logic complexity (cover with fault-injection drills); stale lock file causing restart reject (add timeout reclaim).
- **Acceptance (fault-injection drills, all must pass)**:
  1. Temporarily make `import pha.main` fail → restart aborts in preflight, old service `/health` stays 200, zero interruption;
  2. Preflight passes but new instance health times out → trap restore fires, `/health` back to 200 within 60s, exit code = 70;
  3. Occupy the port with `nc -l 8788` (non-PHA) → restart refuses to kill and error-exits, nc process still alive;
  4. Two terminals concurrent restart → one runs, one is lock-rejected, final service healthy;
  5. 10 consecutive happy-path restarts: service interrupt window < 5s (Phase B) / < 2s (Phase A), no leftover processes or ports.
- **Depends / preconditions**: none. Do this before any other startup-class change; Phase A depends on P0-4.
- **PR mapping**: prerequisite patch for PR-B (unified keepalive model).

---

## 2. P0 task list (must finish this week)

| ID | Task | Effort | Depends |
|---|---|---|---|
| P0-0 | Suicidal-restart fix (§1, Phase B) | 0.5 day | none, do first |
| P0-1 | Import pipeline GC/memory fix | 0.5–1 day | none |
| P0-2 | Import tail rebuild-chain restructure | 1 day | same batch as P0-1 |
| P0-3 | Full re-import + service restore | 0.5 day | P0-1, P0-2 |
| P0-4 | launchd keepalive landing (incl. P0-0 Phase A) | 1–1.5 day | can parallel P0-1 |
| P0-5 | Unify ops entries | 0.5 day | P0-4 |

### P0-1 Import pipeline GC/memory fix

- **Main change points**: delete `_seen_samples` in-memory dedupe (dedupe via `INSERT OR IGNORE` + `UNIQUE(user_id, sample_id)`); remove periodic `gc.collect()` from `WearableDataBatchWriter` and workout streams; skip non-allowlist Records before attrib fetch; drop `_count_records_in_zip` pre-scan pass (progress estimated from zip bytes already read).
- **Risks**: `sample_id` generation must be consistent across paths (premise of unique-index fallback); progress-percentage precision drops (acceptable).
- **Acceptance**: `export 3.zip` full import on M4 Air ≤ 30 minutes; `wearable_data` row count aligned to 2.83M baseline; row count monotonically increases every 30s during import; process RSS peak < 1GB.
- **Depends**: none.

### P0-2 Import tail rebuild-chain restructure

- **Main change points**: `rebuild_daily_sleep_from_segments` becomes single-connection batch (no per-day connections); `compute_sleep_hours_union` becomes sweep-line O(n log n); remove/rewrite `sync_index_from_daily` full-table DELETE+reinsert (`substr(timestamp,1,10)` misses the index and destroys fine-grained HR samples).
- **Risks**: daily-aggregate numeric regression (sleep duration, HRV daily mean).
- **Acceptance**: full rebuild < 60s; sample 30 days daily vs old algorithm value-by-value identical; HRV 90d baseline mean stays ~32.9 ms.
- **Depends**: same file family as P0-1; merge in order, one regression.

### P0-3 Full re-import + service restore

- **Main change points**: no new code; run the fixed `scripts/pha_full_import_from_zip.py`, then start via the fixed restart.
- **Risks**: service downtime during import (one-shot window).
- **Acceptance**: `wearable_daily` rows > 0 and `MAX(day)` ≥ 2026-06-09; `/health` 200; chat queries for HRV/steps return new data; 7-image real-device HRV retest = 27 ms.
- **Depends**: P0-1, P0-2.

### P0-4 launchd keepalive landing (existing PR-B plan)

- **Main change points**: install plist to `~/Library/LaunchAgents/`, `KeepAlive=true` + `ThrottleInterval` directly supervise uvicorn; logs move to `~/Library/Logs/pha/`; `pha_keepalive.py` retire or degrade to `/health` deep-probe reporting; P0-0 Phase A switch.
- **Risks**: **already failed once historically** — launchd executing scripts under `~/Documents` reported `Operation not permitted` (macOS TCC). Fallback: move wrapper and run entry to `~/Library/Application Support/pha/`; worst-case floor keep Phase B keepalive. **Day 1: 10-minute TCC feasibility check before investing.**
- **Acceptance**: after reboot, `/health` 200 within 60s; after `kill -9` app, auto-bring-up within 10s; logout/login auto-restore; `pha_stop.sh` (bootout version) stays down after stop.
- **Depends**: none, can parallel P0-1.

### P0-5 Unify ops entries

- **Main change points**: `pha_restart_accept.sh` becomes `launchctl kickstart` wrapper; `pha_stop.sh` becomes `launchctl bootout/disable`; delete the dual-track “foreground Terminal is most stable” wording in docs; `.env.example` port aligned to 8788.
- **Risks**: stop/restart semantics change; must sync this file, `.cursor/rules/startup-consensus.mdc`, and `startup-change-log.md`.
- **Acceptance**: restart full interrupt < 5s; after stop, truly not brought back; 10 consecutive restarts with no leftover process/port.
- **Depends**: P0-4.

---

## 3. P1 tasks (finish this week if possible)

| ID | Task | Effort | Points |
|---|---|---|---|
| P1-1 | Split `chat_service.py` (2589 lines; `stream_pha_chat_events` ~1354) | 1–1.5 day | Split by attachment OCR / vision / harness wiring / SSE orchestration, zero behavior change; accept = all selfcheck + golden byte-compare + wearable chat curl byte-identical; depends all P0 done |
| P1-2 | Unify daily-aggregate logic in three places (`_build_summaries` / `rebuild_wearable_daily_for_days` / `rebuild_daily_sleep_from_segments`) | 0.5–1 day | Reuse P0-2 compare infra; accept = three callers’ output matches current |
| P1-3 | SQLite connection-management closeout | 0.5 day | thread-local connections / shared factory; BatchWriter no longer runs `init_schema` migrate every time; accept = import + concurrent chat stress with no `database is locked` |
| P1-4 | Unify selfcheck entry | 0.5–1 day | 50+ `pha_stage*_selfcheck.py` registered into pytest / `run_selfchecks.sh` single entry; accept = one command runs full selfcheck with summary |

## 4. P2 tasks (opportunistic, not on the critical path)

- P2-1 Delete 410 dead lines (`main.py:267-344` already-offline delta/workout background functions) — 1 hour.
- P2-2 Version and config alignment (README version → actual build_marker; `.env.example` 8787 → 8788) — 0.5 hour.
- P2-3 Move runtime state out of `/tmp` (pid/logs → `~/Library/Logs/pha`) — fold into P0-4.
- P2-4 Converge broad `except Exception` + structured logs — ongoing; no acceptance this week.

---

## 5. Overall timeline and risk overview

- **Day 1**: P0-0 Phase B (first) → P0-1 + P0-2 coding and golden compare; in parallel, P0-4’s 10-minute TCC feasibility check.
- **Day 2**: P0-3 re-import `export 3.zip` + service-restore accept; P0-4 body.
- **Day 3**: P0-4 wrap (reboot / logout / kill -9 three-scene accept) + P0-5 entry unify (incl. P0-0 Phase A).
- **Day 4**: start 24h probe regression watch; P1-3 connection closeout + P2-1/2/3.
- **Day 5**: P1-1 chat_service split (phase 1) + P1-4 selfcheck closeout.

| Risk | Level | Mitigation |
|---|---|---|
| launchd × `~/Documents` TCC (already hit historically) | High | Move run entry out of Documents; floor Phase B keepalive; Day 1 falsify first |
| Rebuild restructure causes daily-aggregate numeric regression | Medium | golden compare 30 days; keep old impl behind env flag for a week |
| After deleting in-memory dedupe, inconsistent `sample_id` causes duplicate rows | Medium | post-import row count + unique-index conflict count dual check |
| Restart trap-restore logic defect | Medium | §1.4 five fault-injection drills all pass before done |
| stop/restart semantic change mis-ops | Low | Sync consensus docs; scripts print new-semantics hints |
| M4 Air resource floor | Low | P0-1 accept includes RSS < 1GB; launchd adds no extra resident process |

---

## 6. Cross-agent behavior red lines (mandatory; violate = revert)

The following rules apply to **all** coding agents on the PHA project (any model, any session):

1. **Process-lifecycle red lines**
   - R1 Forbidden to add any “kill processes first, then check” logic; every kill must be preceded by startability preflight (venv, `import pha.main` dry-run, port identity).
   - R2 Forbidden indiscriminate kill: before killing any process, dual-check pidfile + command-line identity that it belongs to PHA; forbidden bare `lsof -ti :PORT | xargs kill -9`.
   - R3 Forbidden to add a third start/stop entry besides `pha_restart_accept.sh` / `pha_stop.sh` (scripts, .command, .app, Makefile targets all count).
   - R4 After P0-4 lands: restart must go through `launchctl kickstart`, stop must go through `launchctl bootout`; forbidden to directly `kill` launchd-managed processes (they come back immediately, manufacturing a fake fault).
   - R5 Any restart/stop change must run §1.4’s five fault-injection drills and paste results in the PR/summary; missing any = no merge.
2. **Import-pipeline red lines**
   - R6 Forbidden to introduce an in-process full dedupe collection (set/dict accumulating per row) on the import hot path; dedupe always depends on DB unique index + `INSERT OR IGNORE`.
   - R7 Forbidden to call `gc.collect()` on loop/batch-write paths.
   - R8 Forbidden to restore incremental-sync product entries (`ingest_modules`, `/data/sync-module/*`, Dashboard dropdown) unless the user explicitly asks; full `/data/upload` and `pha_full_import_from_zip.py` are the only import paths.
   - R9 Import-class change accept must include: monotonic row-count probe (every 30s), RSS peak < 1GB, `export 3.zip` ≤ 30 minutes.
3. **General red lines**
   - R10 Do not break the A+ constitution: Harness / TurnEvidencePlan / C-layer audit zero change.
   - R11 Startup/import/process-related changes must update `docs/startup-change-log.md` in the same PR, mapped to this document’s task IDs (P0-x/P1-x/P2-x).
   - R12 Before changing, must emit the ack line: `CONSENSUS_ACK: stability-plan-v2026-06-10 read`.

---

## 7. Mandatory prompt for subsequent coding agents (copy-paste)

> Paste the entire block below at the start of any agent session that works on PHA stability:

```text
You will work on the personal_health_agent (PHA) project. Before any work, you must fully read in order:

1. docs/stability-remediation-plan-2026-06-10.md   ← current execution source of truth (task list, acceptance, behavior red lines)
2. docs/startup-availability-remediation-plan-2026-06-08.md
3. docs/startup-stability-2026-06-07.md
4. docs/startup-change-log.md

After reading, your first implementation reply must contain exactly once:
CONSENSUS_ACK: stability-plan-v2026-06-10 read

Hard constraints (violate any → stop and revert):
- You may only claim task IDs in stability-remediation-plan-2026-06-10.md §2-§4 (P0-x / P1-x / P2-x), and must declare the claimed ID in the reply; do not invent out-of-plan startup/import changes.
- Strictly obey all 12 behavior red lines in that document §6 (R1-R12). Focus: preflight + identity check before kill (R1/R2); no new start entry (R3); import hot path forbids in-memory full dedupe and gc.collect() (R6/R7); do not restore incremental sync (R8).
- Done for each task = all acceptance criteria listed for that task in the plan document pass, and paste accept evidence (command output / probe data / drill results) in the summary. restart/stop-class changes must attach §1.4 five fault-injection drill results.
- When changing startup/import/process-lifecycle files, must update docs/startup-change-log.md in the same change batch, noting the corresponding task ID and rollback method.
- Hold the M4 Air resource floor (import RSS < 1GB, no extra resident process); do not touch Harness / TurnEvidencePlan / C-layer audit (A+ constitution).
- If you believe an item in the plan is wrong or infeasible, stop first, report reasons and an alternative to the user, update the plan document after confirmation, then touch code; forbidden to silently deviate from the plan.
```

---

## 8. Rollback general rules

- Each task is an independent batch (commit/PR granularity = task ID), independently rollbackable.
- P0-1/P0-2 keep the old impl behind an env flag for a week (e.g. `PHA_IMPORT_LEGACY=1`).
- P0-4 fail rollback = delete plist + restore Phase B keepalive (Phase B scripts are not deleted; they are a permanent backup).
- Rollback itself is a startup-class change and must be registered in `startup-change-log.md`.

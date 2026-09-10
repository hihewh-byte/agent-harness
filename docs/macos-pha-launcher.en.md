# macOS PHA launcher

> **Language / 语言**：English (this document) · [中文](macos-pha-launcher.md)

> 2026-06-10: official background path is **launchd LaunchAgent** (`KeepAlive`); keepalive script is fallback.

## Official path (recommended)

| Action | Command |
|--------|---------|
| **First install** (once) | `bash scripts/pha_install_launchd.sh install` |
| **Restart + accept** | `bash scripts/pha_restart_accept.sh` |
| **Stop** | `bash scripts/pha_stop.sh` |
| **Status** | `bash scripts/pha_install_launchd.sh status` |
| **Uninstall launchd** | `bash scripts/pha_install_launchd.sh uninstall` |

- Logs: `~/Library/Logs/pha/pha-${PORT}.log` (default 8788)
- Config mirror: `~/Library/Application Support/pha/env-${PORT}.sh` (copied from `.env` at install; **re-install after editing `.env`**)
- Wrapper: `~/Library/Application Support/pha/run-${PORT}.sh` (runs under Application Support to avoid Documents TCC)

## Dev / debug

| Scene | Command |
|-------|---------|
| Foreground (keep Terminal open) | double-click `scripts/macos/PHA-Serve.command` or `PHA_RUN_MODE=foreground bash scripts/pha_restart_accept.sh` |
| Force keepalive fallback | `PHA_USE_LAUNCHD=0 bash scripts/pha_restart_accept.sh` |

## Real-device / E2E rule

**Restart before every real chat, attachment upload, or harness accept**, or you may still be on an old build.

```bash
bash scripts/pha_restart_accept.sh
```

The script: preflight → `launchctl kickstart -k` (if installed) → wait `/health` → check `pha_build`.

**Do not** start a new real-device round just because “the service is already up” without a restart.

## TCC (project under Documents)

If the repo lives in `~/Documents`, launchd **must not** set `WorkingDirectory` to Documents (`Operation not permitted`). Current layout:

- Wrapper and env under `~/Library/Application Support/pha/`
- Python still loads code from the project (`PYTHONPATH=$ROOT`)

Smoke TCC before install: `bash scripts/pha_install_launchd.sh verify`

If verify fails, keepalive fallback: `PHA_USE_LAUNCHD=0 bash scripts/pha_restart_accept.sh`

## History (retired)

- `PHA-Restart.command` / `PHA-Stop.command` / `.app` launchers (removed 2026-06-09)

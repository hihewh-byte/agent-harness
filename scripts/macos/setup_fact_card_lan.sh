#!/usr/bin/env bash
# One-shot LAN setup for the iPhone fact card (Mac + iPhone same Wi-Fi).
#
# Does not pull Ollama. Daily numbers need no LLM.
# Token stays in gitignored .env + data/local_shortcuts/. Never commit those.
#
# Usage (repo root, after bootstrap.sh):
#   source .venv/bin/activate
#   bash scripts/macos/setup_fact_card_lan.sh
#   bash scripts/macos/setup_fact_card_lan.sh --no-sign   # env only
#   PHA_INGEST_URL_HOST=192.168.1.23 bash scripts/macos/setup_fact_card_lan.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

NO_SIGN=0
NO_OPEN=0
for arg in "$@"; do
  case "$arg" in
    --no-sign) NO_SIGN=1 ;;
    --no-open) NO_OPEN=1 ;;
    -h | --help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "FAIL: fact-card LAN setup needs macOS (Shortcuts signing + AirDrop)." >&2
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  if [[ -f "$ROOT/.env.example" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "==> created .env from .env.example"
  else
    echo "FAIL: missing .env and .env.example" >&2
    exit 1
  fi
fi

python3 - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
raw = path.read_text(encoding="utf-8") if path.is_file() else ""
lines = raw.splitlines()
keys = {}
order = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        order.append(("raw", line))
        continue
    k, v = stripped.split("=", 1)
    k = k.strip()
    v = v.strip().strip("'").strip('"')
    keys[k] = v
    order.append(("kv", k))

changed = []

def set_key(k: str, v: str, *, force: bool = False) -> None:
    prev = keys.get(k)
    if prev == v:
        return
    if prev and not force:
        return
    if k not in keys:
        order.append(("kv", k))
    keys[k] = v
    changed.append(k)

host = (keys.get("PHA_HOST") or "").strip() or "127.0.0.1"
if host != "0.0.0.0":
    set_key("PHA_HOST", "0.0.0.0", force=True)
    changed.append("PHA_HOST")

token = (keys.get("PHA_INGEST_TOKEN") or "").strip()
if not token:
    set_key("PHA_INGEST_TOKEN", secrets.token_urlsafe(32), force=True)

if not (keys.get("PHA_INGEST_TZ") or "").strip():
    set_key("PHA_INGEST_TZ", "Asia/Shanghai", force=True)

out = []
seen = set()
for kind, payload in order:
    if kind == "raw":
        # Drop commented placeholders we are about to write as live keys.
        s = payload.strip()
        if s.startswith("#") and "=" in s:
            ck = s.lstrip("#").strip().split("=", 1)[0].strip()
            if ck in {"PHA_INGEST_TOKEN", "PHA_INGEST_TZ"} and ck in keys:
                continue
        out.append(payload)
        continue
    if payload in seen:
        continue
    seen.add(payload)
    val = keys[payload]
    if payload == "PHA_INGEST_TOKEN":
        out.append(f"{payload}='{val}'")
    else:
        out.append(f"{payload}={val}")
for k, v in keys.items():
    if k in seen:
        continue
    if k == "PHA_INGEST_TOKEN":
        out.append(f"{k}='{v}'")
    else:
        out.append(f"{k}={v}")
text = "\n".join(out).rstrip() + "\n"
path.write_text(text, encoding="utf-8")
token_len = len(keys.get("PHA_INGEST_TOKEN") or "")
print(f"env PHA_HOST={keys.get('PHA_HOST')}")
print(f"env PHA_INGEST_TZ={keys.get('PHA_INGEST_TZ')}")
print(f"env PHA_INGEST_TOKEN set (length {token_len}; not printed)")
if changed:
    print("env updated:", ", ".join(sorted(set(changed))))
else:
    print("env already LAN-ready")
PY

lan_ip=""
for iface in en0 en1 en2; do
  lan_ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
  if [[ -n "$lan_ip" ]]; then
    break
  fi
done
local_name="$(scutil --get LocalHostName 2>/dev/null || true)"
bonjour="${local_name:+${local_name}.local}"
port="$(python3 - <<'PY'
from pathlib import Path
port = "8788"
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s.startswith("PHA_PORT="):
        port = s.split("=", 1)[1].strip().strip("'").strip('"') or "8788"
print(port)
PY
)"

echo "==> listen 0.0.0.0:${port} (phone cannot hit 127.0.0.1)"
if [[ -n "$bonjour" ]]; then
  echo "==> Bonjour  http://${bonjour}:${port}"
fi
if [[ -n "$lan_ip" ]]; then
  echo "==> LAN IP   http://${lan_ip}:${port}"
else
  echo "==> LAN IP   (none on en0/en1/en2 — check Wi-Fi)"
fi

PY="${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}"
if [[ -z "${PY}" || ! -x "${PY}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    PY="$(command -v python3 || true)"
  fi
fi
if [[ -z "${PY}" ]]; then
  echo "FAIL: need Python 3.10+ (source .venv/bin/activate after bootstrap.sh)" >&2
  exit 1
fi

if [[ "$NO_SIGN" -eq 1 ]]; then
  echo "==> skipped shortcut signing (--no-sign)"
else
  if ! command -v shortcuts >/dev/null 2>&1; then
    echo "FAIL: macOS 'shortcuts' CLI missing. Open the Shortcuts app once, then retry." >&2
    exit 1
  fi
  "$PY" scripts/macos/build_pha_ingest_shortcuts.py
  if [[ "$NO_OPEN" -eq 0 ]]; then
    open "$ROOT/data/local_shortcuts"
  fi
fi

cat <<EOF

Next (iPhone, same Wi-Fi — not cellular):

  1. Settings → Shortcuts → Advanced → Allow Untrusted Shortcuts
  2. Settings → Privacy & Security → Local Network → Shortcuts ON
  3. Preferred: download shortcuts/pha-daily.shortcut from the repo (no secrets).
     Import asks for Mac URL + PHA_INGEST_TOKEN from this .env.
     Or AirDrop the personal copy (Finder may be open):
       pha-daily.shortcut  →  PHA Daily   (contains your token; do not upload)
  4. Run PHA Daily once (Allow Access on every Find).
  5. Keep PHA listening:
       source .venv/bin/activate && python -m pha.main
     If it was already bound to 127.0.0.1:
       bash scripts/pha_restart_accept.sh

If .local times out, edit PHA Base in the Shortcut to your LAN IP, or:
  PHA_INGEST_URL_HOST=${lan_ip:-YOUR_LAN_IP} bash scripts/macos/setup_fact_card_lan.sh

Do not expose port ${port} to the public internet.
Handbook: docs/pha-fact-card-lan.md

EOF

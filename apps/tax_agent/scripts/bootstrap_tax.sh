#!/usr/bin/env bash
# Bootstrap tax-agent reference app (monorepo: apps/tax_agent or standalone clone).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO_ROOT="$ROOT"
for _ in 1 2 3 4; do
  if [[ -d "$REPO_ROOT/packages/harness_core/src" ]]; then
    break
  fi
  REPO_ROOT="$(dirname "$REPO_ROOT")"
done

PY="${TAX_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python
fi

echo "==> tax_agent bootstrap ($ROOT)"
echo "==> Python: $($PY --version)"

if [[ ! -d "$ROOT/.venv" ]]; then
  "$PY" -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$ROOT"

if [[ -d "$REPO_ROOT/packages/harness_core/src" ]]; then
  echo "==> Installing harness_core from $REPO_ROOT/packages/harness_core"
  python -m pip install -e "$REPO_ROOT/packages/harness_core"
elif [[ -d "$ROOT/../harness_core/src" ]]; then
  python -m pip install -e "$ROOT/../harness_core"
else
  echo "WARN: harness_core not found — adapter selfchecks may fail"
fi

python scripts/preflight_ci.py
python scripts/preflight_oss_publish.py
python scripts/run_tax_harness_golden_run.py
python scripts/run_production_selfchecks.py

cat <<'EOF'

✅ tax_agent verified (fixtures only, no local docs/*.xlsx required).

Run UI:
  source .venv/bin/activate
  tax-agent app          # http://127.0.0.1:8790

LLM (optional):
  ollama pull qwen2.5:7b-instruct
  export TAX_AGENT_MODEL=qwen2.5:7b-instruct

EOF

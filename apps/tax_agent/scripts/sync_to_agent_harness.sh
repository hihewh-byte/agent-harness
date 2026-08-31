#!/usr/bin/env bash
# Sync tax_agent → agent-harness monorepo (apps/tax_agent). Excludes secrets & local docs.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-}"

if [[ -z "$DEST" ]]; then
  echo "Usage: $0 /path/to/agent-harness" >&2
  exit 2
fi

if [[ ! -d "$DEST/packages/harness_core" ]]; then
  echo "ERROR: $DEST does not look like agent-harness (missing packages/harness_core)" >&2
  exit 1
fi

TARGET="$DEST/apps/tax_agent"
mkdir -p "$TARGET"

echo "==> Sync $SRC -> $TARGET"
rsync -a --delete \
  --exclude '.venv/' \
  --exclude '.data/' \
  --exclude '.env' \
  --exclude '.cursor/' \
  --exclude 'docs/*.xlsx' \
  --exclude 'docs/*.xls' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '*.egg-info/' \
  "$SRC/" "$TARGET/"

echo "==> OSS strict preflight on target"
(cd "$TARGET" && python3 scripts/preflight_oss_publish.py --strict)

echo "PASS synced to $TARGET"

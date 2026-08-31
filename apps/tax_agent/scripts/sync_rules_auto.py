#!/usr/bin/env python3
"""CLI: sync rules feed/inbox, run regression, optionally auto-publish."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.rule_auto_updater import run_auto_update_and_record


def main() -> int:
    result = run_auto_update_and_record(trigger="cli")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())

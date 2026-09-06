#!/usr/bin/env python3
"""Print the no-LLM fact card JSON for a user (default=default)."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pha.fact_card import load_fact_card  # noqa: E402
from pha.llm_provider import load_dotenv_if_present  # noqa: E402


def main() -> int:
    load_dotenv_if_present()
    uid = (sys.argv[1] if len(sys.argv) > 1 else "default").strip() or "default"
    print(json.dumps(load_fact_card(uid), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

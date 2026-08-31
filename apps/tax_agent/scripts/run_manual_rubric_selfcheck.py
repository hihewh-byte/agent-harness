#!/usr/bin/env python3
"""D3: validate manual rubric JSON schema and sample coverage."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUBRIC = ROOT / "evals" / "chat_manual_rubric.json"


def main() -> int:
    data = json.loads(RUBRIC.read_text(encoding="utf-8"))
    assert data.get("schema") == "tax.chat_manual_rubric/v1"
    dims = data.get("dimensions") or []
    assert len(dims) == 3
    samples = data.get("samples") or []
    assert len(samples) >= 10, f"expected ≥10 samples, got {len(samples)}"
    ids = {s["id"] for s in samples}
    assert len(ids) == len(samples)
    profiles = {s.get("profile") for s in samples}
    assert "policy_qa" in profiles and "policy_explain" in profiles
    print(f"PASS D3 rubric {len(samples)} samples, {len(dims)} dimensions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

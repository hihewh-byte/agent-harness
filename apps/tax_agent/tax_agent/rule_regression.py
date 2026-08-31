from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_golden_regression(*, timeout_seconds: int = 120) -> dict[str, object]:
    """Run golden selfcheck; return pass/fail report."""
    script = _repo_root() / "scripts" / "run_golden_selfcheck.py"
    report_id = str(uuid4())
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "reportId": report_id,
            "passed": False,
            "reason": "timeout",
            "stdout": "",
            "stderr": "",
        }
    passed = proc.returncode == 0
    return {
        "reportId": report_id,
        "passed": passed,
        "returnCode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-1000:],
    }

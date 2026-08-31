#!/usr/bin/env python3
"""CI / local preflight: Python version, runtime deps, generated xlsx fixtures."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)

# (import_name, pip package hint)
REQUIRED = [
    ("yaml", "PyYAML"),
    ("openpyxl", "openpyxl"),
    ("fastapi", "fastapi"),
    ("pydantic", "pydantic"),
    ("httpx", "httpx"),
    ("uvicorn", "uvicorn[standard]"),
    ("multipart", "python-multipart"),
]

FIXTURE_BUILDERS = [
    "build_ibkr_sample_xlsx.py",
    "build_unknown_generic_xlsx.py",
]


def _check_python() -> bool:
    if sys.version_info < MIN_PYTHON:
        print(
            f"FAIL: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required "
            f"(got {sys.version_info.major}.{sys.version_info.minor})"
        )
        print("  Fix: use python3.10+ or pyenv/venv with >=3.10")
        return False
    print(f"PASS python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def _check_imports() -> bool:
    ok = True
    for mod, pip_name in REQUIRED:
        try:
            importlib.import_module(mod)
            print(f"PASS import {mod}")
        except ImportError:
            print(f"FAIL missing {mod} — install: pip install {pip_name}")
            ok = False
    if not ok:
        print("\nHint: from tax_agent/ run:  pip install -e .")
    return ok


def _bootstrap_fixtures() -> bool:
    ok = True
    for name in FIXTURE_BUILDERS:
        script = ROOT / "scripts" / name
        if not script.exists():
            continue
        r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL fixture builder {name}:")
            print((r.stderr or r.stdout or "").strip())
            ok = False
        else:
            line = (r.stdout or "").strip().splitlines()[-1] if r.stdout else name
            print(f"PASS {line}")
    ibkr = ROOT / "tests" / "fixtures" / "broker" / "ibkr_mini.xlsx"
    if not ibkr.exists():
        print(f"FAIL missing required fixture {ibkr}")
        ok = False
    return ok


def main() -> int:
    print("=== tax_agent preflight ===")
    checks = [_check_python(), _check_imports(), _bootstrap_fixtures()]
    if all(checks):
        print("PASS preflight")
        return 0
    print("FAIL preflight — fix issues above before running selfchecks")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

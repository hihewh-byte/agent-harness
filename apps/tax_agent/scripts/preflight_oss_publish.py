#!/usr/bin/env python3
"""Pre-push gate: no PII paths, secrets, or forbidden account tokens in tracked tree."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"16585150", "broker account id in source"),
    (r"docs/20\d{2}_Annual_Statement", "hardcoded personal docs path"),
]

FORBIDDEN_FILENAMES = (".env", "tax_agent.db")

SCAN_SUFFIXES = {".py", ".yaml", ".yml", ".html", ".json"}

SKIP_DIRS = {".venv", ".data", "__pycache__", ".git", "node_modules"}


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if path.name == "preflight_oss_publish.py":
            continue
        out.append(path)
    return sorted(out)


def _scan_forbidden_tokens(*, strict: bool) -> list[str]:
    failures: list[str] = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"{path.relative_to(ROOT)}: {label} ({pattern})")
    if strict:
        for name in FORBIDDEN_FILENAMES:
            hits = list(ROOT.rglob(name))
            hits = [h for h in hits if not any(p in SKIP_DIRS for p in h.parts)]
            if hits:
                failures.append(f"forbidden file present: {hits[0].relative_to(ROOT)}")
        docs_xlsx = list((ROOT / "docs").glob("*.xlsx"))
        if docs_xlsx:
            failures.append(
                f"docs/*.xlsx must not ship ({len(docs_xlsx)} files) — remove before push"
            )
    return failures


def _git_tracked_docs_xlsx() -> list[str]:
    try:
        r = subprocess.run(
            ["git", "ls-files", "docs/"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.endswith((".xlsx", ".xls"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Also fail if docs/*.xlsx or .env present (use before git push)",
    )
    args = ap.parse_args()

    print("=== tax_agent OSS preflight ===")
    failures = _scan_forbidden_tokens(strict=args.strict)
    failures.extend(f"git-tracked docs spreadsheet: {p}" for p in _git_tracked_docs_xlsx())
    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("PASS no forbidden PII tokens in source tree")
    if args.strict:
        print("PASS strict publish tree (no local docs/*.xlsx)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

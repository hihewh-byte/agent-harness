#!/usr/bin/env python3
"""Self-check for API token RBAC."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from tax_agent.auth import (
    RoleLevel,
    auth_enabled,
    principal_from_headers,
    require_role,
)


def main() -> int:
    failures: list[str] = []

    # Auth disabled — anonymous user
    os.environ.pop("TAX_AGENT_AUTH_ENABLED", None)
    p = principal_from_headers()
    if p.role != "user" or p.token_id != "anonymous":
        failures.append("auth disabled should be anonymous user")

    # Auth enabled
    os.environ["TAX_AGENT_AUTH_ENABLED"] = "1"
    os.environ["TAX_AGENT_USER_TOKEN"] = "user-tok-test"
    os.environ["TAX_AGENT_EXPERT_TOKEN"] = "expert-tok-test"
    os.environ["TAX_AGENT_RULES_ADMIN_TOKEN"] = "admin-tok-test"

    if not auth_enabled():
        failures.append("auth should be enabled")

    try:
        principal_from_headers()
        failures.append("missing token should 401")
    except HTTPException as e:
        if e.status_code != 401:
            failures.append(f"expected 401 got {e.status_code}")

    user = principal_from_headers(authorization="Bearer user-tok-test")
    expert = principal_from_headers(authorization="Bearer expert-tok-test")
    admin = principal_from_headers(authorization="Bearer admin-tok-test")

    if user.role != "user" or expert.role != "tax_expert" or admin.role != "tax_rule_admin":
        failures.append("token role mapping wrong")

    try:
        require_role(user, RoleLevel.TAX_EXPERT, action="test")
        failures.append("user should not pass expert gate")
    except HTTPException as e:
        if e.status_code != 403:
            failures.append(f"user gate expected 403 got {e.status_code}")

    require_role(expert, RoleLevel.TAX_EXPERT, action="test")
    require_role(admin, RoleLevel.TAX_RULE_ADMIN, action="test")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: auth RBAC selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

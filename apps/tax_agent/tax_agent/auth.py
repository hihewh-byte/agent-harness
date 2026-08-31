"""Lightweight API token RBAC for Tax Agent v1.

Roles (ascending privilege): user < tax_expert < tax_rule_admin
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import IntEnum

from fastapi import Header, HTTPException


class RoleLevel(IntEnum):
    USER = 1
    TAX_EXPERT = 2
    TAX_RULE_ADMIN = 3


ROLE_ALIASES = {
    "user": RoleLevel.USER,
    "tax_expert": RoleLevel.TAX_EXPERT,
    "expert": RoleLevel.TAX_EXPERT,
    "tax_rule_admin": RoleLevel.TAX_RULE_ADMIN,
    "admin": RoleLevel.TAX_RULE_ADMIN,
}


@dataclass
class Principal:
    role: str
    token_id: str

    @property
    def level(self) -> RoleLevel:
        return ROLE_ALIASES.get(self.role, RoleLevel.USER)

    def has_at_least(self, required: RoleLevel) -> bool:
        return self.level >= required


def auth_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_AUTH_ENABLED") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _load_token_map() -> dict[str, str]:
    raw = (os.environ.get("TAX_AGENT_AUTH_TOKENS") or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass
    mapping: dict[str, str] = {}
    user_tok = (os.environ.get("TAX_AGENT_USER_TOKEN") or "").strip()
    expert_tok = (os.environ.get("TAX_AGENT_EXPERT_TOKEN") or "").strip()
    admin_tok = (os.environ.get("TAX_AGENT_RULES_ADMIN_TOKEN") or "").strip()
    if user_tok:
        mapping[user_tok] = "user"
    if expert_tok:
        mapping[expert_tok] = "tax_expert"
    if admin_tok:
        mapping[admin_tok] = "tax_rule_admin"
    return mapping


def _extract_token(authorization: str | None, x_tax_agent_token: str | None) -> str | None:
    if x_tax_agent_token:
        return x_tax_agent_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def principal_from_headers(
    authorization: str | None = None,
    x_tax_agent_token: str | None = None,
) -> Principal:
    if not auth_enabled():
        return Principal(role="user", token_id="anonymous")
    token = _extract_token(authorization, x_tax_agent_token)
    if not token:
        raise HTTPException(401, "authentication required")
    role = _load_token_map().get(token)
    if not role:
        raise HTTPException(403, "invalid token")
    return Principal(role=role, token_id=token[:8] + "…")


def get_principal(
    authorization: str | None = Header(None),
    x_tax_agent_token: str | None = Header(None, alias="X-Tax-Agent-Token"),
) -> Principal:
    return principal_from_headers(authorization, x_tax_agent_token)


def require_role(principal: Principal, minimum: RoleLevel, *, action: str = "") -> None:
    if not auth_enabled():
        return
    if principal.level < minimum:
        msg = f"insufficient role for {action or 'this endpoint'}: need {minimum.name}"
        raise HTTPException(403, msg)


def require_rule_admin(authorization: str | None = None) -> Principal:
    """Backward-compatible rules admin check."""
    if not auth_enabled():
        expected = (os.environ.get("TAX_AGENT_RULES_ADMIN_TOKEN") or "").strip()
        if expected and authorization != f"Bearer {expected}":
            raise HTTPException(403, "rules admin token required")
        return Principal(role="tax_rule_admin", token_id="legacy")
    principal = principal_from_headers(authorization=authorization)
    require_role(principal, RoleLevel.TAX_RULE_ADMIN, action="rules_admin")
    return principal

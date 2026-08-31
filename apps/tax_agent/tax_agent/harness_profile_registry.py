"""Tax harness profile registry — introspect plan contracts + validate vs catalog.

Local-only tooling (PHA harness_profile_registry twin). No personal data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tax_agent.harness_plan import PROFILE_SLOT_CONTRACTS, FAST_PROFILES
from tax_agent.tax_intent_catalog import load_tax_intent_catalog

REGISTRY_SCHEMA = "tax.harness_profile_registry/v1"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "rules" / "tax_harness_profile_registry.generated.json"
)

# Soft invariants: profiles that must keep these Tier0 slots when planned.
_PROFILE_SLOT_INVARIANTS: dict[str, dict[str, set[str]]] = {
    "filing_narrative": {
        "required_tier0": {"FILING_TABLE_AUTHORITY", "NUMERICS_MANIFEST", "TASK"},
        "forbidden_tools": {"LLM_COMPUTE"},
    },
    "compute": {
        "required_tier0": {"NUMERICS_MANIFEST", "TASK"},
        "forbidden_tools": {"LLM_COMPUTE"},
    },
    "coverage_check": {
        "required_tier0": {"DATA_COVERAGE", "TASK"},
        "forbidden_tools": set(),
    },
    "policy_qa": {
        "required_tier0": {"POLICY_CARDS", "TASK"},
        "forbidden_tools": {"INVENT_POLICY"},
    },
}


@dataclass
class RegistryValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, msg: str) -> None:
        self.errors.append(msg)


def introspect_profile_contracts() -> dict[str, Any]:
    """Snapshot slot/tool contracts from harness_plan templates (no LLM, no DB)."""
    profiles: dict[str, Any] = {}
    for pid, tpl in PROFILE_SLOT_CONTRACTS.items():
        profiles[pid] = {
            "slots_tier0": list(tpl.get("slots_tier0") or ()),
            "slots_tier1": list(tpl.get("slots_tier1") or ()),
            "forbidden": list(tpl.get("forbidden") or ()),
            "tools_allowed": list(tpl.get("tools_allowed") or ()),
            "fast_lane_default": bool(tpl.get("fast_lane")),
            "in_fast_profiles_set": pid in FAST_PROFILES,
        }
    return {
        "schema": REGISTRY_SCHEMA,
        "profile_count": len(profiles),
        "profiles": profiles,
    }


def validate_harness_profile_registry() -> RegistryValidationResult:
    result = RegistryValidationResult()
    contracts = PROFILE_SLOT_CONTRACTS
    cat = load_tax_intent_catalog()
    catalog_profiles = set((cat.get("profiles") or {}).keys())

    for pid in catalog_profiles:
        if pid == "clarify":
            continue
        if pid not in contracts and pid not in ("profile_memory",):
            # Catalog may list profiles that fall through to general template
            if pid not in contracts:
                result.add(f"catalog_profile_missing_slot_contract:{pid}")

    for pid, inv in _PROFILE_SLOT_INVARIANTS.items():
        tpl = contracts.get(pid)
        if not tpl:
            result.add(f"invariant_profile_missing_template:{pid}")
            continue
        have = set(tpl.get("slots_tier0") or ())
        need = inv.get("required_tier0") or set()
        missing = need - have
        if missing:
            result.add(f"invariant_missing_tier0:{pid}:{sorted(missing)}")
        forbidden_need = inv.get("forbidden_tools") or set()
        have_forb = set(tpl.get("forbidden") or ())
        forb_miss = forbidden_need - have_forb
        if forb_miss:
            result.add(f"invariant_missing_forbidden:{pid}:{sorted(forb_miss)}")

    if "filing_narrative" not in contracts:
        result.add("core_profile_missing:filing_narrative")
    if "compute" not in contracts:
        result.add("core_profile_missing:compute")

    return result


def generate_profile_registry_manifest(path: Path | None = None) -> Path:
    out = path or DEFAULT_MANIFEST_PATH
    payload = introspect_profile_contracts()
    validation = validate_harness_profile_registry()
    payload["validation_ok"] = validation.ok
    payload["validation_errors"] = list(validation.errors)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


__all__ = [
    "REGISTRY_SCHEMA",
    "RegistryValidationResult",
    "generate_profile_registry_manifest",
    "introspect_profile_contracts",
    "validate_harness_profile_registry",
]

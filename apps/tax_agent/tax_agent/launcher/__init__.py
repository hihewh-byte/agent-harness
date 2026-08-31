"""Stable launcher shell — decoupled from compute/parser internals.

Uses HTTP API contract (/api/v1/*) and process management only.
"""

from tax_agent.launcher.manifest import LAUNCHER_MANIFEST

__all__ = ["LAUNCHER_MANIFEST"]

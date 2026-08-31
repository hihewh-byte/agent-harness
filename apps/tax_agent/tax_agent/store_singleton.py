from __future__ import annotations

import os

from tax_agent.store_base import InMemoryDatasetStore

_store = None


def get_app_store():
    global _store
    if _store is not None:
        return _store
    if os.environ.get("TAX_AGENT_MEMORY", "").lower() in ("1", "true", "yes"):
        _store = InMemoryDatasetStore()
    else:
        from tax_agent.storage.sqlite_store import SqliteDatasetStore

        _store = SqliteDatasetStore()
    return _store

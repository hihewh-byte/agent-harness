"""Backward-compatible re-exports."""

from tax_agent.store_base import InMemoryDatasetStore, StoredDataset, StoredReport
from tax_agent.store_singleton import get_app_store

DatasetStore = InMemoryDatasetStore

__all__ = ["DatasetStore", "StoredDataset", "StoredReport", "get_app_store"]


def __getattr__(name: str):
    if name == "store":
        return get_app_store()
    raise AttributeError(name)

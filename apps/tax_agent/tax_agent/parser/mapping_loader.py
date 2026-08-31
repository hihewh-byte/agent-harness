from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def mappings_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "mappings"


def load_mapping(template_id: str) -> dict[str, Any]:
    path = mappings_dir() / f"{template_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"mapping not found: {template_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_template_ids() -> list[str]:
    return sorted(p.stem for p in mappings_dir().glob("broker_*.yaml"))

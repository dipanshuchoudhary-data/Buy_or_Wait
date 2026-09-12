from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.infrastructure.config import get_settings


def cache_path(namespace: str, key: str) -> Path:
    directory = get_settings().cache_dir / namespace
    directory.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)
    return directory / f"{safe}.json"


def read_cache(namespace: str, key: str) -> dict[str, Any] | None:
    path = cache_path(namespace, key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(namespace: str, key: str, payload: dict[str, Any]) -> None:
    path = cache_path(namespace, key)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

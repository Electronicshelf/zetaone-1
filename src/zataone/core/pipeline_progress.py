# zataone in-process pipeline progress (for poll UX; single-instance friendly)

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_by_asset: dict[str, dict[str, Any]] = {}


def clear(asset_id: str | None) -> None:
    if not asset_id:
        return
    with _lock:
        _by_asset.pop(str(asset_id), None)


def update(asset_id: str | None, **fields: Any) -> None:
    if not asset_id:
        return
    key = str(asset_id)
    with _lock:
        cur = dict(_by_asset.get(key) or {})
        cur.update(fields)
        _by_asset[key] = cur


def get(asset_id: str | None) -> dict[str, Any] | None:
    if not asset_id:
        return None
    with _lock:
        snap = _by_asset.get(str(asset_id))
        return dict(snap) if snap else None

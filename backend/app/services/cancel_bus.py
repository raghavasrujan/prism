"""In-process cancellation registry.

Maps ``request_id`` → asyncio.Event. Setting the event tells any streaming
route to finalise with ``finish_reason=cancelled``.

For multi-host deployments swap this module with a Redis pub/sub-backed
implementation; the public surface is only ``register()`` and ``signal()``.
"""

from __future__ import annotations

import asyncio
from typing import Optional

_events: dict[str, asyncio.Event] = {}


def register(request_id: str) -> asyncio.Event:
    """Create a fresh cancel event for this request. Idempotent."""
    ev = _events.get(request_id)
    if ev is None:
        ev = asyncio.Event()
        _events[request_id] = ev
    return ev


def signal(request_id: str) -> bool:
    """Trigger cancellation. Returns True if a listener was registered."""
    ev = _events.get(request_id)
    if ev is None:
        return False
    ev.set()
    return True


def clear(request_id: str) -> None:
    _events.pop(request_id, None)


def is_cancelled(request_id: str) -> bool:
    ev = _events.get(request_id)
    return bool(ev and ev.is_set())


def get(request_id: str) -> Optional[asyncio.Event]:
    return _events.get(request_id)

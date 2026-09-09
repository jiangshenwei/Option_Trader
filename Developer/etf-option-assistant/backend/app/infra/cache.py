from __future__ import annotations

import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get_or_set(self, key: str, ttl_sec: float, factory: Callable[[], T]) -> T:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry and entry.expires_at > now:
                return entry.value
        value = factory()
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=now + ttl_sec)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


market_cache = TTLCache()

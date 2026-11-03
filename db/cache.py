"""Small bounded in-memory cache for frequently-read database records."""

import copy
import time
from collections import OrderedDict
from typing import Any, Hashable


class TTLCache:
    def __init__(self, ttl_seconds: float = 25, max_entries: int = 10_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()

    def get(self, key: Hashable) -> tuple[bool, Any]:
        entry = self._entries.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            del self._entries[key]
            return False, None
        self._entries.move_to_end(key)
        return True, copy.deepcopy(value)

    def set(self, key: Hashable, value: Any) -> None:
        self._entries[key] = (
            time.monotonic() + self.ttl_seconds,
            copy.deepcopy(value),
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, key: Hashable) -> None:
        self._entries.pop(key, None)


repository_cache = TTLCache()

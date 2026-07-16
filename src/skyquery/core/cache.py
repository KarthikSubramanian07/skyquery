"""On-disk response cache.

Repeated questions must never re-hit a free service. The cache keys on a stable
hash of ``(source, operation, sorted params)`` and stores JSON payloads on disk
with an optional TTL. Pure and filesystem-only, no network, so it is trivially
testable.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def cache_key(source: str, operation: str, params: dict[str, Any]) -> str:
    """Return a stable content hash for a request.

    Parameter order does not matter; ``None`` values are dropped so an explicit
    ``None`` and an omitted key collide, which is the intended behaviour.
    """
    clean = {k: v for k, v in params.items() if v is not None}
    payload = json.dumps(
        {"source": source, "operation": operation, "params": clean},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class DiskCache:
    """A content-addressed JSON cache under a directory.

    Args:
        root: Directory to hold cache entries.
        ttl_seconds: Default entry lifetime; ``None`` means entries never expire.
        clock: Time source in epoch seconds, injectable for tests.
    """

    root: Path
    ttl_seconds: float | None = 7 * 24 * 3600
    clock: Callable[[], float] = time.time

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Shard by the first two hex chars to keep directories small.
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        stored_at = entry.get("stored_at", 0.0)
        ttl = entry.get("ttl", self.ttl_seconds)
        if ttl is not None and self.clock() - stored_at > ttl:
            path.unlink(missing_ok=True)
            return None
        return entry.get("value")

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "stored_at": self.clock(),
            "ttl": ttl if ttl is not None else self.ttl_seconds,
            "value": value,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry, default=str), "utf-8")
        tmp.replace(path)  # atomic within the same filesystem

    def get_or_set(
        self, key: str, producer: Callable[[], Any], *, ttl: float | None = None
    ) -> tuple[Any, bool]:
        """Return ``(value, was_cached)``, computing and storing on a miss."""
        cached = self.get(key)
        if cached is not None:
            return cached, True
        value = producer()
        self.set(key, value, ttl=ttl)
        return value, False

    def clear(self) -> int:
        """Delete every cache entry. Returns the number of files removed."""
        removed = 0
        for path in self.root.rglob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

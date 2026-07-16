"""Recorded-fixture store for deterministic replay.

The replay stub is what makes SkyQuery's whole suite hermetic: green with zero
network and zero keys. Fixtures are recorded raw payloads keyed by a stable hash
of the request. A curated set ships inside the package so a fresh clone can run
the Apophis demo offline the moment it is installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skyquery.core.cache import cache_key
from skyquery.errors import ReplayError

# Fixtures curated for the shipped offline demo and the test suite.
PACKAGED_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "_fixtures"


class FixtureStore:
    """Loads and records raw source payloads for replay.

    Args:
        directories: Directories searched in order for a matching fixture. The
            first hit wins, so a caller can layer a local override in front of the
            packaged set.
        record_dir: Where :meth:`record` writes new fixtures. Recording is used
            by the fixture-capture tooling, never during a normal replay run.
    """

    def __init__(
        self,
        directories: list[Path] | None = None,
        record_dir: Path | None = None,
    ) -> None:
        self.directories = directories or [PACKAGED_FIXTURES_DIR]
        self.record_dir = record_dir

    def _filename(self, source: str, operation: str, params: dict[str, Any]) -> str:
        key = cache_key(source, operation, params)
        return f"{source}__{operation}__{key[:16]}.json"

    def load(self, source: str, operation: str, params: dict[str, Any]) -> Any:
        """Return the recorded payload for a request, or raise :class:`ReplayError`."""
        name = self._filename(source, operation, params)
        for directory in self.directories:
            path = directory / name
            if path.exists():
                return json.loads(path.read_text("utf-8"))
        raise ReplayError(
            f"no recorded fixture for {source}.{operation} "
            f"(looked for {name}). Run with --live to fetch it, or record a fixture."
        )

    def has(self, source: str, operation: str, params: dict[str, Any]) -> bool:
        name = self._filename(source, operation, params)
        return any((d / name).exists() for d in self.directories)

    def record(self, source: str, operation: str, params: dict[str, Any], payload: Any) -> Path:
        """Write a fixture for a request. Used by capture tooling only."""
        if self.record_dir is None:
            raise ReplayError("FixtureStore has no record_dir configured")
        self.record_dir.mkdir(parents=True, exist_ok=True)
        path = self.record_dir / self._filename(source, operation, params)
        path.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
        return path

"""Configuration and filesystem layout.

SkyQuery keeps everything on your machine: a config file, an on-disk cache, and
a SQLite query/citation log, all under your platform's standard data directory.
Nothing here reaches the network, and secrets never live in this file, they live
in the OS keychain (see :mod:`skyquery.auth`).
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_path, user_data_path
from pydantic import BaseModel, Field

APP_NAME = "skyquery"

# Environment variable that lets tests and power users relocate all state.
HOME_ENV = "SKYQUERY_HOME"

# Names of the optional free API keys SkyQuery understands. SIMBAD, VizieR,
# NED, and JPL Horizons need no key at all.
CREDENTIAL_KEYS: tuple[str, ...] = ("ads", "nasa")


def _base_dir() -> Path:
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override).expanduser()
    return user_data_path(APP_NAME, appauthor=False)


class Settings(BaseModel):
    """Runtime settings and resolved paths.

    Attributes:
        replay: When true, adapters serve only recorded fixtures and never touch
            the network. This is the default so a fresh clone runs green offline.
        offline: When true, any attempt to reach the network raises rather than
            silently degrading.
        cache_ttl_seconds: Default lifetime for cached responses.
        rate_max_calls / rate_period / rate_min_interval: Rate-limiter floors.
        row_limit: Default maximum rows for catalog queries.
        home: Root directory for all SkyQuery state.
    """

    replay: bool = True
    offline: bool = False
    cache_ttl_seconds: float = 7 * 24 * 3600
    rate_max_calls: int = 5
    rate_period: float = 1.0
    rate_min_interval: float = 0.2
    row_limit: int = 50
    home: Path = Field(default_factory=_base_dir)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def config_path(self) -> Path:
        return self.home / "config.toml"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def fixtures_dir(self) -> Path:
        return self.home / "fixtures"

    @property
    def downloads_dir(self) -> Path:
        return self.home / "downloads"

    @property
    def db_path(self) -> Path:
        return self.home / "skyquery.sqlite3"

    def ensure_dirs(self) -> None:
        """Create every state directory. Idempotent."""
        self.home.mkdir(parents=True, exist_ok=True)
        for path in (self.cache_dir, self.fixtures_dir, self.downloads_dir):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables, with sensible defaults."""

        def _flag(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in ("1", "true", "yes", "on")

        return cls(
            replay=_flag("SKYQUERY_REPLAY", default=True),
            offline=_flag("SKYQUERY_OFFLINE", default=False),
        )


def default_cache_dir() -> Path:
    """The platform cache directory, used when no home override is set."""
    return user_cache_path(APP_NAME, appauthor=False)

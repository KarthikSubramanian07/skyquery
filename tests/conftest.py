"""Shared pytest fixtures.

The whole suite runs in replay mode: zero network, zero keys. Every adapter
resolves against the shipped fixtures, so cloning the repo and running `pytest`
is enough to verify SkyQuery's behaviour before trusting it with anything.
"""

from __future__ import annotations

import pytest

from skyquery.client import SkyQuery
from skyquery.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Replay-mode settings rooted at a throwaway directory."""
    return Settings(replay=True, offline=True, home=tmp_path)


@pytest.fixture
def app(settings: Settings) -> SkyQuery:
    """A SkyQuery client wired to the shipped fixtures, fully offline."""
    return SkyQuery(settings)

"""The SkyQuery client: the single object both the CLI and MCP server drive.

It owns the shared :class:`SourceContext` (cache, rate-limiter, fixtures, clock),
constructs every adapter, and exposes the high-level operations. Sessions
accumulate provenance so a citations block can be assembled at the end.
"""

from __future__ import annotations

from skyquery.config import Settings
from skyquery.core.cache import DiskCache
from skyquery.core.citations import assemble_citations, render_citations_block
from skyquery.core.ratelimit import BackoffPolicy, RateLimiter
from skyquery.models.provenance import Citation, Provenance
from skyquery.sources.base import SourceContext
from skyquery.sources.fixtures import FixtureStore
from skyquery.store.db import QueryStore


class SkyQuery:
    """High-level entry point holding shared state and every adapter."""

    def __init__(
        self, settings: Settings | None = None, *, store: QueryStore | None = None
    ) -> None:
        self.settings = settings or Settings.from_env()
        cache: DiskCache | None = None
        if not self.settings.replay:
            self.settings.ensure_dirs()
            cache = DiskCache(self.settings.cache_dir, ttl_seconds=self.settings.cache_ttl_seconds)
        self.ctx = SourceContext(
            replay=self.settings.replay,
            offline=self.settings.offline,
            cache=cache,
            limiter=RateLimiter(
                max_calls=self.settings.rate_max_calls,
                period=self.settings.rate_period,
                min_interval=self.settings.rate_min_interval,
            ),
            backoff=BackoffPolicy(),
            fixtures=FixtureStore(),
        )
        self.store = store
        self._session_provenance: list[Provenance] = []

        # Import here to avoid a heavy import graph at module load.
        from skyquery.sources import (
            AdsSource,
            ArxivSource,
            GaiaSource,
            HorizonsSource,
            MastSource,
            NasaSource,
            NedSource,
            SbdbSource,
            SimbadSource,
            VizierSource,
            VoTapSource,
        )

        self.simbad = SimbadSource(self.ctx)
        self.ned = NedSource(self.ctx)
        self.vizier = VizierSource(self.ctx)
        self.gaia = GaiaSource(self.ctx)
        self.horizons = HorizonsSource(self.ctx)
        self.sbdb = SbdbSource(self.ctx)
        self.ads = AdsSource(self.ctx)
        self.arxiv = ArxivSource(self.ctx)
        self.mast = MastSource(self.ctx)
        self.nasa = NasaSource(self.ctx)
        self.vo = VoTapSource(self.ctx)

    def track(self, provenance: Provenance) -> None:
        """Record a provenance record into the session and the query log."""
        self._session_provenance.append(provenance)
        if self.store is not None:
            self.store.record(provenance, provenance.source)

    def citations(self) -> list[Citation]:
        """Assemble the deduplicated citation list for this session."""
        return assemble_citations(self._session_provenance)

    def citations_block(self) -> str:
        """Render this session's citations as a ready-to-paste text block."""
        return render_citations_block(self.citations())

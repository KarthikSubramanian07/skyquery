"""The DataSource adapter interface.

Every external astronomy service is wrapped by exactly one adapter that
implements this interface. The base class owns the parts that must behave
identically for every source: the replay/offline routing, the cache, the
rate-limiter with backoff, and provenance stamping. Subclasses implement only
the two things that differ per service: how to fetch a raw payload live, and how
to normalize a raw payload into SkyQuery's schema.

The seam is deliberately around the *service*, not around any model. If a
service changes its API, exactly one adapter's ``_live_fetch`` changes and
nothing else in the codebase moves.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from skyquery.core.cache import DiskCache, cache_key
from skyquery.core.citations import acknowledgment_for
from skyquery.core.ratelimit import BackoffPolicy, RateLimiter, retry_with_backoff
from skyquery.errors import ReplayError, SourceError, TransientSourceError
from skyquery.logging import event, get_logger
from skyquery.models.provenance import Provenance
from skyquery.sources.fixtures import FixtureStore

_log = get_logger("sources")


@dataclass
class SourceContext:
    """Shared services handed to every adapter.

    Bundling these means adapters never construct their own cache, limiter, or
    fixture store, so the whole system shares one consistent policy.
    """

    replay: bool = True
    offline: bool = False
    cache: DiskCache | None = None
    limiter: RateLimiter = field(default_factory=RateLimiter)
    backoff: BackoffPolicy = field(default_factory=BackoffPolicy)
    fixtures: FixtureStore = field(default_factory=FixtureStore)
    now: Any = None  # optional injected clock returning an ISO string, for tests

    def timestamp(self) -> str:
        if self.now is not None:
            return str(self.now())
        return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class DataSource(ABC):
    """Base class for every SkyQuery data-source adapter."""

    source_id: ClassVar[str]
    service_name: ClassVar[str]
    homepage: ClassVar[str | None] = None
    requires_key: ClassVar[str | None] = None  # credential name, or None if free

    def __init__(self, ctx: SourceContext) -> None:
        self.ctx = ctx

    # -- the one method every adapter must implement to reach the live service --
    @abstractmethod
    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        """Perform the real network call and return a JSON-serializable payload."""

    # -- routing shared by every adapter -------------------------------------
    def fetch(self, operation: str, params: dict[str, Any]) -> tuple[Any, bool]:
        """Return ``(raw_payload, cached)`` for a request, honouring the mode.

        Order of resolution: cache, then replay fixture (in replay mode), then a
        rate-limited, backed-off live call (in live mode). Offline mode forbids
        the live call entirely.
        """
        key = cache_key(self.source_id, operation, params)

        if self.ctx.cache is not None:
            hit = self.ctx.cache.get(key)
            if hit is not None:
                event(_log, 20, "cache hit", source=self.source_id, operation=operation)
                return hit, True

        if self.ctx.replay:
            payload = self.ctx.fixtures.load(self.source_id, operation, params)
            event(_log, 20, "replay", source=self.source_id, operation=operation)
            return payload, False

        if self.ctx.offline:
            raise ReplayError(f"offline mode: no cache or fixture for {self.source_id}.{operation}")

        payload = self._fetch_live_guarded(operation, params)
        if self.ctx.cache is not None:
            self.ctx.cache.set(key, payload)
        return payload, False

    def _fetch_live_guarded(self, operation: str, params: dict[str, Any]) -> Any:
        """Live fetch wrapped in the rate-limiter and retry/backoff policy."""

        def call() -> Any:
            self.ctx.limiter.acquire()
            event(_log, 20, "live fetch", source=self.source_id, operation=operation)
            try:
                return self._live_fetch(operation, params)
            except TransientSourceError:
                raise
            except SourceError:
                raise
            except Exception as exc:
                # Do not chain the original exception: httpx embeds full request
                # URLs (including api_key query params) in HTTPStatusError, and
                # ADS puts Bearer tokens on the request object. Scrub to type only.
                raise TransientSourceError(
                    f"{self.source_id}.{operation} failed: {type(exc).__name__}"
                ) from None

        return retry_with_backoff(
            call,
            policy=self.ctx.backoff,
            retryable=lambda e: isinstance(e, TransientSourceError),
        )

    # -- provenance shared by every adapter ----------------------------------
    def provenance(
        self,
        operation: str,
        query: str,
        *,
        cached: bool,
        url: str | None = None,
    ) -> Provenance:
        """Build a provenance record for a returned value."""
        ack = acknowledgment_for(self.source_id)
        citation = ack[1] if ack else None
        return Provenance(
            source=self.source_id,
            service=self.service_name,
            query=query,
            url=url or self.homepage,
            retrieved_at=None if (self.ctx.replay or cached) else self.ctx.timestamp(),
            citation=citation,
            cached=cached,
        )

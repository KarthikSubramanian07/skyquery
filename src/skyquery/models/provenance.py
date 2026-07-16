"""Provenance and citation models.

Every value SkyQuery returns can name the service that produced it, the exact
query that produced it, and the acknowledgment text that service asks users to
include. Provenance is a first-class field on every domain model, never an
afterthought. If you cannot cite it, you cannot trust it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Where a value came from and how to credit it.

    Attributes:
        source: Short SkyQuery source id, for example ``"simbad"`` or ``"horizons"``.
        service: Human-readable service name, for example ``"SIMBAD (CDS)"``.
        query: The exact query string or a compact description of the request.
        url: A resolvable URL for the service or the specific query, when known.
        retrieved_at: ISO-8601 timestamp of retrieval, or ``None`` for replayed fixtures.
        citation: The acknowledgment text the service asks users to include.
        cached: Whether this value was served from the local on-disk cache.
    """

    source: str
    service: str
    query: str
    url: str | None = None
    retrieved_at: str | None = None
    citation: str | None = None
    cached: bool = False

    model_config = {"frozen": True}


class Citation(BaseModel):
    """A single, deduplicated acknowledgment entry for a session."""

    source: str
    service: str
    text: str
    references: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

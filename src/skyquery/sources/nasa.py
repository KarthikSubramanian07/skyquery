"""NASA Open API adapter (the "wonder" layer).

APOD and other NASA open endpoints. Uses a free key when configured, otherwise
falls back to the public ``DEMO_KEY`` so casual use works with zero setup.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from skyquery.auth import get_credential
from skyquery.models.provenance import Provenance
from skyquery.sources.base import DataSource

_APOD_API = "https://api.nasa.gov/planetary/apod"


class AstronomyPicture(BaseModel):
    """A normalized Astronomy Picture of the Day record."""

    date: str
    title: str
    explanation: str
    url: str | None = None
    hdurl: str | None = None
    media_type: str = "image"
    copyright: str | None = None
    provenance: Provenance


class NasaSource(DataSource):
    source_id: ClassVar[str] = "nasa"
    service_name: ClassVar[str] = "NASA Open APIs"
    homepage: ClassVar[str | None] = "https://api.nasa.gov/"
    requires_key: ClassVar[str | None] = None  # DEMO_KEY works without one

    def apod(self, date: str | None = None) -> AstronomyPicture:
        """Return the Astronomy Picture of the Day for a date (or today)."""
        raw, cached = self.fetch("apod", {"date": date})
        prov = self.provenance(
            "apod", f"NASA.apod(date={date!r})", cached=cached, url=self.homepage
        )
        return AstronomyPicture(
            date=raw.get("date", date or ""),
            title=raw.get("title", ""),
            explanation=raw.get("explanation", ""),
            url=raw.get("url"),
            hdurl=raw.get("hdurl"),
            media_type=raw.get("media_type", "image"),
            copyright=raw.get("copyright"),
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import httpx

        if operation != "apod":
            raise ValueError(f"unsupported NASA operation {operation!r}")
        key = get_credential("nasa") or "DEMO_KEY"
        query: dict[str, Any] = {"api_key": key}
        if params.get("date"):
            query["date"] = params["date"]
        response = httpx.get(_APOD_API, params=query, timeout=30.0)
        response.raise_for_status()
        return response.json()

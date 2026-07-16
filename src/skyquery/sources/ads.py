"""NASA ADS adapter (Astrophysics Data System).

Literature search over the astronomy corpus. ADS needs a free researcher token,
read from the OS keychain at call time. The token is never logged, never cached,
and never placed in a returned payload.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.auth import require_credential
from skyquery.models.paper import Paper
from skyquery.sources.base import DataSource

_ADS_API = "https://api.adsabs.harvard.edu/v1/search/query"
_FIELDS = "bibcode,title,author,year,abstract,doi,citation_count,identifier"


class AdsSource(DataSource):
    source_id: ClassVar[str] = "ads"
    service_name: ClassVar[str] = "NASA ADS"
    homepage: ClassVar[str | None] = "https://ui.adsabs.harvard.edu/"
    requires_key: ClassVar[str | None] = "ads"

    def search(self, query: str, *, rows: int = 10) -> list[Paper]:
        """Search ADS and return normalized :class:`Paper` records."""
        raw, cached = self.fetch("search", {"q": query, "rows": rows})
        prov = self.provenance(
            "search", f"ADS.search(q={query!r}, rows={rows})", cached=cached, url=self.homepage
        )
        docs = (raw.get("response") or {}).get("docs") or []
        return [self._to_paper(doc, prov) for doc in docs]

    def _to_paper(self, doc: dict[str, Any], prov: Any) -> Paper:
        title = doc.get("title")
        title_str = title[0] if isinstance(title, list) and title else (title or "(untitled)")
        arxiv_id = None
        for ident in doc.get("identifier") or []:
            if isinstance(ident, str) and ident.lower().startswith("arxiv:"):
                arxiv_id = ident.split(":", 1)[1]
                break
        bibcode = doc.get("bibcode")
        return Paper(
            title=title_str,
            authors=list(doc.get("author") or []),
            year=int(doc["year"]) if doc.get("year") else None,
            bibcode=bibcode,
            arxiv_id=arxiv_id,
            doi=(doc.get("doi") or [None])[0]
            if isinstance(doc.get("doi"), list)
            else doc.get("doi"),
            abstract=doc.get("abstract"),
            citation_count=doc.get("citation_count"),
            url=f"https://ui.adsabs.harvard.edu/abs/{bibcode}" if bibcode else None,
            provenance=prov.model_copy(
                update={"url": f"https://ui.adsabs.harvard.edu/abs/{bibcode}"}
            )
            if bibcode
            else prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import httpx

        token = require_credential("ads")  # raises a clean CredentialError if missing
        response = httpx.get(
            _ADS_API,
            params={
                "q": params["q"],
                "rows": params["rows"],
                "fl": _FIELDS,
                "sort": "date desc",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

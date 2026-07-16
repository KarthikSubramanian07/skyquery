"""arXiv adapter (astro-ph).

Free full-text preprint search. No key required. The arXiv API returns Atom XML,
which the live path parses into the same recorded payload shape used for replay.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.models.paper import Paper
from skyquery.sources.base import DataSource

_ARXIV_API = "http://export.arxiv.org/api/query"


class ArxivSource(DataSource):
    source_id: ClassVar[str] = "arxiv"
    service_name: ClassVar[str] = "arXiv.org"
    homepage: ClassVar[str | None] = "https://arxiv.org/"
    requires_key: ClassVar[str | None] = None

    def search(self, query: str, *, max_results: int = 10) -> list[Paper]:
        """Search arXiv and return normalized :class:`Paper` records."""
        raw, cached = self.fetch("search", {"q": query, "max_results": max_results})
        prov = self.provenance(
            "search", f"arXiv.search(q={query!r})", cached=cached, url=self.homepage
        )
        return [self._to_paper(entry, prov) for entry in raw.get("entries", [])]

    def _to_paper(self, entry: dict[str, Any], prov: Any) -> Paper:
        arxiv_id = entry.get("id")
        return Paper(
            title=entry.get("title", "(untitled)"),
            authors=list(entry.get("authors") or []),
            year=entry.get("year"),
            arxiv_id=arxiv_id,
            doi=entry.get("doi"),
            abstract=entry.get("summary"),
            url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import xml.etree.ElementTree as ET

        import httpx

        response = httpx.get(
            _ARXIV_API,
            params={
                "search_query": params["q"],
                "max_results": params["max_results"],
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(response.text)
        entries: list[dict[str, Any]] = []
        for node in root.findall("a:entry", ns):
            raw_id = _text(node.find("a:id", ns))
            published = _text(node.find("a:published", ns))
            entries.append(
                {
                    "id": raw_id.rsplit("/abs/", 1)[-1] if raw_id else None,
                    "title": " ".join(_text(node.find("a:title", ns)).split()),
                    "summary": " ".join(_text(node.find("a:summary", ns)).split()),
                    "authors": [_text(a.find("a:name", ns)) for a in node.findall("a:author", ns)],
                    "year": int(published[:4]) if published else None,
                }
            )
        return {"entries": entries}


def _text(node: Any) -> str:
    return (node.text or "").strip() if node is not None else ""

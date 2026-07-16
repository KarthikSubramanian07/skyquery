"""Literature results from ADS and arXiv."""

from __future__ import annotations

from pydantic import BaseModel, Field

from skyquery.models.provenance import Provenance


class Paper(BaseModel):
    """A normalized publication record.

    Attributes:
        title: The paper title.
        authors: Author list in catalog order.
        year: Publication year, when known.
        bibcode: The ADS bibcode, the canonical citation key when available.
        arxiv_id: The arXiv identifier, for example ``"2401.01234"``.
        doi: The Digital Object Identifier, when known.
        abstract: The abstract text, when retrieved.
        citation_count: ADS citation count, when known.
        url: A resolvable URL to the record.
        provenance: Where the record came from and how to cite it.
    """

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    bibcode: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    abstract: str | None = None
    citation_count: int | None = None
    url: str | None = None
    provenance: Provenance

    @property
    def first_author(self) -> str | None:
        return self.authors[0] if self.authors else None

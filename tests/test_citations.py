"""Tests for provenance and citation assembly."""

from __future__ import annotations

from skyquery.core.citations import (
    acknowledgment_for,
    assemble_citations,
    render_citations_block,
)
from skyquery.models.provenance import Provenance


def _prov(source: str, url: str | None = None) -> Provenance:
    return Provenance(source=source, service=source.upper(), query="q", url=url)


class TestCitations:
    def test_known_source_has_acknowledgment(self) -> None:
        ack = acknowledgment_for("simbad")
        assert ack is not None
        assert "SIMBAD" in ack[0]

    def test_assemble_dedups_by_source(self) -> None:
        provs = [_prov("simbad"), _prov("simbad"), _prov("horizons")]
        cites = assemble_citations(provs)
        assert len(cites) == 2
        sources = {c.source for c in cites}
        assert sources == {"simbad", "horizons"}

    def test_references_collected_and_sorted(self) -> None:
        provs = [
            _prov("ads", "https://ui.adsabs.harvard.edu/abs/2024B"),
            _prov("ads", "https://ui.adsabs.harvard.edu/abs/2024A"),
        ]
        cites = assemble_citations(provs)
        assert cites[0].references == [
            "https://ui.adsabs.harvard.edu/abs/2024A",
            "https://ui.adsabs.harvard.edu/abs/2024B",
        ]

    def test_deterministic_order(self) -> None:
        a = assemble_citations([_prov("vizier"), _prov("gaia"), _prov("simbad")])
        b = assemble_citations([_prov("simbad"), _prov("vizier"), _prov("gaia")])
        assert [c.source for c in a] == [c.source for c in b]

    def test_render_block_includes_disclaimer(self) -> None:
        block = render_citations_block(assemble_citations([_prov("horizons")]))
        assert "not affiliated" in block.lower()
        assert "JPL Horizons" in block

    def test_empty_session(self) -> None:
        assert "No sources" in render_citations_block([])

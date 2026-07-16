"""Tests for the data-source adapters, exercised against the shipped fixtures.

These verify the normalization path: a recorded raw payload becomes a typed,
unit-tagged model. They run fully offline, which is the whole point of the replay
harness. Reference numbers are the real captured values.
"""

from __future__ import annotations

import pytest

from skyquery.client import SkyQuery
from skyquery.errors import ReplayError
from skyquery.models.object import Object


class TestSimbad:
    def test_vega_resolves_with_units(self, app: SkyQuery) -> None:
        obj: Object = app.simbad.resolve("Vega")
        assert obj.name == "* alf Lyr"
        assert obj.position is not None
        assert obj.position.frame == "icrs"
        assert obj.position.lon == pytest.approx(279.234734787, abs=1e-6)
        assert obj.parallax is not None
        assert obj.parallax.unit == "mas"
        assert obj.parallax.value == pytest.approx(130.23)
        assert obj.spectral_type == "A0V"
        assert obj.magnitude("V") is not None

    def test_provenance_attached(self, app: SkyQuery) -> None:
        obj = app.simbad.resolve("Vega")
        assert obj.provenance.source == "simbad"
        assert "SIMBAD" in obj.provenance.service
        assert obj.provenance.citation is not None

    def test_m31_masked_fields_are_none(self, app: SkyQuery) -> None:
        obj = app.simbad.resolve("M31")
        assert obj.parallax is None  # masked in the real SIMBAD row
        assert obj.redshift is not None


class TestHorizons:
    def test_apophis_ephemeris_units_and_frame(self, app: SkyQuery) -> None:
        eph = app.horizons.ephemerides(
            "99942 Apophis", location="500@399", start="2029-04-13", stop="2029-04-14", step="1h"
        )
        assert eph.rows
        row0 = eph.rows[0]
        assert row0.position.frame == "icrs"
        assert row0.delta is not None
        assert row0.delta.unit == "AU"

    def test_apophis_closest_approach_value(self, app: SkyQuery) -> None:
        eph = app.horizons.ephemerides(
            "99942 Apophis", location="500@399", start="2029-04-13", stop="2029-04-14", step="1h"
        )
        closest = min(r.delta.value for r in eph.rows if r.delta and r.delta.value)
        # Real captured minimum for the 2029-04-13 window.
        assert closest == pytest.approx(0.00025724539139, abs=1e-8)


class TestSbdb:
    def test_apophis_physical(self, app: SkyQuery) -> None:
        body = app.sbdb.small_body("Apophis")
        assert "Apophis" in body.fullname
        assert body.neo is True
        assert body.pha is True
        assert body.diameter is not None
        assert body.diameter.value == pytest.approx(0.34)
        assert body.diameter.unit == "km"
        assert body.absolute_magnitude is not None
        assert body.absolute_magnitude.value == pytest.approx(19.09)


class TestGaia:
    def test_cone_search_columns_unit_tagged(self, app: SkyQuery) -> None:
        table = app.gaia.cone_search(279.234735, 38.783689, 0.02, row_limit=20)
        assert table.catalog == "Gaia DR3"
        assert table.row_count == 5
        parallax_col = table.column("parallax")
        assert parallax_col is not None
        assert parallax_col.unit == "mas"


class TestArxiv:
    def test_search_returns_papers(self, app: SkyQuery) -> None:
        papers = app.arxiv.search("Apophis", max_results=1)
        assert papers
        assert "Apophis" in papers[0].title
        assert papers[0].provenance.source == "arxiv"


class TestNasa:
    def test_apod_normalized(self, app: SkyQuery) -> None:
        picture = app.nasa.apod()
        assert picture.title
        assert picture.provenance.source == "nasa"


class TestReplayMiss:
    def test_missing_fixture_raises_replay_error(self, app: SkyQuery) -> None:
        with pytest.raises(ReplayError):
            app.simbad.resolve("SomeObjectWithNoFixture")

"""Tests for the composed operations and the Apophis demo end to end."""

from __future__ import annotations

import pytest

from skyquery import services
from skyquery.client import SkyQuery


class TestResolve:
    def test_resolve_tracks_provenance_in_session(self, app: SkyQuery) -> None:
        services.resolve_object(app, "Vega")
        cites = app.citations()
        assert any(c.source == "simbad" for c in cites)


class TestApophisDemo:
    def test_full_report(self, app: SkyQuery) -> None:
        report = services.apophis_report(app, with_paper=True)
        assert "Apophis" in report.body.fullname
        assert report.closest_distance_au.unit == "AU"
        assert report.closest_distance_au.value == pytest.approx(0.00025724539139, abs=1e-8)
        assert report.closest_distance_lunar.value == pytest.approx(0.1001, abs=1e-3)
        assert report.latest_paper is not None
        assert "inside geostationary orbit" in report.narrative

    def test_report_assembles_citations(self, app: SkyQuery) -> None:
        services.apophis_report(app, with_paper=True)
        sources = {c.source for c in app.citations()}
        assert {"sbdb", "horizons", "arxiv"}.issubset(sources)


class TestObjectDossier:
    def test_dossier_without_papers(self, app: SkyQuery) -> None:
        dossier = services.object_dossier(app, "Vega", with_papers=False)
        assert dossier.object.name == "* alf Lyr"
        assert dossier.papers == []

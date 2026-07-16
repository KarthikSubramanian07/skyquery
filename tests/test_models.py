"""Tests for the schema primitives: coordinates and measurements."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skyquery.models.coordinates import SkyPosition
from skyquery.models.quantity import Measurement


class TestSkyPositionWrap:
    def test_ra_360_wraps_to_zero(self) -> None:
        assert SkyPosition(lon=360.0, lat=0.0).lon == 0.0

    def test_ra_just_under_360_kept(self) -> None:
        assert SkyPosition(lon=359.9999, lat=0.0).lon == pytest.approx(359.9999)

    def test_negative_ra_wraps(self) -> None:
        assert SkyPosition(lon=-10.0, lat=0.0).lon == pytest.approx(350.0)

    def test_ra_over_360_wraps(self) -> None:
        assert SkyPosition(lon=370.5, lat=0.0).lon == pytest.approx(10.5)

    def test_dec_at_poles_allowed(self) -> None:
        assert SkyPosition(lon=0.0, lat=90.0).lat == 90.0
        assert SkyPosition(lon=0.0, lat=-90.0).lat == -90.0

    def test_dec_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SkyPosition(lon=0.0, lat=91.0)
        with pytest.raises(ValidationError):
            SkyPosition(lon=0.0, lat=-90.1)

    def test_unsupported_frame_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SkyPosition(lon=0.0, lat=0.0, frame="ecliptic")  # type: ignore[arg-type]

    def test_hms_dms_formatting(self) -> None:
        pos = SkyPosition(lon=279.234734787, lat=38.783688956)
        assert pos.ra_hms.startswith("18:36:")
        assert pos.dec_dms.startswith("+38:47:")


class TestMeasurement:
    def test_rejects_unparseable_unit(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(value=1.0, unit="furlongs_per_fortnight_zzz")

    def test_dimensionless_ok(self) -> None:
        assert Measurement(value=0.5, unit="").unit == ""

    def test_negative_error_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(value=1.0, unit="mag", error=-0.1)

    def test_maybe_returns_none_for_nan(self) -> None:
        assert Measurement.maybe(float("nan"), "mag") is None

    def test_maybe_returns_none_for_missing(self) -> None:
        assert Measurement.maybe(None, "mag") is None

    def test_maybe_builds_measurement(self) -> None:
        m = Measurement.maybe("3.44", "mag")
        assert m is not None
        assert m.value == pytest.approx(3.44)

    def test_to_quantity_roundtrip(self) -> None:
        m = Measurement(value=130.23, unit="mas")
        q = m.to_quantity()
        assert str(q.unit) == "mas"
        assert float(q.value) == pytest.approx(130.23)

    def test_str_includes_unit(self) -> None:
        assert "mag" in str(Measurement(value=0.03, unit="mag"))

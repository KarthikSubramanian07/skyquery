"""Correctness tests for unit, frame, and epoch conversion.

These are the most trust-critical tests in SkyQuery. The oracle is external
ground truth: astropy's own tested transforms and reference values recorded from
a real capture (see DECISIONS.md). A confidently wrong coordinate is the one
failure an astronomer cannot forgive, so this file is deliberately picky.
"""

from __future__ import annotations

import astropy.units as u
import pytest
from astropy.coordinates import SkyCoord

from skyquery.core.convert import (
    angular_separation,
    convert_unit,
    parallax_to_distance,
    propagate_proper_motion,
    to_altaz,
    transform_frame,
)
from skyquery.models.coordinates import SkyPosition
from skyquery.models.quantity import Measurement

# Reference values recorded from a real astropy 8.0.1 run (Vega, ICRS).
VEGA_RA = 279.23473479
VEGA_DEC = 38.78368896


class TestUnitConversion:
    def test_parsec_to_lightyear(self) -> None:
        result = convert_unit(Measurement(value=1.0, unit="pc"), "lyr")
        assert result.value == pytest.approx(3.261563777167, rel=1e-9)

    def test_au_to_km(self) -> None:
        result = convert_unit(Measurement(value=1.0, unit="AU"), "km")
        assert result.value == pytest.approx(149597870.7, rel=1e-12)

    def test_velocity_roundtrip(self) -> None:
        original = Measurement(value=-13.5, unit="km / s")
        there = convert_unit(original, "m / s")
        back = convert_unit(there, "km / s")
        assert back.value == pytest.approx(-13.5, rel=1e-12)

    def test_uncertainty_is_converted(self) -> None:
        result = convert_unit(Measurement(value=1.0, unit="pc", error=0.1), "lyr")
        assert result.error == pytest.approx(0.3261563777, rel=1e-6)

    def test_incompatible_units_raise(self) -> None:
        with pytest.raises(u.UnitConversionError):
            convert_unit(Measurement(value=1.0, unit="deg"), "km")


class TestFrameTransform:
    def test_icrs_to_galactic_matches_reference(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        gal = transform_frame(pos, "galactic")
        assert gal.frame == "galactic"
        # Reference: l=67.4482081386, b=19.2372522697 (astropy 8.0.1).
        assert gal.lon == pytest.approx(67.4482081386, abs=1e-6)
        assert gal.lat == pytest.approx(19.2372522697, abs=1e-6)

    def test_icrs_to_galactic_matches_astropy_directly(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        gal = transform_frame(pos, "galactic")
        oracle = SkyCoord(VEGA_RA, VEGA_DEC, unit="deg", frame="icrs").galactic
        assert gal.lon == pytest.approx(float(oracle.l.deg), abs=1e-9)
        assert gal.lat == pytest.approx(float(oracle.b.deg), abs=1e-9)

    def test_roundtrip_icrs_galactic_icrs(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        back = transform_frame(transform_frame(pos, "galactic"), "icrs")
        assert back.lon == pytest.approx(VEGA_RA, abs=1e-9)
        assert back.lat == pytest.approx(VEGA_DEC, abs=1e-9)

    def test_fk5_j2000_close_to_icrs(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        fk5 = transform_frame(pos, "fk5")
        # ICRS and FK5 J2000 agree to well under an arcsecond.
        assert fk5.lon == pytest.approx(279.2347398591, abs=1e-6)
        assert fk5.lat == pytest.approx(38.7836948218, abs=1e-6)


class TestAltAz:
    def test_altaz_at_kitt_peak_matches_reference(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        alt, az = to_altaz(
            pos,
            latitude_deg=31.9583,
            longitude_deg=-111.5967,
            height_m=2096.0,
            time_utc="2025-07-15T05:00:00",
        )
        # Reference (no refraction): alt=70.2960804184, az=63.3358141203 deg.
        # IERS tables can shift this slightly, so allow a small tolerance.
        assert alt.value == pytest.approx(70.2960804184, abs=1e-2)
        assert az.value == pytest.approx(63.3358141203, abs=1e-2)


class TestProperMotion:
    def test_vega_propagation_j2000_to_j2025(self) -> None:
        pos = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC, frame="icrs")
        moved = propagate_proper_motion(
            pos,
            pm_ra_cosdec_mas_yr=200.94,
            pm_dec_mas_yr=286.23,
            from_epoch="J2000",
            to_epoch="J2025",
            parallax_mas=130.23,
            radial_velocity_km_s=-20.6,
        )
        # Reference: ra=279.236525068495, dec=38.785676791030 deg.
        assert moved.lon == pytest.approx(279.236525068495, abs=1e-6)
        assert moved.lat == pytest.approx(38.785676791030, abs=1e-6)


class TestParallaxDistance:
    def test_vega_distance(self) -> None:
        dist = parallax_to_distance(Measurement(value=130.23, unit="mas"))
        assert dist.unit == "pc"
        assert dist.value == pytest.approx(7.6787, rel=1e-3)

    def test_negative_parallax_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-positive"):
            parallax_to_distance(Measurement(value=-1.0, unit="mas"))


class TestAngularSeparation:
    def test_known_small_separation(self) -> None:
        a = SkyPosition(lon=VEGA_RA, lat=VEGA_DEC)
        b = SkyPosition(lon=279.235, lat=38.784)
        sep = angular_separation(a, b)
        # Reference: 1.344518172281 arcsec.
        assert sep.unit == "arcsec"
        assert sep.value == pytest.approx(1.344518172281, abs=1e-4)

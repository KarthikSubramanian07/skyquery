"""Tests for input clamps, TAP allowlisting, and ADQL hardening."""

from __future__ import annotations

import pytest

from skyquery.core.limits import (
    clamp_radius_deg,
    clamp_row_limit,
    clamp_targets,
    validate_ephemeris_window,
)
from skyquery.errors import ValidationError
from skyquery.sources.vo_policy import prepare_adql, validate_tap_url


class TestLimits:
    def test_row_limit_clamped(self) -> None:
        assert clamp_row_limit(20) == 20
        assert clamp_row_limit(10_000) == 100

    def test_row_limit_rejects_non_positive(self) -> None:
        with pytest.raises(ValidationError):
            clamp_row_limit(0)

    def test_radius_rejects_sky_wide(self) -> None:
        with pytest.raises(ValidationError):
            clamp_radius_deg(90.0)

    def test_targets_capped(self) -> None:
        with pytest.raises(ValidationError):
            clamp_targets([f"t{i}" for i in range(51)])

    def test_ephemeris_rejects_huge_window(self) -> None:
        with pytest.raises(ValidationError):
            validate_ephemeris_window("2020-01-01", "2030-01-01", "1s")

    def test_ephemeris_accepts_demo_window(self) -> None:
        validate_ephemeris_window("2029-04-13", "2029-04-14", "1h")


class TestVoPolicy:
    def test_rejects_http_and_private_hosts(self) -> None:
        with pytest.raises(ValidationError):
            validate_tap_url("http://gea.esac.esa.int/tap-server/tap")
        with pytest.raises(ValidationError):
            validate_tap_url("https://127.0.0.1/tap")
        with pytest.raises(ValidationError):
            validate_tap_url("https://evil.example/tap")

    def test_allows_known_host(self) -> None:
        url = validate_tap_url("https://gea.esac.esa.int/tap-server/tap")
        assert url.startswith("https://gea.esac.esa.int/")

    def test_adql_injects_top_case_insensitive(self) -> None:
        out = prepare_adql("select * from gaiadr3.gaia_source", row_limit=25)
        assert out.lower().startswith("select top 25 ")

    def test_adql_rejects_multi_statement(self) -> None:
        with pytest.raises(ValidationError):
            prepare_adql("SELECT 1; DROP TABLE x", row_limit=10)

"""Tests for positional cross-matching."""

from __future__ import annotations

import pytest

from skyquery.core.crossmatch import cross_match
from skyquery.models.coordinates import SkyPosition


def _pos(ra: float, dec: float) -> SkyPosition:
    return SkyPosition(lon=ra, lat=dec)


class TestCrossMatch:
    def test_exact_match_within_tolerance(self) -> None:
        left = [_pos(10.0, 20.0)]
        right = [_pos(10.0001, 20.0001)]
        result = cross_match(left, right, tolerance_arcsec=5.0)
        assert len(result.matches) == 1
        assert result.matches[0].left_index == 0
        assert result.matches[0].right_index == 0
        assert result.unmatched_left == []

    def test_outside_tolerance_is_unmatched(self) -> None:
        left = [_pos(10.0, 20.0)]
        right = [_pos(11.0, 21.0)]
        result = cross_match(left, right, tolerance_arcsec=5.0)
        assert result.matches == []
        assert result.unmatched_left == [0]

    def test_picks_nearest_of_several(self) -> None:
        left = [_pos(10.0, 20.0)]
        right = [_pos(10.5, 20.5), _pos(10.0002, 20.0), _pos(9.0, 19.0)]
        result = cross_match(left, right, tolerance_arcsec=5.0)
        assert result.matches[0].right_index == 1

    def test_empty_left(self) -> None:
        result = cross_match([], [_pos(1, 1)], tolerance_arcsec=5.0)
        assert result.matches == []
        assert result.unmatched_left == []

    def test_empty_right_all_unmatched(self) -> None:
        result = cross_match([_pos(1, 1), _pos(2, 2)], [], tolerance_arcsec=5.0)
        assert result.unmatched_left == [0, 1]

    def test_ra_wraparound_match(self) -> None:
        # 359.9999 and 0.0001 are ~0.7 arcsec apart across the RA=0 seam.
        left = [_pos(359.9999, 0.0)]
        right = [_pos(0.0001, 0.0)]
        result = cross_match(left, right, tolerance_arcsec=5.0)
        assert len(result.matches) == 1
        assert result.matches[0].separation.value == pytest.approx(0.72, abs=0.1)

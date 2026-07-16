"""Positional cross-matching.

Given a list of targets and a list of catalog sources, find the nearest catalog
source to each target within a tolerance. Uses astropy's KD-tree matcher so the
result is exact and fast.
"""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import SkyCoord
from pydantic import BaseModel

from skyquery.models.coordinates import SkyPosition
from skyquery.models.quantity import Measurement


class CrossMatch(BaseModel):
    """One matched pair from a cross-match."""

    left_index: int
    right_index: int
    separation: Measurement


class CrossMatchResult(BaseModel):
    """The result of matching two position lists."""

    matches: list[CrossMatch]
    unmatched_left: list[int]
    tolerance_arcsec: float


def cross_match(
    left: list[SkyPosition],
    right: list[SkyPosition],
    *,
    tolerance_arcsec: float,
) -> CrossMatchResult:
    """Match each ``left`` position to its nearest ``right`` position.

    A left position is matched only if its nearest right neighbour lies within
    ``tolerance_arcsec``; otherwise it is reported as unmatched. Matching uses
    ICRS internally so mixed input frames are handled consistently.

    Args:
        left: The target positions to match.
        right: The catalog positions to match against.
        tolerance_arcsec: The maximum separation for a valid match, in arcseconds.
    """
    if not left:
        return CrossMatchResult(matches=[], unmatched_left=[], tolerance_arcsec=tolerance_arcsec)
    if not right:
        return CrossMatchResult(
            matches=[], unmatched_left=list(range(len(left))), tolerance_arcsec=tolerance_arcsec
        )

    left_coords = _stack(left)
    right_coords = _stack(right)
    idx, sep2d, _ = left_coords.match_to_catalog_sky(right_coords)

    matches: list[CrossMatch] = []
    unmatched: list[int] = []
    tol = tolerance_arcsec * u.arcsec
    # idx and sep2d are 0-d arrays when there is a single left coordinate.
    idx_list = [int(idx)] if idx.ndim == 0 else [int(i) for i in idx]
    sep_list = [sep2d] if sep2d.isscalar else list(sep2d)
    for li, (ri, sep) in enumerate(zip(idx_list, sep_list, strict=True)):
        if sep <= tol:
            matches.append(
                CrossMatch(
                    left_index=li,
                    right_index=ri,
                    separation=Measurement.from_quantity(sep.to(u.arcsec)),
                )
            )
        else:
            unmatched.append(li)
    return CrossMatchResult(
        matches=matches, unmatched_left=unmatched, tolerance_arcsec=tolerance_arcsec
    )


def _stack(positions: list[SkyPosition]) -> SkyCoord:
    coords = [p.to_skycoord().icrs for p in positions]
    ras = [c.ra.deg for c in coords] * u.deg
    decs = [c.dec.deg for c in coords] * u.deg
    return SkyCoord(ra=ras, dec=decs, frame="icrs")

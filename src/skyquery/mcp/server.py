"""The SkyQuery MCP server (stdio transport).

Exposes SkyQuery's normalized toolkit to any MCP-compatible assistant. Every
tool returns a typed pydantic model, so the assistant receives structured,
unit-tagged, provenance-carrying content rather than a raw table it has to
reverse-engineer. Tool docstrings are written to teach the assistant how to
chain calls: resolve a name to a position, a position to a catalog, an object to
its papers.

Logs go to stderr only; stdout is reserved for the MCP protocol.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from skyquery import services
from skyquery.client import SkyQuery
from skyquery.core.convert import convert_unit, parallax_to_distance, transform_frame
from skyquery.errors import SkyQueryError
from skyquery.logging import configure_logging
from skyquery.models.catalog import CatalogTable
from skyquery.models.coordinates import Frame, SkyPosition
from skyquery.models.ephemeris import Ephemeris
from skyquery.models.object import Object
from skyquery.models.paper import Paper
from skyquery.models.provenance import Citation
from skyquery.models.quantity import Measurement
from skyquery.services.operations import ApophisReport, ObjectDossier
from skyquery.sources.nasa import AstronomyPicture
from skyquery.sources.sbdb import SmallBody

mcp = FastMCP("SkyQuery")

# One shared client for the process. Replay/live is governed by the environment
# (SKYQUERY_REPLAY), so the server is deterministic and offline-safe by default.
_app = SkyQuery()


# --------------------------------------------------------------------------- #
# Object intelligence
# --------------------------------------------------------------------------- #
@mcp.tool()
def resolve_object(name: str) -> Object:
    """Resolve an astronomical object name or identifier to normalized data.

    Returns canonical coordinates (ICRS degrees), object type, cross-identifiers,
    and measured properties (parallax, proper motion, redshift, magnitudes), each
    carrying its unit and a provenance record you can cite. Try SIMBAD-style
    names like "Vega", "M31", "Betelgeuse", or catalog ids. This is usually the
    first call: downstream tools take the returned RA/Dec.
    """
    return services.resolve_object(_app, name)


@mcp.tool()
def object_dossier(name: str, with_papers: bool = True) -> ObjectDossier:
    """Resolve an object and, optionally, attach recent papers about it.

    Combines object intelligence with a literature lookup in one call. Use when a
    user asks "tell me about X" and wants both the numbers and the references.
    """
    return services.object_dossier(_app, name, with_papers=with_papers)


# --------------------------------------------------------------------------- #
# Ephemerides and small bodies (the headline capability)
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_ephemeris(
    target: str,
    start: str = Field(description="UT start date, YYYY-MM-DD or YYYY-MM-DD HH:MM"),
    stop: str = Field(description="UT stop date, YYYY-MM-DD or YYYY-MM-DD HH:MM"),
    step: str = Field(default="1h", description="Sampling step such as 1h, 30m, or 1d"),
    observer_location: str = "500@399",
) -> Ephemeris:
    """Compute a solar-system body's apparent ephemeris from JPL Horizons.

    Returns a time series of ICRS position, distance (delta, in AU), range rate,
    and V magnitude for a body such as "99942 Apophis", "Ceres", or "C/2023 A3".
    ``observer_location`` is a Horizons code; "500@399" is geocentric. This is the
    capability the other astronomy MCP servers skip, so prefer it for "where is
    <body> on <date>" questions. Windows that would exceed ~2000 samples are rejected.
    """
    return services.ephemeris(
        _app, target, start=start, stop=stop, step=step, location=observer_location
    )


@mcp.tool()
def get_small_body(designation: str) -> SmallBody:
    """Look up an asteroid or comet's physical and orbital parameters (JPL SBDB).

    Returns diameter, absolute magnitude, albedo, rotation period, and osculating
    orbital elements, each unit-tagged. Pair with get_ephemeris to answer "how big
    is it and where is it".
    """
    return services.small_body(_app, designation)


@mcp.tool()
def apophis_demo(with_paper: bool = True) -> ApophisReport:
    """The headline demo: asteroid Apophis size, its 2029 close approach, a paper.

    Answers "where is Apophis, how big is it, and what is the latest paper" in one
    call, combining SBDB, Horizons, and the literature with full provenance.
    """
    return services.apophis_report(_app, with_paper=with_paper)


# --------------------------------------------------------------------------- #
# Catalogs and cross-match
# --------------------------------------------------------------------------- #
@mcp.tool()
def cone_search(
    center: str,
    radius_deg: float = Field(default=0.05, gt=0, le=5.0),
    catalog: str = "gaia",
    row_limit: int = Field(default=20, ge=1, le=100),
) -> CatalogTable:
    """Return catalog sources within a radius of a position.

    ``center`` may be an object name (resolved via SIMBAD) or "RA DEC" in degrees.
    ``catalog`` is "gaia" for Gaia DR3, or a VizieR catalog id such as "II/246"
    for 2MASS. Every column is unit-tagged. Radius is capped at 5 degrees and
    ``row_limit`` at 100 to protect free public services.
    """
    parsed = _parse_center(center)
    return services.cone_search(_app, parsed, radius_deg, catalog=catalog, row_limit=row_limit)


class CrossMatchOutput(BaseModel):
    """A normalized cross-match result."""

    tolerance_arcsec: float
    matched: list[dict[str, object]]
    unmatched_targets: list[str]


@mcp.tool()
def crossmatch(
    targets: list[str],
    catalog: str = "gaia",
    tolerance_arcsec: float = Field(default=5.0, gt=0, le=60.0),
) -> CrossMatchOutput:
    """Match a list of target names to their nearest source in a catalog.

    Resolves each name to a position, then finds the nearest catalog source within
    ``tolerance_arcsec``. Reports both matches (with separation) and any targets
    with no source inside the tolerance. At most 50 targets per call.
    """
    result = services.crossmatch_targets(
        _app, targets, catalog=catalog, tolerance_arcsec=tolerance_arcsec
    )
    matched = [
        {
            "target": targets[m.left_index] if m.left_index < len(targets) else m.left_index,
            "separation_arcsec": m.separation.value,
        }
        for m in result.matches
    ]
    unmatched = [targets[i] for i in result.unmatched_left if i < len(targets)]
    return CrossMatchOutput(
        tolerance_arcsec=result.tolerance_arcsec, matched=matched, unmatched_targets=unmatched
    )


# --------------------------------------------------------------------------- #
# Literature
# --------------------------------------------------------------------------- #
@mcp.tool()
def search_literature(
    query: str,
    rows: int = Field(default=5, ge=1, le=50),
    prefer: str = "ads",
) -> list[Paper]:
    """Search the astronomy literature (NASA ADS, or arXiv when no ADS key is set).

    Returns normalized paper records with title, authors, year, bibcode, and a
    resolvable URL. ADS needs a free token configured via `skyquery login`; without
    one, SkyQuery falls back to arXiv automatically. ``rows`` is capped at 50.
    """
    return services.literature(_app, query, prefer=prefer, rows=rows)


# --------------------------------------------------------------------------- #
# Analysis (deterministic core, no network)
# --------------------------------------------------------------------------- #
@mcp.tool()
def convert_units(value: float, from_unit: str, to_unit: str) -> Measurement:
    """Convert a value between physical units with astropy's tested conversions.

    Example: convert a parallax in mas, a distance in pc to ly, a velocity in km/s.
    Returns the converted value tagged with its new unit. Rejects unit mismatches.
    """
    return convert_unit(Measurement(value=value, unit=from_unit), to_unit)


@mcp.tool()
def convert_frame(
    ra_deg: float,
    dec_deg: float,
    from_frame: Frame = "icrs",
    to_frame: Frame = "galactic",
) -> SkyPosition:
    """Transform coordinates between reference frames (ICRS, FK5, FK4, Galactic).

    Uses astropy's tested transforms, never hand-rolled trigonometry. Returns the
    position in the target frame with the frame explicitly labeled.
    """
    return transform_frame(SkyPosition(lon=ra_deg, lat=dec_deg, frame=from_frame), to_frame)


@mcp.tool()
def distance_from_parallax(parallax_mas: float) -> Measurement:
    """Convert a parallax in milliarcseconds to a distance in parsecs.

    Rejects non-positive parallaxes, for which distance is undefined, rather than
    returning a nonsense number.
    """
    return parallax_to_distance(Measurement(value=parallax_mas, unit="mas"))


# --------------------------------------------------------------------------- #
# NASA "wonder" layer
# --------------------------------------------------------------------------- #
@mcp.tool()
def astronomy_picture_of_the_day(date: str | None = None) -> AstronomyPicture:
    """Fetch NASA's Astronomy Picture of the Day (APOD) for a date, or today.

    Works with the public DEMO_KEY out of the box; configure a free NASA key via
    `skyquery login` for higher rate limits.
    """
    return _app.nasa.apod(date)


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #
@mcp.tool()
def session_citations() -> list[Citation]:
    """Return the deduplicated acknowledgments for every source used this session.

    Call this at the end of a research conversation to get a ready-to-paste
    citations block honoring each service's acknowledgment policy.
    """
    return _app.citations()


def _parse_center(center: str) -> str | tuple[float, float]:
    parts = center.replace(",", " ").split()
    if len(parts) == 2:
        try:
            return (float(parts[0]), float(parts[1]))
        except ValueError:
            return center
    return center


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    configure_logging(level=logging.INFO)
    try:
        mcp.run(transport="stdio")
    except SkyQueryError as exc:  # pragma: no cover - defensive top-level guard
        logging.getLogger("skyquery").error("fatal: %s", exc)
        raise


if __name__ == "__main__":  # pragma: no cover
    main()

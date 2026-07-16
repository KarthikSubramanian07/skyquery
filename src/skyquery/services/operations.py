"""Composed operations shared by the CLI and the MCP server."""

from __future__ import annotations

from pydantic import BaseModel

from skyquery.core.convert import (
    angular_separation as _angular_separation,
)
from skyquery.core.crossmatch import CrossMatchResult, cross_match
from skyquery.core.limits import (
    clamp_literature_rows,
    clamp_query_text,
    clamp_radius_deg,
    clamp_row_limit,
    clamp_targets,
    validate_ephemeris_window,
)
from skyquery.errors import NotFoundError
from skyquery.models.catalog import CatalogTable
from skyquery.models.coordinates import SkyPosition
from skyquery.models.ephemeris import Ephemeris
from skyquery.models.object import Object
from skyquery.models.observation import ObservationWindow
from skyquery.models.paper import Paper
from skyquery.models.quantity import Measurement
from skyquery.sources.sbdb import SmallBody

# Imported lazily where needed to keep this module import-light for typing tools.


class ObjectDossier(BaseModel):
    """An object plus the papers that measured it."""

    object: Object
    papers: list[Paper] = []


class ApophisReport(BaseModel):
    """The headline demo answer: where is it, how big is it, latest paper."""

    body: SmallBody
    closest_epoch: str
    closest_distance_au: Measurement
    closest_distance_lunar: Measurement
    v_magnitude: Measurement | None
    latest_paper: Paper | None
    narrative: str


def resolve_object(app: object, name: str) -> Object:
    """Resolve a name via SIMBAD, falling back to NED for extragalactic names."""
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    try:
        obj = app.simbad.resolve(name)
        app.track(obj.provenance)
        return obj
    except NotFoundError:
        obj = app.ned.resolve(name)
        app.track(obj.provenance)
        return obj


def object_dossier(app: object, name: str, *, with_papers: bool = False) -> ObjectDossier:
    """Resolve an object and, optionally, attach recent literature about it."""
    obj = resolve_object(app, name)
    papers: list[Paper] = []
    if with_papers:
        papers = literature(app, f'object:"{name}"', prefer="ads", rows=3)
    return ObjectDossier(object=obj, papers=papers)


def ephemeris(
    app: object,
    target: str,
    *,
    start: str,
    stop: str,
    step: str = "1h",
    location: str = "500@399",
) -> Ephemeris:
    """Return a JPL Horizons ephemeris for a solar-system body."""
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    validate_ephemeris_window(start, stop, step)
    eph = app.horizons.ephemerides(target, location=location, start=start, stop=stop, step=step)
    app.track(eph.provenance)
    return eph


def small_body(app: object, designation: str) -> SmallBody:
    """Return the SBDB physical and orbital summary for a small body."""
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    body = app.sbdb.small_body(designation)
    app.track(body.provenance)
    return body


def cone_search(
    app: object,
    center: str | tuple[float, float],
    radius_deg: float,
    *,
    catalog: str = "gaia",
    row_limit: int = 20,
) -> CatalogTable:
    """Cone search a catalog around a name or an (ra, dec) pair."""
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    radius_deg = clamp_radius_deg(radius_deg)
    row_limit = clamp_row_limit(row_limit, ceiling=app.settings.row_limit)
    if isinstance(center, str):
        obj = resolve_object(app, center)
        if obj.position is None:
            raise NotFoundError(f"{center!r} resolved but has no position")
        ra, dec = obj.position.lon, obj.position.lat
    else:
        ra, dec = center
    if catalog.lower() == "gaia":
        table = app.gaia.cone_search(ra, dec, radius_deg, row_limit=row_limit)
    else:
        table = app.vizier.query_region(catalog, ra, dec, radius_deg, row_limit=row_limit)
    app.track(table.provenance)
    return table


def crossmatch_targets(
    app: object,
    targets: list[str],
    *,
    catalog: str = "gaia",
    tolerance_arcsec: float = 5.0,
    radius_deg: float = 0.01,
) -> CrossMatchResult:
    """Resolve each target and match it to its nearest source in a catalog."""
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    targets = clamp_targets(targets)
    radius_deg = clamp_radius_deg(radius_deg)
    left: list[SkyPosition] = []
    for name in targets:
        obj = resolve_object(app, name)
        if obj.position is not None:
            left.append(obj.position)
    right: list[SkyPosition] = []
    for pos in left:
        table = cone_search(app, (pos.lon, pos.lat), radius_deg, catalog=catalog, row_limit=1)
        for row in table.rows:
            if row.get("ra") is not None and row.get("dec") is not None:
                right.append(SkyPosition(lon=float(row["ra"]), lat=float(row["dec"])))
    return cross_match(left, right, tolerance_arcsec=tolerance_arcsec)


def literature(app: object, query: str, *, prefer: str = "arxiv", rows: int = 5) -> list[Paper]:
    """Search the literature. Uses ADS when a key is set, else arXiv."""
    from skyquery.auth import get_credential
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    query = clamp_query_text(query)
    rows = clamp_literature_rows(rows)
    use_ads = prefer == "ads" and get_credential("ads") is not None
    papers = (
        app.ads.search(query, rows=rows) if use_ads else app.arxiv.search(query, max_results=rows)
    )
    for paper in papers:
        app.track(paper.provenance)
    return papers


def observability(
    app: object,
    target: str,
    *,
    site: str,
    date_utc: str,
    min_altitude_deg: float = 30.0,
) -> ObservationWindow:
    """Compute a target's observability from a site over a UTC day."""
    from skyquery.sources.planning import observability as _observability

    obj = resolve_object(app, target)
    if obj.position is None:
        raise NotFoundError(f"{target!r} resolved but has no position")
    window = _observability(
        target_name=obj.name,
        position=obj.position,
        site=site,
        date_utc=date_utc,
        min_altitude_deg=min_altitude_deg,
    )
    from skyquery.client import SkyQuery

    assert isinstance(app, SkyQuery)
    app.track(window.provenance)
    return window


def apophis_report(app: object, *, with_paper: bool = True) -> ApophisReport:
    """The headline demo: Apophis size, its 2029 close approach, and a paper.

    Ephemeris covers the well-known 2029-04-13 close approach. Distances are
    reported in both AU and lunar distances, unit-tagged and sourced.
    """
    body = small_body(app, "Apophis")
    eph = ephemeris(app, "99942 Apophis", start="2029-04-13", stop="2029-04-14", step="1h")
    closest = min(
        (r for r in eph.rows if r.delta and r.delta.value is not None),
        key=lambda r: r.delta.value,  # type: ignore[union-attr,return-value]
    )
    assert closest.delta is not None
    dist_au = closest.delta
    # Convert AU -> lunar distance (1 LD = 384400 km); the unit is registered in
    # skyquery.core.units so it round-trips through the Measurement schema.
    dist_ld = dist_au.to("LD")

    paper = None
    if with_paper:
        papers = literature(app, "Apophis", prefer="arxiv", rows=1)
        paper = papers[0] if papers else None

    diam = body.diameter
    diam_str = f"{diam.value:g} km" if diam and diam.value else "unknown size"
    narrative = (
        f"{body.fullname} is about {diam_str}. On {closest.epoch_utc} it passes "
        f"{dist_au.value:.6f} AU from Earth ({dist_ld.value:.2f} lunar distances), "
        f"inside geostationary orbit. Source: JPL Horizons and SBDB."
    )
    return ApophisReport(
        body=body,
        closest_epoch=closest.epoch_utc,
        closest_distance_au=dist_au,
        closest_distance_lunar=dist_ld,
        v_magnitude=closest.v_magnitude,
        latest_paper=paper,
        narrative=narrative,
    )


def angular_separation(a: SkyPosition, b: SkyPosition) -> Measurement:
    """Great-circle separation between two positions (re-exported for tools)."""
    return _angular_separation(a, b)

"""JPL Small-Body Database adapter (NASA/JPL-Caltech).

Physical and orbital parameters for asteroids and comets: diameter, absolute
magnitude, albedo, rotation period, and osculating elements. Pairs with Horizons
to answer "where is it, and how big is it" in one breath.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pydantic import BaseModel

from skyquery.errors import NotFoundError
from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement
from skyquery.sources.base import DataSource


class SmallBody(BaseModel):
    """Normalized small-body physical and orbital summary."""

    fullname: str
    neo: bool = False
    pha: bool = False
    orbit_class: str | None = None
    diameter: Measurement | None = None
    absolute_magnitude: Measurement | None = None
    albedo: Measurement | None = None
    rotation_period: Measurement | None = None
    eccentricity: Measurement | None = None
    semi_major_axis: Measurement | None = None
    perihelion: Measurement | None = None
    inclination: Measurement | None = None
    orbital_period: Measurement | None = None
    provenance: Provenance


class SbdbSource(DataSource):
    source_id: ClassVar[str] = "sbdb"
    service_name: ClassVar[str] = "JPL Small-Body Database"
    homepage: ClassVar[str | None] = "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html"
    requires_key: ClassVar[str | None] = None

    def small_body(self, designation: str) -> SmallBody:
        """Return the physical and orbital summary for a small body."""
        raw, cached = self.fetch("query", {"target": designation})
        if not raw or not raw.get("fullname"):
            raise NotFoundError(f"SBDB has no record for {designation!r}")
        prov = self.provenance(
            "query",
            f"SBDB.query({designation!r}, phys=True)",
            cached=cached,
            url=self.homepage,
        )
        orbit = raw.get("orbit") or {}
        return SmallBody(
            fullname=raw["fullname"],
            neo=bool(raw.get("neo", False)),
            pha=bool(raw.get("pha", False)),
            orbit_class=raw.get("orbit_class"),
            diameter=Measurement.maybe(raw.get("diameter"), "km"),
            absolute_magnitude=Measurement.maybe(raw.get("H"), "mag"),
            albedo=Measurement.maybe(raw.get("albedo"), ""),
            rotation_period=Measurement.maybe(raw.get("rot_per"), "h"),
            eccentricity=Measurement.maybe(orbit.get("e"), ""),
            semi_major_axis=Measurement.maybe(orbit.get("a"), "AU"),
            perihelion=Measurement.maybe(orbit.get("q"), "AU"),
            inclination=Measurement.maybe(orbit.get("i"), "deg"),
            orbital_period=Measurement.maybe(orbit.get("per"), "d"),
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        from astroquery.jplsbdb import SBDB

        if operation != "query":
            raise NotFoundError(f"unsupported SBDB operation {operation!r}")
        data = SBDB.query(params["target"], phys=True)
        obj = data.get("object", {})
        phys = data.get("phys_par", {})
        orbit_src = data.get("orbit", {})
        elements = {e.get("name"): e for e in orbit_src.get("elements", [])} if orbit_src else {}

        def elem(name: str) -> Any:
            entry = elements.get(name)
            return _val(entry.get("value")) if entry else None

        return {
            "fullname": obj.get("fullname"),
            "neo": obj.get("neo") in (True, "Y", "true"),
            "pha": obj.get("pha") in (True, "Y", "true"),
            "orbit_class": (obj.get("orbit_class") or {}).get("name"),
            "diameter": _val(phys.get("diameter")),
            "H": _val(phys.get("H")),
            "albedo": _val(phys.get("albedo")),
            "rot_per": _val(phys.get("rot_per")),
            "orbit": {
                "e": elem("e"),
                "a": elem("a"),
                "q": elem("q"),
                "i": elem("i"),
                "per": elem("per"),
            },
        }


def _val(value: Any) -> Any:
    """Strip astropy units from an SBDB value, returning a plain float when possible."""
    if value is None:
        return None
    raw = getattr(value, "value", value)
    try:
        fv = float(raw)
        return None if math.isnan(fv) else fv
    except (TypeError, ValueError):
        return str(raw)

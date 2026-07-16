"""NED adapter (NASA/IPAC Extragalactic Database).

Extragalactic object intelligence, with a focus on redshift and distance.
Complements SIMBAD for galaxies, quasars, and other extragalactic sources.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from skyquery.errors import NotFoundError
from skyquery.models.coordinates import SkyPosition
from skyquery.models.object import Object
from skyquery.models.quantity import Measurement
from skyquery.sources.base import DataSource


class NedSource(DataSource):
    source_id: ClassVar[str] = "ned"
    service_name: ClassVar[str] = "NASA/IPAC Extragalactic Database (NED)"
    homepage: ClassVar[str | None] = "https://ned.ipac.caltech.edu/"
    requires_key: ClassVar[str | None] = None

    def resolve(self, name: str) -> Object:
        """Resolve an extragalactic object to a normalized :class:`Object`."""
        raw, cached = self.fetch("query_object", {"name": name})
        if not raw or raw.get("name") is None:
            raise NotFoundError(f"NED did not resolve {name!r}")
        prov = self.provenance(
            "query_object", f"Ned.query_object({name!r})", cached=cached, url=self.homepage
        )
        position = None
        if raw.get("ra") is not None and raw.get("dec") is not None:
            position = SkyPosition(lon=float(raw["ra"]), lat=float(raw["dec"]), frame="icrs")
        return Object(
            name=raw["name"],
            object_type=raw.get("type"),
            position=position,
            redshift=Measurement.maybe(raw.get("redshift"), ""),
            radial_velocity=Measurement.maybe(raw.get("velocity"), "km / s"),
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        from astroquery.ned import Ned

        if operation != "query_object":
            raise NotFoundError(f"unsupported NED operation {operation!r}")
        table = Ned.query_object(params["name"])
        if table is None or len(table) == 0:
            return {}
        row = table[0]

        def cell(key: str) -> Any:
            return row[key] if key in table.colnames else None

        def num(value: Any) -> float | None:
            try:
                fv = float(value)
                return None if math.isnan(fv) else fv
            except (TypeError, ValueError):
                return None

        return {
            "name": str(cell("Object Name")) if cell("Object Name") is not None else None,
            "ra": num(cell("RA")),
            "dec": num(cell("DEC")),
            "type": str(cell("Type")) if cell("Type") is not None else None,
            "redshift": num(cell("Redshift")),
            "velocity": num(cell("Velocity")),
        }

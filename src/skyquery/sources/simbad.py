"""SIMBAD adapter (CDS, Strasbourg).

Object intelligence: resolve a name to canonical coordinates, cross-identifiers,
and measured properties. This is the entry point for most SkyQuery workflows,
because everything downstream keys off a resolved position.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from skyquery.errors import NotFoundError
from skyquery.models.coordinates import SkyPosition
from skyquery.models.object import Object, Photometry
from skyquery.models.quantity import Measurement
from skyquery.sources.base import DataSource

# Photometric bands SIMBAD commonly reports, in a friendly display order.
_BANDS = ("U", "B", "V", "R", "I", "J", "H", "K", "G")


class SimbadSource(DataSource):
    source_id: ClassVar[str] = "simbad"
    service_name: ClassVar[str] = "SIMBAD (CDS)"
    homepage: ClassVar[str | None] = "https://simbad.cds.unistra.fr/simbad/"
    requires_key: ClassVar[str | None] = None

    def resolve(self, name: str) -> Object:
        """Resolve a name to a normalized :class:`Object`."""
        raw, cached = self.fetch("query_object", {"name": name})
        if not raw or raw.get("main_id") is None:
            raise NotFoundError(f"SIMBAD did not resolve {name!r}")
        prov = self.provenance(
            "query_object",
            f"Simbad.query_object({name!r})",
            cached=cached,
            url=self.homepage,
        )
        return self._to_object(name, raw, prov)

    def _to_object(self, query_name: str, raw: dict[str, Any], prov: Any) -> Object:
        position = None
        if raw.get("ra") is not None and raw.get("dec") is not None:
            position = SkyPosition(lon=float(raw["ra"]), lat=float(raw["dec"]), frame="icrs")
        photometry = [
            Photometry(band=b, magnitude=m)
            for b in _BANDS
            if (m := Measurement.maybe((raw.get("flux") or {}).get(b), "mag")) is not None
        ]
        return Object(
            name=raw.get("main_id") or query_name,
            object_type=raw.get("otype"),
            position=position,
            identifiers=list(raw.get("ids") or []),
            parallax=Measurement.maybe(raw.get("plx_value"), "mas", raw.get("plx_err")),
            proper_motion_ra=Measurement.maybe(raw.get("pmra"), "mas / yr"),
            proper_motion_dec=Measurement.maybe(raw.get("pmdec"), "mas / yr"),
            radial_velocity=Measurement.maybe(raw.get("rvz_radvel"), "km / s"),
            redshift=Measurement.maybe(raw.get("rvz_redshift"), ""),
            distance=None,
            spectral_type=raw.get("sp_type"),
            photometry=photometry,
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        from astroquery.simbad import Simbad

        if operation != "query_object":
            raise NotFoundError(f"unsupported SIMBAD operation {operation!r}")
        sim = Simbad()
        sim.add_votable_fields(
            "otype", "sp_type", "plx", "pmra", "pmdec", "rvz_radvel", "rvz_redshift", "ids"
        )
        for band in _BANDS:
            try:
                sim.add_votable_fields(f"flux({band})")
            except Exception:
                continue
        table = sim.query_object(params["name"])
        if table is None or len(table) == 0:
            return {}
        row = table[0]

        def cell(key: str) -> Any:
            for candidate in (key, key.upper(), key.lower()):
                if candidate in table.colnames:
                    value = row[candidate]
                    try:
                        return None if bool(getattr(value, "mask", False)) else value
                    except (ValueError, TypeError):
                        return value
            return None

        flux = {b: _to_float(cell(f"flux_{b}") or cell(f"FLUX_{b}")) for b in _BANDS}
        ids_raw = cell("ids")
        ids = str(ids_raw).split("|") if ids_raw else []
        return {
            "main_id": _to_str(cell("main_id")),
            "ra": _to_float(cell("ra")),
            "dec": _to_float(cell("dec")),
            "otype": _to_str(cell("otype")),
            "sp_type": _to_str(cell("sp_type")),
            "plx_value": _to_float(cell("plx_value")),
            "pmra": _to_float(cell("pmra")),
            "pmdec": _to_float(cell("pmdec")),
            "rvz_radvel": _to_float(cell("rvz_radvel")),
            "rvz_redshift": _to_float(cell("rvz_redshift")),
            "flux": {k: v for k, v in flux.items() if v is not None},
            "ids": ids,
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        fv = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(fv) else fv


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").strip()
    return str(value).strip() or None

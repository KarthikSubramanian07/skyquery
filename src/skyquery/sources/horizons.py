"""JPL Horizons adapter (NASA/JPL-Caltech).

The headline capability, and the one the existing NASA MCP servers skip. Precise
apparent positions and observing circumstances for any solar-system body over a
time range. Correctness here is not negotiable, so every value is re-tagged with
its unit and the position carries its frame.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from skyquery.errors import NotFoundError
from skyquery.models.coordinates import SkyPosition
from skyquery.models.ephemeris import Ephemeris, EphemerisRow
from skyquery.models.quantity import Measurement
from skyquery.sources.base import DataSource


class HorizonsSource(DataSource):
    source_id: ClassVar[str] = "horizons"
    service_name: ClassVar[str] = "JPL Horizons"
    homepage: ClassVar[str | None] = "https://ssd.jpl.nasa.gov/horizons/"
    requires_key: ClassVar[str | None] = None

    def ephemerides(
        self,
        target: str,
        *,
        location: str = "500@399",
        start: str,
        stop: str,
        step: str = "1h",
    ) -> Ephemeris:
        """Return an observer ephemeris for a body over a time range.

        Args:
            target: The body, for example ``"99942 Apophis"`` or ``"Ceres"``.
            location: Observer code (``"500@399"`` is geocentric) or site code.
            start: UT calendar start, ``"YYYY-MM-DD [HH:MM]"``.
            stop: UT calendar stop.
            step: Sampling step, for example ``"1h"`` or ``"10d"``.
        """
        params = {
            "target": target,
            "location": location,
            "start": start,
            "stop": stop,
            "step": step,
        }
        raw, cached = self.fetch("ephemerides", params)
        rows_raw = raw.get("rows") or []
        if not rows_raw:
            raise NotFoundError(f"Horizons returned no ephemeris for {target!r}")
        prov = self.provenance(
            "ephemerides",
            f"Horizons(id={target!r}, location={location!r}, "
            f"epochs={{start:{start}, stop:{stop}, step:{step}}}).ephemerides()",
            cached=cached,
            url=self.homepage,
        )
        rows = [self._to_row(r) for r in rows_raw]
        return Ephemeris(
            target=raw.get("target", target),
            observer=raw.get("location", location),
            rows=rows,
            provenance=prov,
        )

    def _to_row(self, r: dict[str, Any]) -> EphemerisRow:
        position = SkyPosition(lon=float(r["RA"]), lat=float(r["DEC"]), frame="icrs")
        return EphemerisRow(
            epoch_utc=str(r.get("datetime_str", "")),
            position=position,
            delta=Measurement.maybe(r.get("delta"), "AU"),
            range_rate=Measurement.maybe(r.get("delta_rate"), "km / s"),
            v_magnitude=Measurement.maybe(r.get("V"), "mag"),
            elongation=Measurement.maybe(r.get("elong"), "deg"),
            phase_angle=Measurement.maybe(r.get("alpha"), "deg"),
            airmass=Measurement.maybe(r.get("airmass"), ""),
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        from astroquery.jplhorizons import Horizons

        if operation != "ephemerides":
            raise NotFoundError(f"unsupported Horizons operation {operation!r}")
        obj = Horizons(
            id=params["target"],
            location=params["location"],
            epochs={"start": params["start"], "stop": params["stop"], "step": params["step"]},
        )
        eph = obj.ephemerides()
        wanted = [
            "datetime_str",
            "RA",
            "DEC",
            "delta",
            "delta_rate",
            "V",
            "elong",
            "alpha",
            "airmass",
        ]
        rows: list[dict[str, Any]] = []
        for row in eph:
            record: dict[str, Any] = {}
            for col in wanted:
                if col in eph.colnames:
                    value = row[col]
                    record[col] = _num(value)
            rows.append(record)
        return {"target": params["target"], "location": params["location"], "rows": rows}


def _num(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bytes,)):
        return value.decode("utf-8", "replace")
    try:
        fv = float(value)
        return None if math.isnan(fv) else fv
    except (TypeError, ValueError):
        return str(value)

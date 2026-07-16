"""Observation planning via astroplan.

Not a network service but a local calculation: given a resolved target position
and a ground site, compute observability, rise/transit/set, and an airmass curve.
The math runs through astroplan and astropy so it is correct by construction.
"""

from __future__ import annotations

from skyquery.models.coordinates import SkyPosition
from skyquery.models.observation import ObservabilityPoint, ObservationWindow
from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement


def observability(
    *,
    target_name: str,
    position: SkyPosition,
    site: str,
    date_utc: str,
    min_altitude_deg: float = 30.0,
    samples: int = 24,
) -> ObservationWindow:
    """Compute a target's observability from a site over one UTC day.

    Args:
        target_name: Display name for the target.
        position: The target's sky position (any frame; transformed internally).
        site: An astropy/astroplan site name, for example ``"Kitt Peak"``.
        date_utc: The UTC date, ``"YYYY-MM-DD"``.
        min_altitude_deg: The altitude horizon limit used for rise/set.
        samples: Number of samples across the 24-hour window.
    """
    import astropy.units as u
    import numpy as np
    from astroplan import FixedTarget, Observer
    from astropy.time import Time

    observer = Observer.at_site(site)
    coord = position.to_skycoord().icrs
    target = FixedTarget(coord=coord, name=target_name)
    midnight = Time(f"{date_utc} 00:00:00", scale="utc")

    offsets = np.linspace(0.0, 1.0, samples + 1) * u.day
    times = midnight + offsets
    altaz = observer.altaz(times, target)

    points: list[ObservabilityPoint] = []
    max_alt = -90.0
    for t, alt, az in zip(times, altaz.alt, altaz.az, strict=True):
        alt_deg = float(alt.to(u.deg).value)
        max_alt = max(max_alt, alt_deg)
        points.append(
            ObservabilityPoint(
                time_utc=t.isot,
                altitude=Measurement(value=alt_deg, unit="deg"),
                azimuth=Measurement(value=float(az.to(u.deg).value), unit="deg"),
                airmass=Measurement.maybe(_airmass(alt_deg), ""),
            )
        )

    rise = _safe_time(observer.target_rise_time(midnight, target, horizon=min_altitude_deg * u.deg))
    sett = _safe_time(observer.target_set_time(midnight, target, horizon=min_altitude_deg * u.deg))
    transit = _safe_time(observer.target_meridian_transit_time(midnight, target))

    prov = Provenance(
        source="astroplan",
        service="astroplan / astropy",
        query=f"observability(target={target_name!r}, site={site!r}, date={date_utc})",
        citation=None,
    )
    return ObservationWindow(
        target=target_name,
        site=observer.name or site,
        rise_time_utc=rise,
        set_time_utc=sett,
        transit_time_utc=transit,
        max_altitude=Measurement(value=max_alt, unit="deg"),
        ever_observable=max_alt >= min_altitude_deg,
        points=points,
        provenance=prov,
    )


def _airmass(alt_deg: float) -> float | None:
    import math

    if alt_deg <= 5.0:
        return None
    return 1.0 / math.cos(math.radians(90.0 - alt_deg))


def _safe_time(value: object) -> str | None:
    try:
        isot = getattr(value, "isot", None)
        if isot is None:
            return None
        text = str(isot)
        return None if text.lower() == "nan" else text
    except Exception:
        return None

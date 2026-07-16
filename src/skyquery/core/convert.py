"""Unit, frame, and epoch conversion.

This is the single most trust-critical module in SkyQuery. A confidently wrong
coordinate is the one failure an astronomer cannot forgive, so every conversion
here delegates to astropy's tested transforms. We never hand-roll trigonometry.
"""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time

from skyquery.models.coordinates import Frame, SkyPosition
from skyquery.models.quantity import Measurement


def convert_unit(measurement: Measurement, target_unit: str) -> Measurement:
    """Convert a :class:`Measurement` to ``target_unit``.

    Raises:
        astropy.units.UnitConversionError: if the units are not convertible.
    """
    return measurement.to(target_unit)


def transform_frame(
    position: SkyPosition, target_frame: Frame, epoch: str | None = None
) -> SkyPosition:
    """Transform a :class:`SkyPosition` to another reference frame.

    Args:
        position: The source position, carrying its own frame.
        target_frame: One of ``"icrs"``, ``"fk5"``, ``"fk4"``, ``"galactic"``.
        epoch: Optional equinox for ``fk5``/``fk4`` targets, for example ``"J2000.0"``.
    """
    coord = position.to_skycoord()
    if target_frame in ("fk5", "fk4") and epoch:
        transformed = coord.transform_to(f"{target_frame}")
        transformed = transformed.transform_to(  # apply the requested equinox
            SkyCoord(0, 0, unit="deg", frame=target_frame, equinox=epoch).frame
        )
    else:
        transformed = coord.transform_to(target_frame)
    return SkyPosition.from_skycoord(transformed)


def to_altaz(
    position: SkyPosition,
    *,
    latitude_deg: float,
    longitude_deg: float,
    height_m: float,
    time_utc: str,
    pressure_hpa: float = 0.0,
) -> tuple[Measurement, Measurement]:
    """Compute apparent altitude and azimuth from a ground site.

    With ``pressure_hpa=0`` (the default) atmospheric refraction is disabled, which
    matches the geometric AltAz an astronomer expects when reasoning about pointing.

    Returns:
        A ``(altitude, azimuth)`` pair of :class:`Measurement` in degrees.
    """
    location = EarthLocation(
        lat=latitude_deg * u.deg, lon=longitude_deg * u.deg, height=height_m * u.m
    )
    obstime = Time(time_utc, scale="utc")
    frame = AltAz(
        obstime=obstime,
        location=location,
        pressure=pressure_hpa * u.hPa,
    )
    altaz = position.to_skycoord().transform_to(frame)
    return (
        Measurement.from_quantity(altaz.alt.to(u.deg)),
        Measurement.from_quantity(altaz.az.to(u.deg)),
    )


def propagate_proper_motion(
    position: SkyPosition,
    *,
    pm_ra_cosdec_mas_yr: float,
    pm_dec_mas_yr: float,
    from_epoch: str,
    to_epoch: str,
    parallax_mas: float | None = None,
    radial_velocity_km_s: float | None = None,
) -> SkyPosition:
    """Propagate a position from one epoch to another using proper motion.

    ``pm_ra_cosdec_mas_yr`` is the RA proper motion already multiplied by
    ``cos(dec)``, which is the convention SIMBAD and Gaia report.
    """
    kwargs: dict[str, object] = {
        "ra": position.lon * u.deg,
        "dec": position.lat * u.deg,
        "pm_ra_cosdec": pm_ra_cosdec_mas_yr * u.mas / u.yr,
        "pm_dec": pm_dec_mas_yr * u.mas / u.yr,
        "frame": position.frame,
        "obstime": Time(from_epoch),
    }
    if parallax_mas is not None and parallax_mas > 0:
        kwargs["distance"] = (parallax_mas * u.mas).to(u.pc, equivalencies=u.parallax())
    if radial_velocity_km_s is not None:
        kwargs["radial_velocity"] = radial_velocity_km_s * u.km / u.s
    coord = SkyCoord(**kwargs)
    moved = coord.apply_space_motion(new_obstime=Time(to_epoch))
    return SkyPosition.from_skycoord(moved.icrs if position.frame == "icrs" else moved)


def angular_separation(a: SkyPosition, b: SkyPosition) -> Measurement:
    """The great-circle angular separation between two positions, in arcseconds."""
    sep = a.to_skycoord().separation(b.to_skycoord())
    return Measurement.from_quantity(sep.to(u.arcsec))


def parallax_to_distance(parallax: Measurement) -> Measurement:
    """Convert a parallax measurement to a distance in parsecs.

    Raises:
        ValueError: if the parallax is missing or non-positive.
    """
    if parallax.value is None or parallax.value <= 0:
        raise ValueError("distance is undefined for non-positive parallax")
    dist = parallax.to_quantity().to(u.pc, equivalencies=u.parallax())
    return Measurement.from_quantity(dist)

"""Frame- and epoch-aware sky positions.

A coordinate without a reference frame is not a coordinate, it is a guess. Every
position carries its frame (ICRS, FK5, Galactic, ...) and, where relevant, its
epoch. Conversions go through astropy's tested transforms, never hand-rolled
trigonometry.
"""

from __future__ import annotations

from typing import Literal

from astropy.coordinates import SkyCoord
from pydantic import BaseModel, field_validator

Frame = Literal["icrs", "fk5", "fk4", "galactic"]

_SUPPORTED_FRAMES: frozenset[str] = frozenset({"icrs", "fk5", "fk4", "galactic"})


class SkyPosition(BaseModel):
    """A position on the sky with an explicit reference frame.

    For equatorial frames (``icrs``, ``fk5``, ``fk4``) ``lon`` is Right Ascension
    and ``lat`` is Declination, both in degrees. For ``galactic`` they are the
    Galactic longitude ``l`` and latitude ``b``.

    Attributes:
        lon: Longitude in degrees (RA for equatorial frames), 0 to 360.
        lat: Latitude in degrees (Dec for equatorial frames), -90 to +90.
        frame: The reference frame the coordinates are expressed in.
        epoch: Coordinate epoch such as ``"J2000.0"``, when the frame needs one.
    """

    lon: float
    lat: float
    frame: Frame = "icrs"
    epoch: str | None = None

    model_config = {"frozen": True}

    @field_validator("lon")
    @classmethod
    def _wrap_lon(cls, v: float) -> float:
        # Normalize to [0, 360) so RA 360.0 and RA 0.0 are identical, and negative
        # longitudes wrap cleanly rather than being rejected.
        wrapped = v % 360.0
        return 0.0 if wrapped == 360.0 else wrapped

    @field_validator("lat")
    @classmethod
    def _check_lat(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"latitude {v} out of range [-90, 90]")
        return v

    @field_validator("frame")
    @classmethod
    def _check_frame(cls, v: str) -> str:
        if v not in _SUPPORTED_FRAMES:
            raise ValueError(f"unsupported frame {v!r}; supported: {sorted(_SUPPORTED_FRAMES)}")
        return v

    def to_skycoord(self) -> SkyCoord:
        """Return an astropy :class:`~astropy.coordinates.SkyCoord`."""
        kwargs: dict[str, object] = {"frame": self.frame, "unit": "deg"}
        if self.frame in ("fk5", "fk4") and self.epoch:
            kwargs["equinox"] = self.epoch
        return SkyCoord(self.lon, self.lat, **kwargs)

    @classmethod
    def from_skycoord(cls, coord: SkyCoord) -> SkyPosition:
        """Build a :class:`SkyPosition` from an astropy coordinate."""
        frame_name = coord.frame.name
        if frame_name == "galactic":
            lon = float(coord.l.deg)  # type: ignore[union-attr]
            lat = float(coord.b.deg)  # type: ignore[union-attr]
        else:
            lon = float(coord.spherical.lon.deg)
            lat = float(coord.spherical.lat.deg)
        epoch = None
        equinox = getattr(coord, "equinox", None)
        if equinox is not None:
            epoch = str(equinox)
        frame = frame_name if frame_name in _SUPPORTED_FRAMES else "icrs"
        return cls(lon=lon, lat=lat, frame=frame, epoch=epoch)  # type: ignore[arg-type]

    @property
    def ra_hms(self) -> str:
        """Right Ascension formatted as ``HH:MM:SS.sss`` (equatorial frames only)."""
        return self.to_skycoord().icrs.ra.to_string(
            unit="hourangle", sep=":", precision=3, pad=True
        )

    @property
    def dec_dms(self) -> str:
        """Declination formatted as ``+DD:MM:SS.ss`` (equatorial frames only)."""
        return self.to_skycoord().icrs.dec.to_string(
            unit="deg", sep=":", precision=2, alwayssign=True, pad=True
        )

    def __str__(self) -> str:
        if self.frame == "galactic":
            return f"l={self.lon:.6f} b={self.lat:+.6f} [galactic]"
        return f"RA={self.lon:.6f} Dec={self.lat:+.6f} [{self.frame}]"

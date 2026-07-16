"""The astronomical object model.

An :class:`Object` is the normalized answer to "tell me about this thing in the
sky". It is what SIMBAD, NED, and VizieR resolve to, in one shape.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from skyquery.models.coordinates import SkyPosition
from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement


class Photometry(BaseModel):
    """A single photometric magnitude in a named band."""

    band: str
    magnitude: Measurement


class Object(BaseModel):
    """A resolved astronomical object with measured properties.

    Every measured quantity is a :class:`Measurement` carrying its unit, and the
    position is a frame-aware :class:`SkyPosition`. Missing values are ``None``
    rather than guessed.
    """

    name: str
    object_type: str | None = None
    position: SkyPosition | None = None
    identifiers: list[str] = Field(default_factory=list)
    parallax: Measurement | None = None
    proper_motion_ra: Measurement | None = None
    proper_motion_dec: Measurement | None = None
    radial_velocity: Measurement | None = None
    redshift: Measurement | None = None
    distance: Measurement | None = None
    spectral_type: str | None = None
    photometry: list[Photometry] = Field(default_factory=list)
    provenance: Provenance

    def magnitude(self, band: str) -> Measurement | None:
        """Return the magnitude in ``band`` if present."""
        for phot in self.photometry:
            if phot.band.lower() == band.lower():
                return phot.magnitude
        return None

"""Solar-system ephemerides.

The headline capability. An :class:`Ephemeris` is a time series of a body's
apparent position and observing circumstances as seen from an observer, straight
from JPL Horizons. Positions carry their frame; every other quantity carries its
unit.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from skyquery.models.coordinates import SkyPosition
from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement


class EphemerisRow(BaseModel):
    """One epoch of an ephemeris."""

    epoch_utc: str
    position: SkyPosition
    delta: Measurement | None = None
    range_rate: Measurement | None = None
    v_magnitude: Measurement | None = None
    elongation: Measurement | None = None
    phase_angle: Measurement | None = None
    airmass: Measurement | None = None


class Ephemeris(BaseModel):
    """A body's ephemeris over a range of epochs.

    Attributes:
        target: The body queried, for example ``"99942 Apophis"``.
        observer: The observing location code or description, for example ``"geocentric (500)"``.
        rows: One :class:`EphemerisRow` per epoch, in time order.
        provenance: Where the ephemeris came from and how to cite it.
    """

    target: str
    observer: str
    rows: list[EphemerisRow] = Field(default_factory=list)
    provenance: Provenance

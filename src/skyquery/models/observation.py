"""Observation planning results from astroplan."""

from __future__ import annotations

from pydantic import BaseModel, Field

from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement


class ObservabilityPoint(BaseModel):
    """Airmass and altitude at one instant during a night."""

    time_utc: str
    altitude: Measurement
    azimuth: Measurement
    airmass: Measurement | None = None


class ObservationWindow(BaseModel):
    """A target's observability from a site over a night.

    Attributes:
        target: The target name.
        site: The observing site, for example ``"Kitt Peak National Observatory"``.
        rise_time_utc: When the target rises above the horizon limit, if it does.
        set_time_utc: When the target sets below the horizon limit, if it does.
        transit_time_utc: When the target transits the meridian (its highest point).
        max_altitude: The maximum altitude reached during the window.
        ever_observable: Whether the target is observable at all under the constraints.
        points: A sampled airmass/altitude curve across the night.
        provenance: Where the calculation came from and how to cite it.
    """

    target: str
    site: str
    rise_time_utc: str | None = None
    set_time_utc: str | None = None
    transit_time_utc: str | None = None
    max_altitude: Measurement | None = None
    ever_observable: bool = False
    points: list[ObservabilityPoint] = Field(default_factory=list)
    provenance: Provenance

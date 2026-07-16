"""Custom astronomy units, registered so they round-trip through the schema.

A :class:`~skyquery.models.quantity.Measurement` validates its unit string with
``astropy.units.Unit``, so any custom unit we want to expose (like the lunar
distance) must be enabled globally. Enabling them here, at import time, keeps the
rest of the code free to say ``.to("LD")`` and have it parse everywhere.
"""

from __future__ import annotations

import astropy.units as u

# Lunar distance: the Earth-Moon mean distance, a natural yardstick for reporting
# how close a near-Earth asteroid passes.
LD = u.def_unit(["LD", "lunar_distance"], 384400 * u.km, doc="Lunar distance (Earth-Moon)")

_enabled = False


def enable_custom_units() -> None:
    """Register SkyQuery's custom units with astropy. Idempotent."""
    global _enabled  # noqa: PLW0603 - simple idempotency guard
    if _enabled:
        return
    u.add_enabled_units([LD])
    _enabled = True


enable_custom_units()

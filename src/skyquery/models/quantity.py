"""Unit-tagged scalar values.

Nothing crosses the SkyQuery schema boundary as a bare float. A number is
either a :class:`Measurement` (value plus an astropy-parseable unit, optionally
with an uncertainty) or it is rejected. This is the single rule that stops a
confidently wrong, unit-ambiguous number from reaching an assistant.
"""

from __future__ import annotations

import math
from typing import Any

import astropy.units as u
from astropy.units import Quantity
from pydantic import BaseModel, field_validator, model_validator

from skyquery.core.units import enable_custom_units

# Register custom units (lunar distance, ...) so they parse in the validator below.
enable_custom_units()


class Measurement(BaseModel):
    """A scalar physical value with an explicit unit.

    Attributes:
        value: The numeric value, or ``None`` when the service reported no value.
        unit: An astropy-parseable unit string, for example ``"mas"``, ``"deg"``,
            ``"km / s"``, ``"mag"``. Use ``""`` for dimensionless quantities.
        error: Symmetric 1-sigma uncertainty in the same unit, when known.
    """

    value: float | None
    unit: str
    error: float | None = None

    model_config = {"frozen": True}

    @field_validator("unit")
    @classmethod
    def _validate_unit(cls, v: str) -> str:
        # An empty string is the canonical dimensionless unit.
        if v == "":
            return v
        try:
            u.Unit(v)
        except Exception as exc:
            raise ValueError(f"unparseable unit {v!r}: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _check_error(self) -> Measurement:
        if self.error is not None and self.error < 0:
            raise ValueError("uncertainty must be non-negative")
        return self

    @property
    def astropy_unit(self) -> u.UnitBase:
        return u.dimensionless_unscaled if self.unit == "" else u.Unit(self.unit)

    def to_quantity(self) -> Quantity:
        """Return this measurement as an astropy :class:`~astropy.units.Quantity`."""
        if self.value is None:
            raise ValueError("cannot convert a Measurement with no value to a Quantity")
        return self.value * self.astropy_unit

    def to(self, unit: str | u.UnitBase) -> Measurement:
        """Convert to another unit, preserving the uncertainty."""
        if self.value is None:
            return Measurement(value=None, unit=str(unit), error=None)
        q = self.to_quantity().to(unit)
        err = None
        if self.error is not None:
            err = float((self.error * self.astropy_unit).to(unit).value)
        return Measurement(value=float(q.value), unit=str(q.unit), error=err)

    @classmethod
    def from_quantity(cls, q: Quantity, error: Quantity | None = None) -> Measurement:
        """Build a :class:`Measurement` from an astropy quantity."""
        err = None
        if error is not None:
            err = float(error.to(q.unit).value)
        return cls(value=float(q.value), unit=str(q.unit), error=err)

    @classmethod
    def maybe(cls, value: Any, unit: str, error: Any = None) -> Measurement | None:
        """Return a :class:`Measurement`, or ``None`` if the value is missing or masked."""
        if value is None:
            return None
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(fv):
            return None
        fe = None
        if error is not None:
            try:
                fe = float(error)
                if math.isnan(fe):
                    fe = None
            except (TypeError, ValueError):
                fe = None
        return cls(value=fv, unit=unit, error=fe)

    def __str__(self) -> str:
        if self.value is None:
            return f"n/a {self.unit}".strip()
        core = f"{self.value:g}"
        if self.error is not None:
            core += f" +/- {self.error:g}"
        return f"{core} {self.unit}".strip()

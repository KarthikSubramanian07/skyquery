"""Helpers for turning astropy Tables into JSON-serializable payloads.

Adapters record their live results as plain dicts so fixtures are readable JSON
and normalization can be tested without any astropy Table in the loop.
"""

from __future__ import annotations

import math
from typing import Any


def table_to_payload(table: Any, columns: list[str] | None = None) -> dict[str, Any]:
    """Convert an astropy Table to ``{"columns": {name: unit}, "rows": [...]}``.

    Masked or missing cells become ``None``. Column units are captured as strings
    so the normalizer can re-tag every value.
    """
    names = columns or list(table.colnames)
    col_units: dict[str, str] = {}
    for name in names:
        unit = getattr(table[name], "unit", None)
        col_units[name] = str(unit) if unit is not None else ""

    rows: list[dict[str, Any]] = []
    for row in table:
        record: dict[str, Any] = {}
        for name in names:
            value = row[name]
            record[name] = _scalar(value)
        rows.append(record)
    return {"columns": col_units, "rows": rows}


def _scalar(value: Any) -> Any:
    """Coerce a single table cell to a JSON-safe scalar, or ``None`` if masked."""
    import numpy as np

    if value is None:
        return None
    if isinstance(value, np.ma.core.MaskedConstant):
        return None
    try:
        if hasattr(value, "mask") and bool(value.mask):
            return None
    except (ValueError, TypeError):
        pass
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        fv = float(value)
        return None if math.isnan(fv) else fv
    if isinstance(value, np.str_):
        return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value

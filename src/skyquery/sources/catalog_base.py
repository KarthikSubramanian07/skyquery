"""Shared normalization for tabular catalog sources.

Gaia, VizieR, SDSS, and the VO TAP fallback all return the same shape after our
adapters record them: a ``{"columns": {name: unit}, "rows": [...]}`` payload.
This helper turns that into a :class:`CatalogTable` with unit-tagged columns, so
every tabular source normalizes identically.
"""

from __future__ import annotations

from typing import Any

from skyquery.models.catalog import CatalogTable, Column
from skyquery.models.provenance import Provenance


def payload_to_catalog(
    catalog: str, payload: dict[str, Any], provenance: Provenance
) -> CatalogTable:
    """Build a :class:`CatalogTable` from a recorded table payload."""
    col_units: dict[str, str] = payload.get("columns", {})
    rows: list[dict[str, Any]] = payload.get("rows", [])
    columns = [Column(name=name, unit=unit) for name, unit in col_units.items()]
    if not columns and rows:
        columns = [Column(name=name) for name in rows[0]]
    return CatalogTable(
        catalog=catalog,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        provenance=provenance,
    )

"""Tabular catalog results.

Catalog queries (cone, box, ADQL) return many rows of many columns. We keep the
tabular shape but tag every column with its unit, so a column is never an
ambiguous list of floats.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from skyquery.models.provenance import Provenance


class Column(BaseModel):
    """Metadata for one catalog column."""

    name: str
    unit: str = ""
    description: str | None = None


class CatalogTable(BaseModel):
    """A normalized table of catalog rows with unit-tagged columns.

    Attributes:
        catalog: The catalog or survey the rows came from, for example ``"Gaia DR3"``.
        columns: Column metadata in display order.
        rows: Row dictionaries keyed by column name. Values stay in the column's unit.
        row_count: Number of rows returned (may be less than the catalog total).
        provenance: Where the table came from and how to cite it.
    """

    catalog: str
    columns: list[Column]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    provenance: Provenance

    def column(self, name: str) -> Column | None:
        for col in self.columns:
            if col.name == name:
                return col
        return None

"""SkyQuery's normalized schema.

One shape for every service. Every value carries a unit; every position carries
a frame; every record carries its provenance. This package is the single source
of truth that both the MCP tools and the CLI render.
"""

from __future__ import annotations

from skyquery.models.catalog import CatalogTable, Column
from skyquery.models.coordinates import Frame, SkyPosition
from skyquery.models.data_product import DataProduct, DataProductList
from skyquery.models.ephemeris import Ephemeris, EphemerisRow
from skyquery.models.object import Object, Photometry
from skyquery.models.observation import ObservabilityPoint, ObservationWindow
from skyquery.models.paper import Paper
from skyquery.models.provenance import Citation, Provenance
from skyquery.models.quantity import Measurement

__all__ = [
    "CatalogTable",
    "Citation",
    "Column",
    "DataProduct",
    "DataProductList",
    "Ephemeris",
    "EphemerisRow",
    "Frame",
    "Measurement",
    "Object",
    "ObservabilityPoint",
    "ObservationWindow",
    "Paper",
    "Photometry",
    "Provenance",
    "SkyPosition",
]

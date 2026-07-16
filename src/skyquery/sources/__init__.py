"""Per-source adapters.

Each module wraps exactly one external astronomy service (or, for planning, one
local calculation) behind the :class:`~skyquery.sources.base.DataSource`
interface. The seam is around the service, so a service API change touches
exactly one file.
"""

from __future__ import annotations

from skyquery.sources.ads import AdsSource
from skyquery.sources.arxiv import ArxivSource
from skyquery.sources.base import DataSource, SourceContext
from skyquery.sources.gaia import GaiaSource
from skyquery.sources.horizons import HorizonsSource
from skyquery.sources.mast import MastSource
from skyquery.sources.nasa import NasaSource
from skyquery.sources.ned import NedSource
from skyquery.sources.sbdb import SbdbSource
from skyquery.sources.simbad import SimbadSource
from skyquery.sources.vizier import VizierSource
from skyquery.sources.vo import VoTapSource

# All adapter classes, keyed by their source id, for registry-style access.
ADAPTERS: tuple[type[DataSource], ...] = (
    SimbadSource,
    NedSource,
    VizierSource,
    GaiaSource,
    HorizonsSource,
    SbdbSource,
    AdsSource,
    ArxivSource,
    MastSource,
    NasaSource,
    VoTapSource,
)

__all__ = [
    "ADAPTERS",
    "AdsSource",
    "ArxivSource",
    "DataSource",
    "GaiaSource",
    "HorizonsSource",
    "MastSource",
    "NasaSource",
    "NedSource",
    "SbdbSource",
    "SimbadSource",
    "SourceContext",
    "VizierSource",
    "VoTapSource",
]

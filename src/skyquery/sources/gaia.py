"""Gaia adapter (ESA / DPAC).

Astrometry and photometry from Gaia DR3 via cone search. Returns a normalized
:class:`~skyquery.models.catalog.CatalogTable`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.models.catalog import CatalogTable
from skyquery.sources.base import DataSource
from skyquery.sources.catalog_base import payload_to_catalog

_COLUMNS = ["source_id", "ra", "dec", "parallax", "pmra", "pmdec", "phot_g_mean_mag", "bp_rp"]


class GaiaSource(DataSource):
    source_id: ClassVar[str] = "gaia"
    service_name: ClassVar[str] = "Gaia DR3 (ESA/DPAC)"
    homepage: ClassVar[str | None] = "https://gea.esac.esa.int/archive/"
    requires_key: ClassVar[str | None] = None

    def cone_search(
        self, ra_deg: float, dec_deg: float, radius_deg: float, *, row_limit: int = 20
    ) -> CatalogTable:
        """Return Gaia DR3 sources within ``radius_deg`` of a position."""
        params = {
            "ra": round(ra_deg, 6),
            "dec": round(dec_deg, 6),
            "radius": radius_deg,
            "row_limit": row_limit,
        }
        raw, cached = self.fetch("cone_search", params)
        prov = self.provenance(
            "cone_search",
            f"Gaia.cone_search(ra={ra_deg:.6f}, dec={dec_deg:.6f}, radius={radius_deg} deg)",
            cached=cached,
            url=self.homepage,
        )
        return payload_to_catalog("Gaia DR3", raw, prov)

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astroquery.gaia import Gaia

        from skyquery.sources._tables import table_to_payload

        previous = getattr(Gaia, "ROW_LIMIT", None)
        Gaia.ROW_LIMIT = int(params["row_limit"])
        try:
            coord = SkyCoord(ra=params["ra"] * u.deg, dec=params["dec"] * u.deg, frame="icrs")
            job = Gaia.cone_search_async(coord, radius=params["radius"] * u.deg)
            table = job.get_results()
        finally:
            if previous is None:
                delattr(Gaia, "ROW_LIMIT")
            else:
                Gaia.ROW_LIMIT = previous
        available = [c for c in _COLUMNS if c in table.colnames]
        return table_to_payload(table, columns=available)

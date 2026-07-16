"""VizieR adapter (CDS, Strasbourg).

Access to thousands of published catalogs. Used for cone queries against a named
catalog and as the access path for surveys like 2MASS (II/246).
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.models.catalog import CatalogTable
from skyquery.sources.base import DataSource
from skyquery.sources.catalog_base import payload_to_catalog


class VizierSource(DataSource):
    source_id: ClassVar[str] = "vizier"
    service_name: ClassVar[str] = "VizieR (CDS)"
    homepage: ClassVar[str | None] = "https://vizier.cds.unistra.fr/"
    requires_key: ClassVar[str | None] = None

    def query_region(
        self,
        catalog: str,
        ra_deg: float,
        dec_deg: float,
        radius_deg: float,
        *,
        row_limit: int = 50,
    ) -> CatalogTable:
        """Return rows from a named VizieR catalog within a radius of a position."""
        params = {
            "catalog": catalog,
            "ra": round(ra_deg, 6),
            "dec": round(dec_deg, 6),
            "radius": radius_deg,
            "row_limit": row_limit,
        }
        raw, cached = self.fetch("query_region", params)
        prov = self.provenance(
            "query_region",
            f"Vizier(catalog={catalog!r}).query_region(ra={ra_deg:.6f}, "
            f"dec={dec_deg:.6f}, radius={radius_deg} deg)",
            cached=cached,
            url=self.homepage,
        )
        return payload_to_catalog(catalog, raw, prov)

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astroquery.vizier import Vizier

        from skyquery.sources._tables import table_to_payload

        viz = Vizier()
        viz.ROW_LIMIT = int(params["row_limit"])
        coord = SkyCoord(ra=params["ra"] * u.deg, dec=params["dec"] * u.deg, frame="icrs")
        result = viz.query_region(coord, radius=params["radius"] * u.deg, catalog=params["catalog"])
        if result is None or len(result) == 0:
            return {"columns": {}, "rows": []}
        return table_to_payload(result[0])

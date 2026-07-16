"""MAST adapter (Barbara A. Mikulski Archive for Space Telescopes).

Locates HST/JWST/TESS/Kepler observations by object. SkyQuery returns product
records with resolvable URLs; it never bulk-downloads by default, keeping the
archive and your disk unsurprised.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.models.data_product import DataProduct, DataProductList
from skyquery.models.quantity import Measurement
from skyquery.sources.base import DataSource


class MastSource(DataSource):
    source_id: ClassVar[str] = "mast"
    service_name: ClassVar[str] = "MAST (STScI)"
    homepage: ClassVar[str | None] = "https://mast.stsci.edu/"
    requires_key: ClassVar[str | None] = None

    def search_observations(
        self, target: str, *, radius_deg: float = 0.02, row_limit: int = 25
    ) -> DataProductList:
        """Find archival observations for an object."""
        params = {"target": target, "radius": radius_deg, "row_limit": row_limit}
        raw, cached = self.fetch("query_object", params)
        prov = self.provenance(
            "query_object",
            f"Observations.query_object({target!r}, radius={radius_deg} deg)",
            cached=cached,
            url=self.homepage,
        )
        rows = raw.get("rows") or []
        products = [self._to_product(r, prov) for r in rows[:row_limit]]
        return DataProductList(
            query_target=target,
            products=products,
            total_found=raw.get("total", len(rows)),
            provenance=prov,
        )

    def _to_product(self, r: dict[str, Any], prov: Any) -> DataProduct:
        return DataProduct(
            obs_id=str(r.get("obs_id", "")),
            title=r.get("target_name"),
            instrument=r.get("instrument_name"),
            product_type=r.get("dataproduct_type"),
            wavelength_band=r.get("wavelength_region"),
            access_url=r.get("dataURL") or r.get("access_url"),
            exposure_time=Measurement.maybe(r.get("t_exptime"), "s"),
            provenance=prov,
        )

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        from astroquery.mast import Observations

        from skyquery.sources._tables import table_to_payload

        table = Observations.query_object(params["target"], radius=f"{params['radius']} deg")
        wanted = [
            "obs_id",
            "target_name",
            "instrument_name",
            "dataproduct_type",
            "wavelength_region",
            "dataURL",
            "t_exptime",
        ]
        available = [c for c in wanted if c in table.colnames]
        payload = table_to_payload(table, columns=available)
        return {"rows": payload["rows"], "total": len(table)}

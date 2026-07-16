"""Generic Virtual Observatory fallback (TAP / ADQL).

Any VO-compliant TAP service not natively wrapped above is still reachable
through this escape hatch. It is deliberately the last resort, not the main
interface, because it returns whatever shape the service defines. SkyQuery still
tags every column with its unit and attaches provenance.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.models.catalog import CatalogTable
from skyquery.sources.base import DataSource
from skyquery.sources.catalog_base import payload_to_catalog


class VoTapSource(DataSource):
    source_id: ClassVar[str] = "vo"
    service_name: ClassVar[str] = "Virtual Observatory TAP"
    homepage: ClassVar[str | None] = "https://www.ivoa.net/"
    requires_key: ClassVar[str | None] = None

    def run_adql(self, tap_url: str, adql: str, *, row_limit: int = 100) -> CatalogTable:
        """Run an ADQL query against an arbitrary TAP endpoint."""
        params = {"tap_url": tap_url, "adql": adql, "row_limit": row_limit}
        raw, cached = self.fetch("run_adql", params)
        prov = self.provenance(
            "run_adql", f"TAP({tap_url}).query({adql!r})", cached=cached, url=tap_url
        )
        return payload_to_catalog(f"TAP:{tap_url}", raw, prov)

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import pyvo  # type: ignore[import-untyped]

        from skyquery.sources._tables import table_to_payload

        service = pyvo.dal.TAPService(params["tap_url"])
        adql = params["adql"]
        if "top" not in adql.lower() and "limit" not in adql.lower():
            adql = adql.replace("SELECT", f"SELECT TOP {params['row_limit']}", 1)
        result = service.search(adql)
        return table_to_payload(result.to_table())

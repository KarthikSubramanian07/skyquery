"""Generic Virtual Observatory fallback (TAP / ADQL).

Any VO-compliant TAP service not natively wrapped above is still reachable
through this escape hatch. It is deliberately the last resort, not the main
interface, because it returns whatever shape the service defines. SkyQuery still
tags every column with its unit and attaches provenance.

TAP URLs are allowlisted (HTTPS + known public hosts) to prevent SSRF. ADQL is
validated as a single SELECT with an enforced ``TOP N`` cap.
"""

from __future__ import annotations

from typing import Any, ClassVar

from skyquery.core.limits import clamp_row_limit
from skyquery.models.catalog import CatalogTable
from skyquery.sources.base import DataSource
from skyquery.sources.catalog_base import payload_to_catalog
from skyquery.sources.vo_policy import prepare_adql, validate_tap_url


class VoTapSource(DataSource):
    source_id: ClassVar[str] = "vo"
    service_name: ClassVar[str] = "Virtual Observatory TAP"
    homepage: ClassVar[str | None] = "https://www.ivoa.net/"
    requires_key: ClassVar[str | None] = None

    def run_adql(self, tap_url: str, adql: str, *, row_limit: int = 100) -> CatalogTable:
        """Run an ADQL query against an allowlisted public TAP endpoint."""
        safe_url = validate_tap_url(tap_url)
        safe_limit = clamp_row_limit(row_limit, ceiling=500)
        safe_adql = prepare_adql(adql, row_limit=safe_limit)
        params = {"tap_url": safe_url, "adql": safe_adql, "row_limit": safe_limit}
        raw, cached = self.fetch("run_adql", params)
        prov = self.provenance(
            "run_adql", f"TAP({safe_url}).query({safe_adql!r})", cached=cached, url=safe_url
        )
        return payload_to_catalog(f"TAP:{safe_url}", raw, prov)

    def _live_fetch(self, operation: str, params: dict[str, Any]) -> Any:
        import pyvo  # type: ignore[import-untyped]

        from skyquery.sources._tables import table_to_payload

        # Re-validate at the live boundary in case a fixture/cache was hand-edited.
        tap_url = validate_tap_url(params["tap_url"])
        adql = prepare_adql(params["adql"], row_limit=int(params["row_limit"]))
        service = pyvo.dal.TAPService(tap_url)
        result = service.search(adql)
        return table_to_payload(result.to_table())

"""Smoke tests for the MCP tool surface.

The tools are thin wrappers over the same operations the CLI uses, so these
verify the wiring, the structured pydantic return types, and that the server
registers the expected tool names. No stdio transport is started.
"""

from __future__ import annotations

import pytest

from skyquery.mcp import server
from skyquery.models.ephemeris import Ephemeris
from skyquery.models.object import Object
from skyquery.models.quantity import Measurement


@pytest.fixture(autouse=True)
def _replay_app(monkeypatch, tmp_path) -> None:  # pyright: ignore[reportUnusedFunction]
    """Point the module-level server app at an offline replay client."""
    from skyquery.client import SkyQuery
    from skyquery.config import Settings

    app = SkyQuery(Settings(replay=True, offline=True, home=tmp_path))
    monkeypatch.setattr(server, "_app", app)


class TestTools:
    def test_resolve_object_returns_typed_object(self) -> None:
        obj = server.resolve_object("Vega")
        assert isinstance(obj, Object)
        assert obj.position is not None

    def test_get_ephemeris_returns_typed_ephemeris(self) -> None:
        eph = server.get_ephemeris(
            "99942 Apophis", start="2029-04-13", stop="2029-04-14", step="1h"
        )
        assert isinstance(eph, Ephemeris)
        assert eph.rows

    def test_apophis_demo_tool(self) -> None:
        report = server.apophis_demo()
        assert "Apophis" in report.body.fullname

    def test_convert_units_tool(self) -> None:
        result = server.convert_units(1.0, "pc", "lyr")
        assert isinstance(result, Measurement)
        assert result.value == pytest.approx(3.2615637, rel=1e-5)

    def test_convert_frame_tool(self) -> None:
        pos = server.convert_frame(279.23473479, 38.78368896, "icrs", "galactic")
        assert pos.frame == "galactic"
        assert pos.lon == pytest.approx(67.4482081386, abs=1e-6)

    def test_distance_from_parallax_tool(self) -> None:
        result = server.distance_from_parallax(130.23)
        assert result.unit == "pc"


class TestServerRegistration:
    @pytest.mark.anyio
    async def test_expected_tools_registered(self) -> None:
        tools = await server.mcp.list_tools()
        names = {t.name for t in tools}
        expected = {
            "resolve_object",
            "get_ephemeris",
            "get_small_body",
            "apophis_demo",
            "cone_search",
            "search_literature",
            "convert_units",
            "convert_frame",
            "session_citations",
        }
        assert expected.issubset(names)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

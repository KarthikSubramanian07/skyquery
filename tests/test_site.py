"""Checks for the agent-facing files of the landing site in ``site/``.

The edge behavior (content negotiation, 404s, the JSON API) is tested in
``tests/edge/agent.test.js``. These tests cover the static and generated files:
that they are current, well-formed, follow their published formats, and agree
with each other and with the MCP server.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse

import pytest
from defusedxml import ElementTree
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_URL = "https://skyquery-mcp.pages.dev"
HTML_PAGES = sorted(p.stem for p in SITE.glob("*.html"))
INDEXABLE = [p for p in HTML_PAGES if p != "404"]


def _load_build_site() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_site"] = module
    spec.loader.exec_module(module)
    return module


build_site = _load_build_site()


def _local_path(url: str) -> Path | None:
    """Map a site URL to the file that serves it, or None for external URLs."""
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != urlparse(SITE_URL).netloc:
        return None
    path = parsed.path
    if path in ("", "/"):
        return SITE / "index.html"
    if path.startswith("/api/v1"):
        rest = path.removeprefix("/api/v1").strip("/") or "index"
        if rest.startswith("tools/"):
            return SITE / "api" / "v1" / "tools.json"
        return SITE / "api" / "v1" / f"{rest}.json"
    candidate = SITE / path.lstrip("/")
    return candidate if candidate.suffix or candidate.exists() else candidate.with_suffix(".html")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.lang = ""
        self.jsonld: list[str] = []
        self.text: list[str] = []
        self._skip = 0
        self._in_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key:
                self.meta[key] = a.get("content", "")
        if tag == "link" and "rel" in a:
            self.links[a["rel"]] = a.get("href", "")
        if tag == "script":
            self._skip += 1
            self._in_jsonld = a.get("type") == "application/ld+json"
        if tag == "style":
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip -= 1
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self.jsonld.append(data)
        elif not self._skip:
            self.text.append(data)

    @property
    def visible_text(self) -> str:
        return " ".join(" ".join(self.text).split())


def _parse(name: str) -> _Page:
    page = _Page()
    page.feed((SITE / f"{name}.html").read_text(encoding="utf-8"))
    return page


# --------------------------------------------------------------------------- #
# Generated files are current
# --------------------------------------------------------------------------- #
def test_generated_files_are_current() -> None:
    stale = [
        str(path.relative_to(ROOT))
        for path, content in build_site.build().items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    assert not stale, f"Run `uv run python scripts/build_site.py`; stale: {stale}"


def test_tool_catalog_matches_mcp_server() -> None:
    from skyquery.mcp import server

    registered = {t.name for t in asyncio.run(server.mcp.list_tools())}
    catalog = json.loads((SITE / "api/v1/tools.json").read_text())
    assert {t["name"] for t in catalog["tools"]} == registered
    assert catalog["count"] == len(registered)


# --------------------------------------------------------------------------- #
# OpenAPI and API catalog
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    return json.loads((SITE / "openapi.json").read_text())


def test_openapi_is_valid(openapi: dict[str, Any]) -> None:
    validate(openapi)
    assert openapi["openapi"].startswith("3.1")


def test_openapi_operations_are_function_calling_ready(openapi: dict[str, Any]) -> None:
    op_ids: list[str] = []
    for path, item in openapi["paths"].items():
        for method, op in item.items():
            op_ids.append(op["operationId"])
            assert re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", op["operationId"])
            assert op.get("description"), f"{method} {path} lacks a description"
            assert op.get("summary")
            for param in op.get("parameters", []):
                assert param["schema"].get("type"), f"untyped parameter in {path}"
                assert param.get("description")
            for status, resp in op["responses"].items():
                schema = resp["content"]["application/json"]["schema"]
                assert schema, f"{path} {status} has no schema"
    assert len(op_ids) == len(set(op_ids)), "operationIds must be unique"


def test_openapi_tool_enum_matches_catalog(openapi: dict[str, Any]) -> None:
    catalog = json.loads((SITE / "api/v1/tools.json").read_text())
    param = openapi["paths"]["/api/v1/tools/{name}"]["get"]["parameters"][0]
    assert param["schema"]["enum"] == [t["name"] for t in catalog["tools"]]


def test_api_payloads_exist_for_every_openapi_path(openapi: dict[str, Any]) -> None:
    for path in openapi["paths"]:
        local = _local_path(SITE_URL + path.replace("{name}", "get_ephemeris"))
        assert local is not None
        assert local.exists(), path


def test_api_catalog_is_rfc9727_linkset() -> None:
    data = json.loads((SITE / ".well-known/api-catalog").read_text())
    (entry,) = data["linkset"]
    assert entry["anchor"].startswith(SITE_URL)
    assert entry["service-desc"][0]["href"] == f"{SITE_URL}/openapi.json"
    assert entry["service-doc"][0]["href"].startswith(SITE_URL)


# --------------------------------------------------------------------------- #
# llms.txt (https://llmstxt.org)
# --------------------------------------------------------------------------- #
def test_llms_txt_follows_spec() -> None:
    text = (SITE / "llms.txt").read_text()
    lines = text.splitlines()
    assert lines[0] == "# SkyQuery"
    first_block = next(line for line in lines[1:] if line.strip())
    assert first_block.startswith("> "), "summary blockquote must follow the H1"
    sections = [line[3:] for line in lines if line.startswith("## ")]
    assert "When to use SkyQuery" in sections
    assert "Optional" in sections
    assert not re.search(r"^#{3,} ", text, re.MULTILINE), "llms.txt uses H2 sections only"


def test_llms_txt_names_every_mcp_tool_it_recommends() -> None:
    text = (SITE / "llms.txt").read_text()
    catalog = json.loads((SITE / "api/v1/tools.json").read_text())
    names = {t["name"] for t in catalog["tools"]}
    mentioned = set(re.findall(r"`([a-z_]+)`", text)) & names
    assert mentioned >= names - {"apophis_demo", "astronomy_picture_of_the_day"}


def test_llms_txt_local_links_resolve() -> None:
    for url in re.findall(r"\]\((https?://[^)]+)\)", (SITE / "llms.txt").read_text()):
        local = _local_path(url)
        if local is not None:
            assert local.exists(), url


# --------------------------------------------------------------------------- #
# Sitemap, robots, routes, headers
# --------------------------------------------------------------------------- #
def test_sitemap_lists_every_indexable_page() -> None:
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ElementTree.parse(SITE / "sitemap.xml").getroot()
    urls = root.findall("sm:url", ns)
    locs = [u.findtext("sm:loc", namespaces=ns) for u in urls]
    for url in urls:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", url.findtext("sm:lastmod", "", ns))
    expected = {f"{SITE_URL}/"} | {f"{SITE_URL}/{p}" for p in INDEXABLE if p != "index"}
    assert set(locs) == expected


def test_robots_points_to_sitemap() -> None:
    assert f"Sitemap: {SITE_URL}/sitemap.xml" in (SITE / "robots.txt").read_text()


def test_routes_json_is_valid() -> None:
    routes = json.loads((SITE / "_routes.json").read_text())
    assert routes["version"] == 1
    assert routes["include"] == ["/*"]
    assert len(routes["include"]) + len(routes["exclude"]) <= 100
    for rule in routes["exclude"]:
        if "*" not in rule:
            assert (SITE / rule.lstrip("/")).exists(), rule


def test_headers_cover_agent_files() -> None:
    headers = (SITE / "_headers").read_text()
    assert "Content-Type: text/markdown; charset=utf-8" in headers
    assert "Content-Type: application/linkset+json" in headers


# --------------------------------------------------------------------------- #
# Pages: Markdown twins, structure, metadata, trust content
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", HTML_PAGES)
def test_every_page_has_a_markdown_twin(name: str) -> None:
    md = (SITE / f"{name}.md").read_text()
    assert md.startswith("# ")
    assert len(md) >= (20 if name == "404" else 500)


@pytest.mark.parametrize("name", HTML_PAGES)
def test_page_structure(name: str) -> None:
    page = _parse(name)
    assert page.lang == "en"
    assert page.headings.count(1) == 1, "exactly one h1"
    assert page.headings[0] == 1, "h1 comes first"
    for prev, cur in zip(page.headings, page.headings[1:], strict=False):
        assert cur <= prev + 1, f"heading jumps from h{prev} to h{cur}"
    assert page.meta.get("og:type")
    assert page.meta.get("og:image", "").startswith(SITE_URL)
    assert page.meta.get("description")


@pytest.mark.parametrize("name", INDEXABLE)
def test_indexable_pages_have_canonical_and_alternate(name: str) -> None:
    page = _parse(name)
    expected = f"{SITE_URL}/" if name == "index" else f"{SITE_URL}/{name}"
    assert page.links["canonical"] == expected
    assert page.links["alternate"] == f"/{name}.md"


def test_404_page_is_noindex() -> None:
    assert "noindex" in _parse("404").meta["robots"]


@pytest.mark.parametrize("name", ["about", "contact", "privacy", "developers"])
def test_trust_and_portal_pages_have_real_content(name: str) -> None:
    assert len(_parse(name).visible_text) >= 500


def test_homepage_content_is_in_raw_html() -> None:
    page = _parse("index")
    assert len(page.visible_text) >= 500
    assert "SkyQuery" in page.visible_text


def test_homepage_links_developer_resources() -> None:
    html = (SITE / "index.html").read_text()
    for href in ("/developers", "/openapi.json", "/llms.txt", "/about", "/contact", "/privacy"):
        assert f'href="{href}"' in html, href


def test_homepage_jsonld() -> None:
    page = _parse("index")
    (block,) = page.jsonld
    graph = json.loads(block)["@graph"]
    by_type = {node["@type"]: node for node in graph}
    app = by_type["SoftwareApplication"]
    assert app["name"] == "SkyQuery"
    assert app["offers"]["price"] == "0"
    org = by_type["Organization"]
    assert org["url"] == f"{SITE_URL}/"
    assert org["contactPoint"]
    address = org["address"]
    assert address["@type"] == "PostalAddress"
    assert address["addressLocality"] == "Berkeley"
    assert address["addressRegion"] == "CA"
    assert address["addressCountry"] == "US"
    for point in org["contactPoint"]:
        assert point["@type"] == "ContactPoint"
        assert point["contactType"]


@pytest.mark.parametrize("name", ["about", "contact", "developers"])
def test_subpage_jsonld(name: str) -> None:
    (block,) = _parse(name).jsonld
    data = json.loads(block)
    assert data["@context"] == "https://schema.org"
    assert data["url"] == f"{SITE_URL}/{name}"


def test_developers_page_documents_every_tool() -> None:
    md = (SITE / "developers.md").read_text()
    catalog = json.loads((SITE / "api/v1/tools.json").read_text())
    for tool in catalog["tools"]:
        assert f"### `{tool['name']}`" in md


def test_render_markdown_adds_heading_ids_and_hides_markers() -> None:
    out = build_site.render_markdown("# T\n\n## Metadata API\n\n<!-- tools:start -->\nx\n")
    assert '<h2 id="metadata-api">' in out
    assert "tools:start" not in out
    assert "<h1>T</h1>" in out

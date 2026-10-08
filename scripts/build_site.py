"""Generate the agent-facing parts of the landing site from their sources of truth.

The marketing homepage (``site/index.html``) is hand-written. Everything an agent
reads is generated here so it cannot drift from the code:

* ``site/api/v1/*.json``: the public metadata API payloads. The tool catalog is
  introspected from the live MCP server, so names and input schemas are exact.
* ``site/openapi.json``: the OpenAPI 3.1 contract for that API.
* ``site/.well-known/api-catalog``: the RFC 9727 API catalog (a linkset).
* The tool reference block inside ``site/developers.md``.
* ``site/{about,contact,privacy,developers,404}.html``: rendered from the
  Markdown files of the same name, which are also served verbatim to agents
  that send ``Accept: text/markdown``.

Run ``uv run python scripts/build_site.py`` after changing a tool or a page, and
``--check`` in CI to fail when committed output is stale.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from skyquery import __version__

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
SITE_URL = "https://skyquery-mcp.pages.dev"
REPO_URL = "https://github.com/KarthikSubramanian07/skyquery"
DOCS_URL = f"{SITE_URL}/developers#metadata-api"

# Pages rendered from Markdown. The homepage is hand-written and excluded.
PAGES: dict[str, dict[str, str]] = {
    "developers": {"schema": "WebPage", "nav": "developers"},
    "about": {"schema": "AboutPage", "nav": ""},
    "contact": {"schema": "ContactPage", "nav": ""},
    "privacy": {"schema": "WebPage", "nav": ""},
    "404": {"schema": "", "nav": ""},
}

SOURCES: list[dict[str, Any]] = [
    {
        "id": "simbad",
        "name": "SIMBAD",
        "provider": "CDS, Strasbourg",
        "provides": "Object identifiers, coordinates, and metadata",
        "key_required": False,
        "url": "https://simbad.cds.unistra.fr/",
    },
    {
        "id": "horizons",
        "name": "JPL Horizons",
        "provider": "NASA JPL Solar System Dynamics",
        "provides": "Solar-system ephemerides and state vectors",
        "key_required": False,
        "url": "https://ssd.jpl.nasa.gov/horizons/",
    },
    {
        "id": "sbdb",
        "name": "JPL Small-Body Database",
        "provider": "NASA JPL Solar System Dynamics",
        "provides": "Small-body physical and orbital parameters",
        "key_required": False,
        "url": "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html",
    },
    {
        "id": "gaia",
        "name": "Gaia DR3",
        "provider": "ESA",
        "provides": "Astrometry and photometry",
        "key_required": False,
        "url": "https://gea.esac.esa.int/archive/",
    },
    {
        "id": "vizier",
        "name": "VizieR",
        "provider": "CDS, Strasbourg",
        "provides": "Thousands of published catalogs, including 2MASS and SDSS",
        "key_required": False,
        "url": "https://vizier.cds.unistra.fr/",
    },
    {
        "id": "ned",
        "name": "NED",
        "provider": "NASA/IPAC",
        "provides": "Extragalactic object data",
        "key_required": False,
        "url": "https://ned.ipac.caltech.edu/",
    },
    {
        "id": "ads",
        "name": "NASA ADS",
        "provider": "NASA / Smithsonian Astrophysical Observatory",
        "provides": "The astronomy literature",
        "key_required": True,
        "url": "https://ui.adsabs.harvard.edu/",
    },
    {
        "id": "arxiv",
        "name": "arXiv",
        "provider": "Cornell University",
        "provides": "astro-ph preprints",
        "key_required": False,
        "url": "https://arxiv.org/",
    },
    {
        "id": "mast",
        "name": "MAST",
        "provider": "STScI",
        "provides": "HST, JWST, TESS, and Kepler data products",
        "key_required": False,
        "url": "https://mast.stsci.edu/",
    },
    {
        "id": "nasa",
        "name": "NASA Open APIs",
        "provider": "NASA",
        "provides": "Astronomy Picture of the Day",
        "key_required": False,
        "url": "https://api.nasa.gov/",
    },
]


# --------------------------------------------------------------------------- #
# Tool catalog (introspected from the MCP server)
# --------------------------------------------------------------------------- #
def _strip_titles(schema: Any) -> Any:
    """Drop pydantic's auto-generated ``title`` keys; they add noise, not meaning."""
    if isinstance(schema, dict):
        return {k: _strip_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_strip_titles(v) for v in schema]
    return schema


def load_tools() -> list[dict[str, Any]]:
    from skyquery.mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    catalog: list[dict[str, Any]] = []
    for tool in sorted(tools, key=lambda t: t.name):
        # cleandoc, not dedent: Python 3.13 pre-strips docstring indentation, 3.12 does not.
        description = inspect.cleandoc(tool.description or "")
        output = tool.output_schema or {}
        catalog.append(
            {
                "name": tool.name,
                "summary": description.splitlines()[0] if description else "",
                "description": description,
                "inputSchema": _strip_titles(tool.input_schema),
                "returns": output.get("title", "object"),
                "url": f"{SITE_URL}/api/v1/tools/{tool.name}",
            }
        )
    return catalog


def _type_label(prop: dict[str, Any]) -> str:
    if "enum" in prop:
        return " \\| ".join(f'`"{v}"`' for v in prop["enum"])
    if "anyOf" in prop:
        return " or ".join(_type_label(p) for p in prop["anyOf"])
    if prop.get("type") == "array":
        return f"array of {_type_label(prop.get('items', {}))}"
    return str(prop.get("type", "any"))


def tool_reference_markdown(tools: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for tool in tools:
        schema = tool["inputSchema"]
        props: dict[str, Any] = schema.get("properties", {})
        required = set(schema.get("required", []))
        body = " ".join(tool["description"].split("\n\n")[0].split())
        rest = [" ".join(p.split()) for p in tool["description"].split("\n\n")[1:]]
        lines = [f"### `{tool['name']}`", "", body, ""]
        lines += [*(f"{p}\n" for p in rest)]
        if props:
            lines += [
                "| Parameter | Type | Required | Default | Notes |",
                "| --- | --- | --- | --- | --- |",
            ]
            for pname, prop in props.items():
                default = json.dumps(prop["default"]) if "default" in prop else ""
                notes = prop.get("description", "")
                limits = [
                    f"{sym} {prop[key]}"
                    for key, sym in (
                        ("exclusiveMinimum", ">"),
                        ("minimum", ">="),
                        ("maximum", "<="),
                    )
                    if key in prop
                ]
                if limits:
                    notes = "; ".join(filter(None, [notes, ", ".join(limits)]))
                req = "yes" if pname in required else "no"
                lines.append(
                    f"| `{pname}` | {_type_label(prop)} | {req} | "
                    f"{f'`{default}`' if default else ''} | {notes} |"
                )
        else:
            lines.append("Takes no parameters.")
        lines += ["", f"Returns: `{tool['returns']}`.", ""]
        parts.append("\n".join(lines))
    return "\n".join(parts).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# API payloads, OpenAPI, and the API catalog
# --------------------------------------------------------------------------- #
def api_payloads(tools: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "index": {
            "name": "SkyQuery metadata API",
            "version": "v1",
            "description": (
                "Public, read-only metadata about SkyQuery's MCP tools and data sources. "
                "Astronomy queries run locally through the SkyQuery MCP server or CLI."
            ),
            "links": {
                "tools": f"{SITE_URL}/api/v1/tools",
                "sources": f"{SITE_URL}/api/v1/sources",
                "status": f"{SITE_URL}/api/v1/status",
                "openapi": f"{SITE_URL}/openapi.json",
                "docs": f"{SITE_URL}/developers",
                "llms": f"{SITE_URL}/llms.txt",
            },
        },
        "tools": {"version": __version__, "count": len(tools), "tools": tools},
        "sources": {"count": len(SOURCES), "sources": SOURCES},
        "status": {
            "status": "ok",
            "version": __version__,
            "install": f"uv tool install git+{REPO_URL}",
            "repository": REPO_URL,
        },
    }


def _ok(description: str, ref: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}}},
    }


def _err(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }


def openapi_spec(tools: list[dict[str, Any]]) -> dict[str, Any]:
    names = [t["name"] for t in tools]
    common_errors = {"405": _err("Method not allowed. Only GET, HEAD, and OPTIONS.")}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "SkyQuery metadata API",
            "version": "1.0.0",
            "summary": "Public, read-only metadata about the SkyQuery astronomy MCP server.",
            "description": (
                "SkyQuery is a free, open-source, local MCP server and CLI that lets AI "
                "assistants query real astronomy data (SIMBAD, JPL Horizons, VizieR, Gaia, "
                "ADS, arXiv) with units and citations attached. This API describes its MCP "
                "tools and upstream data sources so agents can decide whether and how to "
                "use it. It needs no authentication. Astronomy queries themselves run "
                "locally: install with `uv tool install git+" + REPO_URL + "` and run "
                "`skyquery-mcp`."
            ),
            "license": {"name": "MIT", "identifier": "MIT"},
            "contact": {"name": "SkyQuery maintainers", "url": f"{REPO_URL}/issues"},
        },
        "externalDocs": {
            "description": "SkyQuery developer portal",
            "url": f"{SITE_URL}/developers",
        },
        "servers": [{"url": SITE_URL, "description": "Production"}],
        "security": [],
        "tags": [
            {"name": "tools", "description": "The MCP tools SkyQuery exposes."},
            {"name": "meta", "description": "API index, data sources, and status."},
        ],
        "paths": {
            "/api/v1": {
                "get": {
                    "operationId": "getApiIndex",
                    "summary": "API index",
                    "description": "Entry point listing every endpoint and related resource.",
                    "tags": ["meta"],
                    "responses": {"200": _ok("API index with links.", "ApiIndex"), **common_errors},
                }
            },
            "/api/v1/tools": {
                "get": {
                    "operationId": "listTools",
                    "summary": "List MCP tools",
                    "description": (
                        "Every MCP tool the SkyQuery server registers, with its description "
                        "and input JSON Schema. Use this to plan calls to a local SkyQuery "
                        "MCP server."
                    ),
                    "tags": ["tools"],
                    "responses": {"200": _ok("The tool catalog.", "ToolList"), **common_errors},
                }
            },
            "/api/v1/tools/{name}": {
                "get": {
                    "operationId": "getTool",
                    "summary": "Get one MCP tool",
                    "description": "One MCP tool by name, with its full input JSON Schema.",
                    "tags": ["tools"],
                    "parameters": [
                        {
                            "name": "name",
                            "in": "path",
                            "required": True,
                            "description": "The MCP tool name.",
                            "schema": {"type": "string", "enum": names},
                            "example": "get_ephemeris",
                        }
                    ],
                    "responses": {
                        "200": _ok("The requested tool.", "Tool"),
                        "404": _err("No tool with that name. The error lists valid names."),
                        **common_errors,
                    },
                }
            },
            "/api/v1/sources": {
                "get": {
                    "operationId": "listSources",
                    "summary": "List upstream data sources",
                    "description": (
                        "The public astronomy services SkyQuery wraps, and whether each "
                        "needs a free API key."
                    ),
                    "tags": ["meta"],
                    "responses": {"200": _ok("The data sources.", "SourceList"), **common_errors},
                }
            },
            "/api/v1/status": {
                "get": {
                    "operationId": "getStatus",
                    "summary": "Service status",
                    "description": "Health of this API and the current SkyQuery release.",
                    "tags": ["meta"],
                    "responses": {"200": _ok("Status and version.", "Status"), **common_errors},
                }
            },
        },
        "components": {
            "schemas": {
                "ApiIndex": {
                    "type": "object",
                    "required": ["name", "version", "description", "links"],
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "description": {"type": "string"},
                        "links": {
                            "type": "object",
                            "description": "Absolute URLs of related resources.",
                            "additionalProperties": {"type": "string", "format": "uri"},
                        },
                    },
                },
                "Tool": {
                    "type": "object",
                    "required": ["name", "summary", "description", "inputSchema", "returns", "url"],
                    "properties": {
                        "name": {"type": "string", "description": "MCP tool name."},
                        "summary": {"type": "string", "description": "One-line summary."},
                        "description": {"type": "string", "description": "Full guidance."},
                        "inputSchema": {
                            "type": "object",
                            "description": "JSON Schema for the tool's arguments.",
                        },
                        "returns": {"type": "string", "description": "Result model name."},
                        "url": {"type": "string", "format": "uri"},
                    },
                },
                "ToolList": {
                    "type": "object",
                    "required": ["version", "count", "tools"],
                    "properties": {
                        "version": {"type": "string", "description": "SkyQuery release."},
                        "count": {"type": "integer", "minimum": 0},
                        "tools": {"type": "array", "items": {"$ref": "#/components/schemas/Tool"}},
                    },
                },
                "Source": {
                    "type": "object",
                    "required": ["id", "name", "provider", "provides", "key_required", "url"],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "provider": {"type": "string"},
                        "provides": {"type": "string"},
                        "key_required": {"type": "boolean"},
                        "url": {"type": "string", "format": "uri"},
                    },
                },
                "SourceList": {
                    "type": "object",
                    "required": ["count", "sources"],
                    "properties": {
                        "count": {"type": "integer", "minimum": 0},
                        "sources": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Source"},
                        },
                    },
                },
                "Status": {
                    "type": "object",
                    "required": ["status", "version", "install", "repository"],
                    "properties": {
                        "status": {"type": "string", "enum": ["ok"]},
                        "version": {"type": "string"},
                        "install": {"type": "string", "description": "Install command."},
                        "repository": {"type": "string", "format": "uri"},
                    },
                },
                "Error": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {
                        "error": {
                            "type": "object",
                            "required": ["status", "code", "message", "hint", "docs"],
                            "properties": {
                                "status": {"type": "integer"},
                                "code": {
                                    "type": "string",
                                    "enum": [
                                        "not_found",
                                        "tool_not_found",
                                        "method_not_allowed",
                                        "internal_error",
                                    ],
                                },
                                "message": {"type": "string"},
                                "hint": {"type": "string", "description": "How to recover."},
                                "docs": {"type": "string", "format": "uri"},
                            },
                        }
                    },
                },
            }
        },
    }


def api_catalog() -> dict[str, Any]:
    """RFC 9727 API catalog, an RFC 9264 linkset."""
    return {
        "linkset": [
            {
                "anchor": f"{SITE_URL}/api/v1",
                "service-desc": [
                    {"href": f"{SITE_URL}/openapi.json", "type": "application/openapi+json"}
                ],
                "service-doc": [{"href": f"{SITE_URL}/developers", "type": "text/html"}],
                "status": [{"href": f"{SITE_URL}/api/v1/status", "type": "application/json"}],
            }
        ]
    }


# --------------------------------------------------------------------------- #
# Markdown -> HTML pages
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render_markdown(source: str) -> str:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    # Drop generator markers such as <!-- tools:start -->; raw HTML is disabled.
    tokens = md.parse(re.sub(r"^<!-- [a-z]+:(start|end) -->\n", "", source, flags=re.MULTILINE))
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag != "h1":
            tok.attrSet("id", _slug(tokens[i + 1].content.replace("`", "")))
    return md.renderer.render(tokens, md.options, {})


def _first_paragraph(source: str) -> str:
    for raw in source.split("\n\n"):
        block = raw.strip()
        if block and not block.startswith(("#", "-", "|", "`", ">", "<")):
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", " ".join(block.split()))
            text = text.replace("`", "").replace("**", "")
            return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + "..."
    return ""


NAV = """\
  <header class="nav" id="nav">
    <div class="wrap nav__inner">
      <a class="brand" href="/" aria-label="SkyQuery home">
        <span class="brand__mark" aria-hidden="true">✦</span>
        <span class="brand__name">SkyQuery</span>
      </a>
      <nav class="nav__links" aria-label="Primary">
        <a href="/#how">How it works</a>
        <a href="/#capabilities">Capabilities</a>
        <a href="/developers"{dev_current}>Developers</a>
        <a href="/#install">Install</a>
      </nav>
      <div class="nav__actions">
        <button id="theme" class="icon-btn" type="button" aria-label="Toggle color theme" title="Toggle theme">
          <span class="theme-sun" aria-hidden="true">☀</span>
          <span class="theme-moon" aria-hidden="true">☾</span>
        </button>
        <a class="btn btn--ghost" href="https://github.com/KarthikSubramanian07/skyquery" target="_blank" rel="noopener">
          <span aria-hidden="true">★</span> GitHub
        </a>
      </div>
    </div>
  </header>"""

FOOTER = """\
  <footer class="footer">
    <div class="wrap footer__inner">
      <div class="footer__brand">
        <a class="brand" href="/">
          <span class="brand__mark" aria-hidden="true">✦</span>
          <span class="brand__name">SkyQuery</span>
        </a>
        <p>The sky, queryable. Your questions, real data, one conversation.</p>
        <p class="footer__meta">MIT · v{version} · Runs on your machine</p>
      </div>
      <div class="footer__cols">
        <div>
          <h2>Product</h2>
          <a href="/#capabilities">Capabilities</a>
          <a href="/#sources">Sources</a>
          <a href="/#install">Install</a>
        </div>
        <div>
          <h2>Developers</h2>
          <a href="/developers">Developer portal</a>
          <a href="/openapi.json">OpenAPI spec</a>
          <a href="/llms.txt">llms.txt</a>
        </div>
        <div>
          <h2>Project</h2>
          <a href="/about">About</a>
          <a href="/contact">Contact</a>
          <a href="/privacy">Privacy</a>
        </div>
        <div>
          <h2>Community</h2>
          <a href="https://github.com/KarthikSubramanian07/skyquery" target="_blank" rel="noopener">GitHub</a>
          <a href="https://github.com/KarthikSubramanian07/skyquery/issues" target="_blank" rel="noopener">Issues</a>
          <a href="https://github.com/KarthikSubramanian07/skyquery/discussions" target="_blank" rel="noopener">Discussions</a>
        </div>
        <div>
          <h2>Support it</h2>
          <a class="coffee" href="https://buymeacoffee.com/winnerkarthik" target="_blank" rel="noopener">☕ Buy me a coffee</a>
        </div>
      </div>
    </div>
    <div class="wrap footer__credit">
      Built with astropy, astroquery, and astroplan. Data courtesy of SIMBAD (CDS), JPL, VizieR,
      Gaia/ESA, MAST/STScI, and NASA ADS. SkyQuery is independent and unaffiliated with any of them.
    </div>
  </footer>"""

PAGE = """\
<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
{canonical}  <link rel="alternate" type="text/markdown" href="/{slug}.md" />
  <meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)" />
  <meta name="theme-color" content="#F8F6F1" media="(prefers-color-scheme: light)" />
  <meta name="color-scheme" content="dark light" />
  <meta name="robots" content="{robots}" />

  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="SkyQuery" />
  <meta property="og:url" content="{url}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:image" content="{site}/og.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />

  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/styles.css" />
{jsonld}</head>
<body>
  <canvas id="sky" aria-hidden="true"></canvas>

  <a class="skip" href="#content">Skip to content</a>

{nav}

  <main id="content" class="page wrap">
    <article class="prose">
{body}    </article>
  </main>

{footer}

  <script src="/app.js" defer></script>
</body>
</html>
"""


def render_page(slug: str, source: str) -> str:
    meta = PAGES[slug]
    h1 = next(line[2:].strip() for line in source.splitlines() if line.startswith("# "))
    title = f"{h1} · SkyQuery" if "SkyQuery" not in h1 else h1
    description = _first_paragraph(source)
    url = f"{SITE_URL}/{slug}"
    is_404 = slug == "404"
    jsonld = ""
    if meta["schema"]:
        data = {
            "@context": "https://schema.org",
            "@type": meta["schema"],
            "name": h1,
            "description": description,
            "url": url,
            "isPartOf": {"@type": "WebSite", "name": "SkyQuery", "url": f"{SITE_URL}/"},
        }
        jsonld = (
            '\n  <script type="application/ld+json">\n'
            + textwrap.indent(json.dumps(data, indent=2, ensure_ascii=False), "  ")
            + "\n  </script>\n"
        )
    # Not re-indented: whitespace inside <pre> blocks is significant.
    body = render_markdown(source)
    return PAGE.format(
        title=html.escape(title),
        description=html.escape(description),
        canonical="" if is_404 else f'  <link rel="canonical" href="{url}" />\n',
        slug=slug,
        robots="noindex,follow" if is_404 else "index,follow,max-image-preview:large",
        url=url,
        site=SITE_URL,
        jsonld=jsonld,
        nav=NAV.format(dev_current=' aria-current="page"' if meta["nav"] == "developers" else ""),
        body=body,
        footer=FOOTER.format(version=__version__),
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
TOOLS_BLOCK = re.compile(r"(<!-- tools:start -->\n).*?(<!-- tools:end -->)", re.DOTALL)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build() -> dict[Path, str]:
    """Return every generated file's path and expected content."""
    tools = load_tools()
    out: dict[Path, str] = {}
    for name, payload in api_payloads(tools).items():
        out[SITE_DIR / "api" / "v1" / f"{name}.json"] = _json(payload)
    out[SITE_DIR / "openapi.json"] = _json(openapi_spec(tools))
    out[SITE_DIR / ".well-known" / "api-catalog"] = _json(api_catalog())

    dev_path = SITE_DIR / "developers.md"
    dev_source = TOOLS_BLOCK.sub(
        lambda m: m.group(1) + tool_reference_markdown(tools) + m.group(2),
        dev_path.read_text(encoding="utf-8"),
    )
    out[dev_path] = dev_source

    for slug in PAGES:
        md_path = SITE_DIR / f"{slug}.md"
        source = dev_source if md_path == dev_path else md_path.read_text(encoding="utf-8")
        out[SITE_DIR / f"{slug}.html"] = render_page(slug, source)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Fail if output is stale.")
    args = parser.parse_args(argv)

    stale: list[Path] = []
    for path, content in build().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    for path in stale:
        verb = "stale" if args.check else "wrote"
        print(f"{verb}: {path.relative_to(ROOT)}")
    if args.check and stale:
        print("Run `uv run python scripts/build_site.py` and commit the result.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

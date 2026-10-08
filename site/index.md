# SkyQuery: the sky, queryable

> SkyQuery is a free, open-source, local MCP server and CLI that lets AI assistants query real astronomy data: object lookups, asteroid and comet ephemerides, catalog cross-matches, and the literature. Every value comes back typed, unit-tagged, and carrying a citation. It runs entirely on your machine.

- Website: https://skyquery-mcp.pages.dev/
- Source code: https://github.com/KarthikSubramanian07/skyquery
- Developer portal: https://skyquery-mcp.pages.dev/developers
- Agent guide: https://skyquery-mcp.pages.dev/llms.txt
- OpenAPI spec: https://skyquery-mcp.pages.dev/openapi.json
- License: MIT. Free forever. No account, no telemetry.

## The problem

The data is public. The interfaces are not kind. To answer one ordinary question you touch a JPL prompt, a SIMBAD form, and ADS query syntax, each with its own units and conventions.

- Names must resolve to coordinates, coordinates to catalog rows, rows to papers, all by hand.
- Ask an LLM directly and it will happily invent an ephemeris that looks right and is wrong.
- Nothing comes back with the units, the reference frame, or a citation attached.

## How it works

Your assistant talks to SkyQuery over the Model Context Protocol (MCP). SkyQuery calls the public services (SIMBAD, JPL Horizons, VizieR, Gaia, ADS, and more) and returns one normalized schema with provenance.

- **One coordinate frame.** Every position lands in ICRS degrees with its epoch explicit.
- **Every value sourced.** Each field carries the service that produced it, the exact query, and the acknowledgment that service asks you to cite.
- **Deterministic, not guessed.** The assistant reads real results instead of inventing numbers.

## Capabilities

| Capability | MCP tool | Backed by |
| --- | --- | --- |
| Object intelligence | `resolve_object`, `object_dossier` | SIMBAD, NED, VizieR |
| Asteroid and comet ephemerides | `get_ephemeris`, `get_small_body`, `apophis_demo` | JPL Horizons, JPL SBDB |
| Catalog search and cross-match | `cone_search`, `crossmatch` | Gaia DR3, VizieR (2MASS, SDSS, and more) |
| Literature | `search_literature` | NASA ADS, arXiv |
| Unit-correct analysis | `convert_units`, `convert_frame`, `distance_from_parallax` | astropy |
| Wonder layer | `astronomy_picture_of_the_day` | NASA APOD |
| Provenance | `session_citations` | every source used in the session |

## Data sources

| Service | What | Access |
| --- | --- | --- |
| SIMBAD | Object identifiers, coordinates, and metadata | no key |
| JPL Horizons | Solar-system ephemerides and state vectors | no key |
| JPL SBDB | Small-body physical and orbital parameters | no key |
| Gaia, SDSS, 2MASS | Astrometry and photometry catalogs | no key |
| VizieR | Thousands of published catalogs | no key |
| NASA ADS | The astronomy literature | free key |
| arXiv | astro-ph preprints | no key |
| MAST | HST, JWST, TESS, and Kepler data products | no key |
| NASA Open APIs | Astronomy Picture of the Day | DEMO_KEY works |

SkyQuery is an independent open-source client. It is not affiliated with, or endorsed by, NASA, JPL, CDS/Strasbourg, STScI, ESA, or the Astropy project. It is a normalization and MCP layer on top of astroquery, which it credits plainly.

## Install

Requires Python 3.12 or newer.

```bash
uv tool install git+https://github.com/KarthikSubramanian07/skyquery
skyquery demo
```

Then add the stdio server to your MCP client config (for example Claude Desktop):

```json
{
  "mcpServers": {
    "skyquery": { "command": "skyquery-mcp" }
  }
}
```

Optional free keys unlock more: `skyquery login ads` and `skyquery login nasa`. They go straight to your OS keychain, never a file.

## The demo

"Where is Apophis, how big is it, and what's the latest paper?"

99942 Apophis is about 0.34 km across. On 2029-04-13 it passes 0.000257 AU from Earth, roughly 0.10 lunar distances, inside geostationary orbit. Source: JPL Horizons and JPL SBDB, frame ICRS.

## More

- [Developer portal](https://skyquery-mcp.pages.dev/developers): quickstart, MCP tool reference, CLI, and metadata API
- [About](https://skyquery-mcp.pages.dev/about)
- [Contact](https://skyquery-mcp.pages.dev/contact)
- [Privacy](https://skyquery-mcp.pages.dev/privacy)

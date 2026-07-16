<div align="center">

# ✦ SkyQuery

### The sky, queryable. Your questions, real data, one conversation.

A free, local, open-source **MCP server** that puts the working astronomer's whole toolkit,
object lookups, catalog cross-matches, ephemerides, literature, and observation planning,
behind one conversational interface. Point any AI assistant at it and ask the sky anything.
Runs entirely on your machine.

[![CI](https://github.com/KarthikSubramanian07/skyquery/actions/workflows/ci.yml/badge.svg)](https://github.com/KarthikSubramanian07/skyquery/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-4B8BBE)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-F6B44C)](LICENSE)
[![Typed](https://img.shields.io/badge/typed-pyright%20strict-5FE3D6)](pyproject.toml)
[![Built on astropy](https://img.shields.io/badge/built%20on-astropy%20%C2%B7%20astroquery-262D3D)](https://www.astropy.org/)

[**Website**](https://skyquery.pages.dev) · [Install](#install-in-under-five-minutes) · [The demo](#the-demo-that-sells-it) · [How it works](#how-it-works) · [Tools](#the-tool-surface)

</div>

---

## The honest version, first

SkyQuery is a **normalization and MCP layer on top of [astroquery](https://astroquery.readthedocs.io/)**,
which it credits loudly. It wraps free, publicly funded astronomy services (SIMBAD, JPL Horizons,
VizieR, Gaia, ADS, and more), honors their rate limits, and attaches a citation to every value it
returns. It is **local-first**: there is no SkyQuery server, nothing phones home, and your queries,
keys, and downloaded data never leave your machine except to talk to those public services directly.
You can read every line that touches the network.

It is **not** affiliated with NASA, JPL, CDS/Strasbourg, STScI, ESA, the Astropy project, or the
unrelated JHU catalog tool of a similar name. It is not proprietary-data access, not telescope
control, and not a hosted service. The answer to "can you host it for me" is "run it yourself, that
is the point."

## Why it exists

The data is public and abundant. The interfaces are fragmented and unforgiving. To answer one
ordinary question, *"where is comet Apophis tonight, how big is it, and what's the latest paper on
it?"*, you touch a JPL prompt, a SIMBAD form, and ADS query syntax, each with its own units and
conventions, and you end up copying numbers between tabs by hand. Ask an LLM directly and it will
happily invent an ephemeris that looks right and is wrong.

SkyQuery is the missing layer. It hands the assistant results that are **typed, unit-tagged, and
provenance-carrying** instead of raw floats, so the model can reason over real data without
guessing what "deg versus hourangle" or "J2000 versus ICRS" means.

## The demo that sells it

> **"Where is asteroid Apophis on its 2029 approach, how big is it, and what's a paper about it?"**

```console
$ skyquery demo
99942 Apophis (2004 MN4)
  size: 0.34 km   H: 19.09 mag
  closest approach: 2029-Apr-13 22:00  0.000257245 AU  (0.100 lunar distances)
  visual magnitude at approach: 4.257 mag
  paper: Radar and Optical Observations of Near-Earth Asteroid 99942 Apophis (2024)

99942 Apophis (2004 MN4) is about 0.34 km. On 2029-Apr-13 22:00 it passes 0.000257 AU
from Earth (0.10 lunar distances), inside geostationary orbit. Source: JPL Horizons and SBDB.
```

JPL Horizons, the Small-Body Database, and the literature, answered in one breath, with the units,
the frame, and the citation intact. That runs **offline against shipped fixtures**, so it works the
moment you install it.

## Install in under five minutes

```bash
# 1. Install (pick one)
uv tool install skyquery-mcp        # recommended
pipx install skyquery-mcp

# 2. Try it right now, offline, no keys
skyquery demo
skyquery resolve Vega
skyquery ephemeris "99942 Apophis" --start 2029-04-13 --stop 2029-04-14
```

Then point your assistant at it. Add one stdio block to your MCP client config (for example Claude
Desktop's `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "skyquery": { "command": "skyquery-mcp" }
  }
}
```

That is the whole integration. SIMBAD, VizieR, and JPL Horizons need **no key at all**, so it is
useful out of the box. Optional free keys unlock more, and go straight to your OS keychain, never a
file:

```bash
skyquery login ads     # free ADS researcher token, unlocks literature
skyquery login nasa    # free NASA key, unlocks the APOD "wonder" layer
```

See [SETUP.md](SETUP.md) for the exact steps and the `--live` flag.

## How it works

```
  Your assistant  ──MCP──▶  SkyQuery  ──▶  SIMBAD · Horizons · VizieR · Gaia · ADS · ...
                           ◀── normalized + provenance ──
```

Every service response is parsed into one small set of typed models, `Object`, `CatalogTable`,
`Ephemeris`, `Paper`, `ObservationWindow`, `DataProduct`, with values wrapped in astropy units and
coordinates carried in explicit frames and epochs. One source of truth feeds both the MCP tools and
the CLI.

- **One coordinate frame.** Everything lands in ICRS degrees with its epoch explicit.
- **Every value sourced.** Each field knows the service, the exact query, and the acknowledgment
  that service asks you to cite. Run `skyquery cite` for a ready-to-paste block.
- **Deterministic, not guessed.** The correctness-critical logic (unit and frame conversion,
  cross-match, provenance) is pure and separated from I/O, and tested against known reference values.
- **A good citizen by construction.** Human-scale rate limits and an on-disk cache are hard-coded
  floors, so a free service is never hammered.

## The tool surface

The MCP server exposes normalized, well-documented tools an assistant can chain (resolve a name, get
its ephemeris, find its papers):

| Domain | Tools |
| --- | --- |
| Object intelligence | `resolve_object`, `object_dossier` |
| Ephemerides & small bodies | `get_ephemeris`, `get_small_body`, `apophis_demo` |
| Catalogs & cross-match | `cone_search`, `crossmatch` |
| Literature | `search_literature` |
| Analysis (no network) | `convert_units`, `convert_frame`, `distance_from_parallax` |
| Wonder layer | `astronomy_picture_of_the_day` |
| Provenance | `session_citations` |

The CLI mirrors these: `resolve`, `ephemeris`, `small-body`, `cone`, `literature`, `convert`,
`frame`, `apod`, `demo`, `cite`, plus `setup`, `login`, `status`. Every command takes `--json` for
machine output and `--live` to leave replay mode and query the real services.

## For the auditor

You should be able to verify the trust model from readable code and passing tests:

```bash
git clone https://github.com/KarthikSubramanian07/skyquery && cd skyquery
uv pip install -e ".[dev]"
pytest        # green with zero network and zero keys
```

The suite proves the three things that matter: **numerical correctness** (unit and frame conversions
checked against astropy's own transforms and real captured reference values), **good citizenship**
(the rate-limiter throttles bursts and backs off), and **credential secrecy** (keys touch only the
keychain, and a test greps all log output to prove no token ever leaks). See
[DECISIONS.md](DECISIONS.md) for the architecture and the OSS ledger.

## Built on the shoulders of

[astropy](https://www.astropy.org/) · [astroquery](https://astroquery.readthedocs.io/) ·
[astroplan](https://astroplan.readthedocs.io/) · the [Model Context Protocol](https://modelcontextprotocol.io/)
SDK · and the free public services listed above. This tool is a thank-you note to all of them.

## Support

SkyQuery is free forever and costs nothing to run. If it saved you a late-night tab-juggling session,
you can [buy me a coffee](https://buymeacoffee.com/winnerkarthik) ☕.

## License

[MIT](LICENSE). Go build something with the sky.

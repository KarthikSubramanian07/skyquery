# About SkyQuery

SkyQuery is a free, open-source Model Context Protocol (MCP) server and command-line tool for astronomy. It gives AI assistants and the people who use them a single, honest interface to the public astronomy services that working astronomers rely on every day: SIMBAD, JPL Horizons, the JPL Small-Body Database, VizieR, Gaia, NASA ADS, arXiv, and MAST.

## Why it exists

The data is public and abundant, but the interfaces are fragmented and unforgiving. To answer one ordinary question, such as where comet Apophis will be tonight, how big it is, and what the latest paper about it says, you touch three different services, each with its own units, coordinate conventions, and query syntax. Ask a language model directly and it may invent an ephemeris that looks right and is wrong.

SkyQuery is the missing layer. It hands the assistant results that are typed, unit-tagged, and carry their provenance, so the model can reason over real data instead of guessing.

## What it is, and what it is not

- **It is local-first.** SkyQuery runs on your own computer. There is no SkyQuery server, no account, and no telemetry. Your queries go directly from your machine to the public services.
- **It is open source.** The full source is on [GitHub](https://github.com/KarthikSubramanian07/skyquery) under the MIT license.
- **It builds on astroquery.** SkyQuery is a normalization and MCP layer on top of [astroquery](https://astroquery.readthedocs.io/) and [astropy](https://www.astropy.org/), and credits them loudly.
- **It is independent.** SkyQuery is not affiliated with, or endorsed by, NASA, JPL, CDS/Strasbourg, STScI, ESA, the Astropy project, or the unrelated JHU catalog tool of a similar name.
- **It is not a hosted data service.** It does not proxy, resell, or store astronomy data on a server.

## Who builds it

SkyQuery is created and maintained by [Karthik Subramanian](https://github.com/KarthikSubramanian07) as an independent open-source project. Contributions, bug reports, and ideas are welcome through [GitHub issues](https://github.com/KarthikSubramanian07/skyquery/issues) and [discussions](https://github.com/KarthikSubramanian07/skyquery/discussions).

## Acknowledgments

SkyQuery depends on publicly funded infrastructure. Data courtesy of SIMBAD (CDS, Strasbourg), the JPL Solar System Dynamics group, VizieR, ESA Gaia, MAST at STScI, NASA ADS, and arXiv. Every SkyQuery result carries the acknowledgment each service asks you to cite, and the `session_citations` tool collects them for you.

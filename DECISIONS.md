# DECISIONS

Architecture, trade-offs, and the honest cost model. Read this before trusting
SkyQuery's numbers or its network path.

## The overrides worth calling out

- **Local-only, no hosted infrastructure of any kind.** SkyQuery is a stdio MCP
  server plus a CLI. There is no web dashboard, no backend, and no telemetry. The
  usual "$0 on a cloud stack" reasoning is replaced by "$0 because everything runs
  on your machine." State (a single SQLite file), the on-disk cache, downloaded
  data, and credentials (OS keychain) all live locally. Nothing leaves the machine
  except direct calls to the public astronomy services.
- **The marketing site is the one exception**, and it is deliberately just a static
  page (`site/`) with no data surface, deployed to Cloudflare Pages at
  `skyquery-mcp.pages.dev`. It never touches user queries or keys; it exists to explain
  the tool and show the demo.

## Cost model

$0 at any scale, by construction. Each user runs their own local copy, brings their
own free keys, and hits free public APIs. There is no central server, so the
marginal cost of one more user is exactly zero. Every wrapped service (SIMBAD,
VizieR, Horizons, Gaia, ADS, arXiv, NASA, MAST) is free. The only optional cost is
the user's own AI-assistant subscription driving the MCP layer, which is external
and optional; the CLI works with no AI at all.

## The deterministic core, and the one seam

The correctness-critical logic is pure and lives in `skyquery.core` and
`skyquery.models`: unit/frame/epoch conversion, positional cross-match, citation
assembly, the rate-limiter, and the on-disk cache. None of it touches the network,
so all of it is hermetically testable.

The only external seam is **per-data-source**, in `skyquery.sources`. Every adapter
subclasses `DataSource` and implements exactly two things: `_live_fetch` (the
network call, returning a JSON-serializable raw payload) and a normalizer (raw
payload to typed model). The base class owns everything that must behave identically
for every source: replay/offline routing, caching, the rate-limiter with backoff,
and provenance stamping. If a service changes its API, exactly one adapter's
`_live_fetch` changes and nothing else moves.

## Replay stubs as the default

`Settings.replay` defaults to `True`. Adapters serve recorded fixtures
(`src/skyquery/_fixtures`) rather than the network unless you pass `--live` or set
`SKYQUERY_REPLAY=0`. This makes the default experience deterministic and offline: a
fresh install runs the Apophis demo and the full test suite with zero network and
zero keys. The fixtures for Horizons, SBDB, SIMBAD, and Gaia are derived from **real
recorded responses** (astropy 8.0.1 / astroquery 0.4.11); the ADS/arXiv/NASA samples
are small representative snapshots, clearly marked as such, because those are
live-search endpoints for which any fixture is inherently a point-in-time snapshot.
Regenerate them with `python scripts/make_fixtures.py <capture_dir>`.

## Correctness oracle

Unit conversions, frame transforms (ICRS/FK5/Galactic/AltAz), epoch propagation, and
cross-match are tested against **external ground truth**: astropy's own tested
transforms and published reference values captured from a real run (see
`tests/test_convert.py`). We do not check our math against our own re-derived math.
Nasty cases are covered on purpose: RA wrap-around at 0/360, Dec at the poles,
hourangle versus degree, J2000 versus ICRS, and proper-motion epoch propagation.

## Good citizenship and credential secrecy, both provable

- `tests/test_ratelimit.py` proves the rate-limiter throttles bursts (both a
  minimum spacing and a sliding window) and that backoff grows exponentially and is
  capped. The clock and sleep are injected, so tests are deterministic.
- `tests/test_credentials.py` proves credentials touch only the keychain (the real
  keychain is never hit in tests; a fake is injected), that a missing-key error
  never contains the secret value, and that a burst of log lines mentioning a token
  greps clean. Redaction lives in `skyquery.logging`.

## Type checking

`pyright` runs in strict mode. astropy and astroquery ship incomplete inline type
information, so strict mode raises false positives at every call into them
(`SkyCoord`/`Quantity` attribute access, `Table` indexing, astroquery return
shapes). We keep strict mode for our own logic and disable only the specific
diagnostics that fire purely at that untyped third-party boundary
(`reportAttributeAccessIssue`, `reportOptionalMemberAccess`, `reportArgumentType`,
`reportCallIssue`, `reportReturnType`, `reportIndexIssue`). Everything else,
including unused symbols, redefinitions, and general type errors in our code, stays
strict and passes clean.

## Adapters: real service, auth, and cost

Every wrapped service is free. SkyQuery itself has no per-call cost.

| Adapter | Real service | Auth |
| --- | --- | --- |
| `simbad` | SIMBAD (CDS) | none |
| `ned` | NASA/IPAC Extragalactic Database | none |
| `vizier` | VizieR (CDS) | none |
| `gaia` | Gaia DR3 (ESA/DPAC) | none |
| `horizons` | JPL Horizons | none |
| `sbdb` | JPL Small-Body Database | none |
| `mast` | MAST (STScI) | none |
| `arxiv` | arXiv.org | none |
| `nasa` | NASA Open APIs (APOD) | free key, or DEMO_KEY |
| `ads` | NASA ADS | free researcher token |
| `vo` | generic IVOA TAP/ADQL fallback | none |
| `planning` | astroplan (local calculation) | none |

## OSS and licensing ledger

Everything SkyQuery depends on is permissively licensed. Nothing is copyleft.

| Dependency | License | Why it is safe |
| --- | --- | --- |
| astropy | BSD-3-Clause | permissive, industry standard for astronomy |
| astroquery | BSD-3-Clause | permissive; the client we normalize on top of |
| astroplan | BSD-3-Clause | permissive, Astropy-affiliated |
| scipy | BSD-3-Clause | permissive; used by astropy's KD-tree matcher |
| pyvo | BSD-3-Clause | permissive; VO TAP fallback |
| mcp (Python SDK) | MIT | permissive |
| pydantic | MIT | permissive |
| httpx | BSD-3-Clause | permissive |
| typer / rich | MIT | permissive |
| keyring | MIT / PSF | permissive |
| platformdirs | MIT | permissive |

SkyQuery itself is MIT. A security-minded stranger can read the whole network path
and verify that nothing exfiltrates.

## What was deliberately left out

Proprietary or embargoed data, telescope control, simulation or theory engines, and
any hosted or multi-tenant deployment. Those either break the local-only trust model
or are out of scope on purpose.

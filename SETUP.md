# SETUP

The shortest path from zero to asking the sky a question. Most of this is optional;
SkyQuery works offline with no keys the moment it is installed.

## 1. Install

```bash
uv tool install skyquery-mcp        # recommended
# or: pipx install skyquery-mcp
# or, from a clone:  uv tool install .
```

Requires Python 3.12 or newer. `uv` handles the interpreter for you.

## 2. Prove it works, offline

```bash
skyquery demo            # the Apophis close-approach demo, from shipped fixtures
skyquery resolve Vega    # object intelligence
skyquery status          # shows mode and which optional keys are set
```

No network and no keys are needed for any of the above. They run against recorded
fixtures in replay mode, which is the default.

## 3. (Optional) create your local state directory

```bash
skyquery setup
```

This creates a home directory (default `~/.local/share/skyquery` or your platform
equivalent, override with `SKYQUERY_HOME`) holding the on-disk cache, the download
folder, and the SQLite query/citation log. Everything stays on your machine.

## 4. (Optional) add free API keys

Two services want a free key. Keys are written **only to your OS keychain** via
`keyring`, never to a file, never to the repo, never to a log line.

```bash
skyquery login ads      # get a token at https://ui.adsabs.harvard.edu/user/settings/token
skyquery login nasa     # get a key at https://api.nasa.gov/ (or skip; DEMO_KEY works)
```

Remove one at any time with `skyquery logout ads`.

SIMBAD, VizieR, NED, Gaia, JPL Horizons, JPL SBDB, arXiv, and MAST need **no key**.

## 5. Go live (leave replay mode)

By default SkyQuery serves shipped fixtures so it is deterministic and offline. To
query the real services, pass `--live` (or set `SKYQUERY_REPLAY=0`):

```bash
skyquery --live resolve "Proxima Centauri"
skyquery --live ephemeris Ceres --start 2026-01-01 --stop 2026-02-01 --step 5d
```

Live mode throttles every call and caches results on disk, so repeated questions do
not re-hit a free service.

## 6. Connect your AI assistant

Add one stdio server to your MCP client's config. For Claude Desktop, edit
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "skyquery": {
      "command": "skyquery-mcp"
    }
  }
}
```

To let the assistant query live services rather than fixtures, add an env block:

```json
{
  "mcpServers": {
    "skyquery": {
      "command": "skyquery-mcp",
      "env": { "SKYQUERY_REPLAY": "0" }
    }
  }
}
```

Restart your assistant. Ask it: *"Where is asteroid Apophis on its 2029 approach, how
big is it, and what is a recent paper about it?"*

## Deploying the landing page (maintainers only)

The marketing site in `site/` deploys to `https://skyquery-mcp.pages.dev` via Cloudflare
Pages using Wrangler. There is no CI deploy job and no repository secret to manage: a
maintainer publishes with a single command after logging in once with
`npx wrangler login`.

```bash
npx wrangler pages deploy site --project-name=skyquery-mcp --branch=main
```

Run it from the **repository root**: Wrangler bundles the `functions/` directory
(Markdown content negotiation, real 404s, and the JSON metadata API) only when it
sits next to the deployed `site/` folder.

### Agent-facing files

Most of what agents read is generated, so it cannot drift from the code:

```bash
uv run python scripts/build_site.py          # regenerate after changing a tool or page
uv run python scripts/build_site.py --check  # CI fails if output is stale
npm test                                     # edge function unit tests (Node 22+)
npm run dev                                  # serve site + functions locally on :8788
bash scripts/smoke_site.sh                   # end-to-end checks (pass a URL for prod)
```

| Source | Generates / serves |
| --- | --- |
| MCP server tool registry | `site/api/v1/tools.json`, `site/openapi.json`, the tool reference in `site/developers.md` |
| `site/{about,contact,privacy,developers,404}.md` | the matching `.html` pages, and the Markdown served for `Accept: text/markdown` |
| `site/index.md` (hand-written) | the homepage's Markdown twin; keep it in step with `site/index.html` |
| `functions/` + `edge/agent.js` | content negotiation, Markdown 404s, `/api/v1/*` JSON and JSON errors |

Wrangler authenticates through your local Cloudflare login, so nothing leaves your
machine and no long-lived API token is stored anywhere.

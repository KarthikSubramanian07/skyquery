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

The marketing site in `site/` deploys to `https://skyquery.pages.dev` via Cloudflare
Pages. Automatic deploys on push need two GitHub repo secrets:

1. `CLOUDFLARE_API_TOKEN`, a token with the **Cloudflare Pages: Edit** permission
   (create it at https://dash.cloudflare.com/profile/api-tokens).
2. `CLOUDFLARE_ACCOUNT_ID`, your account id.

Add them under the repo's *Settings → Secrets and variables → Actions*. The
`.github/workflows/deploy-pages.yml` workflow then publishes `site/` on every push
that touches it. To deploy manually:

```bash
npx wrangler pages deploy site --project-name=skyquery
```

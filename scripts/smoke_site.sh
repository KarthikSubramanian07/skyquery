#!/usr/bin/env bash
# End-to-end checks for the agent-facing behavior of the SkyQuery site.
# Usage: scripts/smoke_site.sh [base-url]   (default http://localhost:8788)
# Run against `npx wrangler@4 pages dev site --port 8788` or production.
set -uo pipefail

BASE="${1:-http://localhost:8788}"
fail=0
pass() { printf '  ok    %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }

# fetch <accept> <path> -> sets STATUS, CTYPE, VARY, BODY
fetch() {
  local hdr body
  hdr=$(mktemp) body=$(mktemp)
  STATUS=$(curl -sS -L -o "$body" -D "$hdr" -w '%{http_code}' -H "Accept: $1" "$BASE$2")
  CTYPE=$(grep -i '^content-type:' "$hdr" | tail -1 | cut -d' ' -f2- | tr -d '\r')
  VARY=$(grep -i '^vary:' "$hdr" | tail -1 | cut -d' ' -f2- | tr -d '\r')
  BODY=$(cat "$body")
  rm -f "$hdr" "$body"
}

expect() { # <label> <condition...>
  local label=$1; shift
  if "$@"; then pass "$label"; else bad "$label (status=$STATUS type=$CTYPE vary=$VARY)"; fi
}

echo "Smoke testing $BASE"

fetch 'text/markdown' /
expect "homepage markdown: 200 text/markdown + Vary: Accept" \
  test "$STATUS" = 200 -a "${CTYPE%%;*}" = text/markdown
expect "homepage markdown: Vary includes Accept" grep -qi accept <<<"$VARY"
expect "homepage markdown: body starts with H1" grep -q '^# SkyQuery' <<<"$BODY"

fetch 'text/html' /
expect "homepage html: 200 text/html" test "$STATUS" = 200 -a "${CTYPE%%;*}" = text/html
expect "homepage html: Vary includes Accept" grep -qi accept <<<"$VARY"
expect "homepage html: JSON-LD present" grep -q 'application/ld+json' <<<"$BODY"

fetch 'text/markdown' /some-path-that-does-not-exist
expect "unknown path markdown: 404 text/markdown" test "$STATUS" = 404 -a "${CTYPE%%;*}" = text/markdown
expect "unknown path markdown: points to llms.txt" grep -q 'llms.txt' <<<"$BODY"

fetch 'text/html' /some-path-that-does-not-exist
expect "unknown path html: 404" test "$STATUS" = 404

for page in developers about contact privacy; do
  fetch 'text/html' "/$page"
  expect "/$page html: 200" test "$STATUS" = 200 -a "${CTYPE%%;*}" = text/html
  fetch 'text/markdown' "/$page"
  expect "/$page markdown: 200" test "$STATUS" = 200 -a "${CTYPE%%;*}" = text/markdown
done

fetch '*/*' /llms.txt
expect "llms.txt: 200 text/plain" test "$STATUS" = 200 -a "${CTYPE%%;*}" = text/plain
fetch '*/*' /sitemap.xml
expect "sitemap.xml: 200 with urlset" grep -q '<urlset' <<<"$BODY"
fetch '*/*' /robots.txt
expect "robots.txt: references sitemap" grep -q 'Sitemap:' <<<"$BODY"
fetch '*/*' /openapi.json
expect "openapi.json: 200 JSON 3.1" grep -q '"openapi": "3.1' <<<"$BODY"
fetch '*/*' /.well-known/api-catalog
expect "api-catalog: linkset+json" test "${CTYPE%%;*}" = application/linkset+json

for path in /api/v1 /api/v1/tools /api/v1/tools/get_ephemeris /api/v1/sources /api/v1/status; do
  fetch 'application/json' "$path"
  expect "$path: 200 application/json" test "$STATUS" = 200 -a "${CTYPE%%;*}" = application/json
done

fetch 'application/json' /api/v1/tools/not_a_tool
expect "unknown tool: JSON 404 tool_not_found" grep -q '"tool_not_found"' <<<"$BODY"
fetch 'application/json' /api/does-not-exist
expect "unknown endpoint: 404 application/json" test "$STATUS" = 404 -a "${CTYPE%%;*}" = application/json

STATUS=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/tools")
expect "POST to API: 405" test "$STATUS" = 405

if [ "$fail" = 0 ]; then echo "All checks passed."; else echo "Some checks failed."; fi
exit "$fail"

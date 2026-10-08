// Edge logic for the SkyQuery site, shared by the Pages Functions in /functions.
// Pure functions over Request/Response so they run unchanged under Node's test
// runner. Pages does not apply `_headers` to Function responses, so every
// response built here carries its own security headers.

export const SITE_URL = "https://skyquery-mcp.pages.dev";
export const DOCS_URL = `${SITE_URL}/developers#metadata-api`;

export const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Frame-Options": "DENY",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
};

const DISCOVERY_LINKS = [
  '</llms.txt>; rel="describedby"; type="text/plain"',
  '</openapi.json>; rel="service-desc"; type="application/openapi+json"',
  '</developers>; rel="service-doc"; type="text/html"',
];

/* ------------------------------------------------------------------------- */
/* Accept negotiation (RFC 9110 section 12.5.1)                               */
/* ------------------------------------------------------------------------- */

/** Parse an Accept header into [{type, q, specificity, order}]. */
export function parseAccept(header) {
  if (!header) return [];
  return header.split(",").flatMap((part, order) => {
    const [range, ...params] = part.trim().split(";").map((s) => s.trim());
    if (!range || !range.includes("/")) return [];
    let q = 1;
    for (const p of params) {
      const [k, v] = p.split("=").map((s) => s.trim());
      if (k.toLowerCase() === "q") {
        const n = Number(v);
        q = Number.isFinite(n) ? Math.min(Math.max(n, 0), 1) : 0;
      }
    }
    const type = range.toLowerCase();
    const specificity = type === "*/*" ? 0 : type.endsWith("/*") ? 1 : 2;
    return [{ type, q, specificity, order }];
  });
}

/** The q-value and position the client gave `mediaType`, using the most specific match. */
function scoreFor(ranges, mediaType) {
  const [major] = mediaType.split("/");
  let best = null;
  for (const r of ranges) {
    const matches = r.type === mediaType || r.type === `${major}/*` || r.type === "*/*";
    if (matches && (!best || r.specificity > best.specificity)) best = r;
  }
  return best ? { q: best.q, specificity: best.specificity, order: best.order } : { q: 0, specificity: -1, order: Infinity };
}

/**
 * True when the client prefers Markdown over HTML. Markdown wins on a higher
 * q-value, then on a more specific match (`text/markdown` beats `*\/*`), then on
 * listing order. A missing Accept header means HTML, for browsers and crawlers.
 */
export function prefersMarkdown(acceptHeader) {
  const ranges = parseAccept(acceptHeader);
  const md = scoreFor(ranges, "text/markdown");
  if (md.q <= 0) return false;
  const html = scoreFor(ranges, "text/html");
  if (md.q !== html.q) return md.q > html.q;
  if (md.specificity !== html.specificity) return md.specificity > html.specificity;
  return md.order < html.order;
}

/* ------------------------------------------------------------------------- */
/* Pages and Markdown twins                                                   */
/* ------------------------------------------------------------------------- */

/**
 * Map a page URL path to its Markdown twin, or null for non-page paths
 * (assets, API, well-known files). `/` -> `/index.md`, `/about/` -> `/about.md`.
 */
export function markdownPathFor(pathname) {
  if (pathname.startsWith("/api/") || pathname === "/api" || pathname.startsWith("/.well-known/")) return null;
  let path = pathname.replace(/\/+$/, "");
  if (path === "" || path === "/index" || path === "/index.html") return "/index.md";
  if (path.endsWith(".html")) path = path.slice(0, -5);
  const last = path.slice(path.lastIndexOf("/") + 1);
  if (last.includes(".")) return null; // a file with another extension
  return `${path}.md`;
}

function appendVary(headers, value) {
  const current = headers.get("Vary");
  if (!current) return headers.set("Vary", value);
  const parts = current.split(",").map((s) => s.trim().toLowerCase());
  if (!parts.includes(value.toLowerCase())) headers.set("Vary", `${current}, ${value}`);
}

async function markdownResponse(request, assetResponse, status) {
  const headers = new Headers({
    ...SECURITY_HEADERS,
    "Content-Type": "text/markdown; charset=utf-8",
    "Cache-Control": "public, max-age=300",
    Vary: "Accept",
    Link: DISCOVERY_LINKS.join(", "),
  });
  if (status === 404) headers.set("Cache-Control", "no-store");
  const body = request.method === "HEAD" ? null : await assetResponse.text();
  return new Response(body, { status, headers });
}

async function fetchAsset(env, request, path) {
  return env.ASSETS.fetch(new Request(new URL(path, request.url), { method: "GET" }));
}

/**
 * Site-wide middleware: Markdown content negotiation for pages, and Markdown
 * 404 bodies for agents. `next` serves the static asset (or the 404.html page).
 */
export async function handlePage(request, env, next) {
  if (request.method !== "GET" && request.method !== "HEAD") return next();

  const url = new URL(request.url);
  const mdPath = markdownPathFor(url.pathname);
  if (!mdPath) return next();

  const wantsMarkdown = prefersMarkdown(request.headers.get("Accept"));
  if (wantsMarkdown) {
    const asset = await fetchAsset(env, request, mdPath);
    if (asset.status === 200) return markdownResponse(request, asset, 200);
    return markdownResponse(request, await fetchAsset(env, request, "/404.md"), 404);
  }

  const response = await next();
  const headers = new Headers(response.headers);
  appendVary(headers, "Accept");
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) if (!headers.has(k)) headers.set(k, v);
  if (response.status === 200 && (headers.get("Content-Type") || "").startsWith("text/html")) {
    headers.append("Link", `<${mdPath}>; rel="alternate"; type="text/markdown"`);
    headers.append("Link", DISCOVERY_LINKS.join(", "));
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

/* ------------------------------------------------------------------------- */
/* Metadata API                                                               */
/* ------------------------------------------------------------------------- */

const API_ALLOW = "GET, HEAD, OPTIONS";
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": API_ALLOW,
  "Access-Control-Allow-Headers": "Accept, Content-Type",
  "Access-Control-Max-Age": "86400",
};

export function jsonResponse(request, data, status = 200, extra = {}) {
  const headers = new Headers({
    ...SECURITY_HEADERS,
    ...CORS,
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": status === 200 ? "public, max-age=300" : "no-store",
    ...extra,
  });
  const body = request.method === "HEAD" ? null : JSON.stringify(data, null, 2) + "\n";
  return new Response(body, { status, headers });
}

export function errorResponse(request, status, code, message, hint, extra = {}) {
  return jsonResponse(request, { error: { status, code, message, hint, docs: DOCS_URL } }, status, extra);
}

// Static payloads generated by scripts/build_site.py, served from the asset store.
const API_ROUTES = {
  "/api/v1": "/api/v1/index.json",
  "/api/v1/tools": "/api/v1/tools.json",
  "/api/v1/sources": "/api/v1/sources.json",
  "/api/v1/status": "/api/v1/status.json",
};

async function loadJson(env, request, path) {
  const res = await fetchAsset(env, request, path);
  if (res.status !== 200) throw new Error(`asset ${path} returned ${res.status}`);
  return res.json();
}

export async function handleApi(request, env) {
  try {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...SECURITY_HEADERS, ...CORS } });
    if (request.method !== "GET" && request.method !== "HEAD") {
      return errorResponse(
        request, 405, "method_not_allowed",
        `${request.method} is not supported. This API is read-only.`,
        `Use one of: ${API_ALLOW}.`,
        { Allow: API_ALLOW },
      );
    }

    const url = new URL(request.url);
    let path = url.pathname.replace(/\/+$/, "").replace(/\.json$/, "");
    if (path === "/api") path = "/api/v1";

    if (API_ROUTES[path]) return jsonResponse(request, await loadJson(env, request, API_ROUTES[path]));

    const tool = path.match(/^\/api\/v1\/tools\/([^/]+)$/);
    if (tool) {
      const name = decodeURIComponent(tool[1]);
      const { tools } = await loadJson(env, request, "/api/v1/tools.json");
      const found = tools.find((t) => t.name === name);
      if (found) return jsonResponse(request, found);
      return errorResponse(
        request, 404, "tool_not_found",
        `No MCP tool named '${name}'.`,
        `List valid tool names at /api/v1/tools. Valid names: ${tools.map((t) => t.name).join(", ")}.`,
      );
    }

    return errorResponse(
      request, 404, "not_found",
      `No API endpoint at ${url.pathname}.`,
      "Start at /api/v1 for the endpoint index, or read /openapi.json for the full contract.",
    );
  } catch (err) {
    console.error("api error", err);
    return errorResponse(
      request, 500, "internal_error",
      "The metadata API failed to load its data.",
      "Retry shortly. If it persists, open an issue at https://github.com/KarthikSubramanian07/skyquery/issues.",
    );
  }
}

// Unit tests for the Pages Functions logic in edge/agent.js.
// Run with `node --test tests/edge/`. The fake ASSETS binding serves the real
// files in site/, and the fake `next` mimics Pages: the asset or 404.html.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { parseAccept, prefersMarkdown, markdownPathFor, handlePage, handleApi } from "../../edge/agent.js";
import { onRequest as middleware } from "../../functions/_middleware.js";

const SITE = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const TYPES = { ".md": "text/markdown; charset=utf-8", ".json": "application/json", ".html": "text/html; charset=utf-8" };

async function serveFile(pathname) {
  const candidates = pathname === "/" ? ["/index.html"] : [pathname, `${pathname}.html`];
  for (const c of candidates) {
    try {
      const body = await readFile(path.join(SITE, c));
      return new Response(body, { status: 200, headers: { "Content-Type": TYPES[path.extname(c)] || "application/octet-stream" } });
    } catch { /* try next */ }
  }
  return new Response(await readFile(path.join(SITE, "404.html")), { status: 404, headers: { "Content-Type": TYPES[".html"] } });
}

const env = { ASSETS: { fetch: (req) => serveFile(new URL(req.url).pathname) } };
const nextFor = (request) => () => serveFile(new URL(request.url).pathname);
const req = (p, init = {}) => new Request(`https://skyquery-mcp.pages.dev${p}`, init);
const page = (p, accept, method = "GET") => {
  const r = req(p, { method, headers: accept ? { Accept: accept } : {} });
  return handlePage(r, env, nextFor(r));
};

describe("parseAccept", () => {
  test("parses q-values, specificity, and order", () => {
    assert.deepEqual(parseAccept("text/markdown;q=0.9, */*"), [
      { type: "text/markdown", q: 0.9, specificity: 2, order: 0 },
      { type: "*/*", q: 1, specificity: 0, order: 1 },
    ]);
  });
  test("ignores garbage and clamps q", () => {
    assert.deepEqual(parseAccept("nonsense, text/html;q=7"), [{ type: "text/html", q: 1, specificity: 2, order: 1 }]);
    assert.deepEqual(parseAccept(""), []);
  });
});

describe("prefersMarkdown", () => {
  const cases = [
    ["text/markdown", true],
    ["text/markdown, text/html;q=0.9", true],
    ["text/html, text/markdown;q=0.5", false],
    ["text/markdown, text/html", true],
    ["text/html, text/markdown", false],
    ["text/markdown, */*;q=0.8", true],
    ["text/plain, text/markdown, */*", true],
    ["text/*", false],
    ["*/*", false],
    ["text/markdown;q=0", false],
    [null, false],
    ["text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", false],
  ];
  for (const [accept, expected] of cases) {
    test(`${accept} -> ${expected ? "markdown" : "html"}`, () => assert.equal(prefersMarkdown(accept), expected));
  }
});

describe("markdownPathFor", () => {
  test("maps pages to their Markdown twins", () => {
    assert.equal(markdownPathFor("/"), "/index.md");
    assert.equal(markdownPathFor("/index.html"), "/index.md");
    assert.equal(markdownPathFor("/about"), "/about.md");
    assert.equal(markdownPathFor("/about/"), "/about.md");
    assert.equal(markdownPathFor("/privacy.html"), "/privacy.md");
  });
  test("skips assets, the API, and well-known files", () => {
    for (const p of ["/styles.css", "/og.png", "/api/v1/tools", "/api", "/.well-known/api-catalog", "/llms.txt"]) {
      assert.equal(markdownPathFor(p), null, p);
    }
  });
});

describe("handlePage", () => {
  test("homepage serves Markdown with Vary: Accept when asked", async () => {
    const res = await page("/", "text/markdown");
    assert.equal(res.status, 200);
    assert.equal(res.headers.get("Content-Type"), "text/markdown; charset=utf-8");
    assert.match(res.headers.get("Vary"), /Accept/);
    const body = await res.text();
    assert.match(body, /^# SkyQuery/);
    assert.ok(body.length > 500);
  });

  test("homepage serves HTML with Vary: Accept to browsers", async () => {
    const res = await page("/", "text/html,application/xhtml+xml,*/*;q=0.8");
    assert.equal(res.status, 200);
    assert.match(res.headers.get("Content-Type"), /^text\/html/);
    assert.match(res.headers.get("Vary"), /Accept/);
    assert.match(res.headers.get("Link"), /<\/index\.md>; rel="alternate"; type="text\/markdown"/);
    assert.match(await res.text(), /<h1 class="hero__title">/);
  });

  test("no Accept header means HTML", async () => {
    const res = await page("/about");
    assert.match(res.headers.get("Content-Type"), /^text\/html/);
  });

  for (const slug of ["about", "contact", "privacy", "developers"]) {
    test(`/${slug} negotiates Markdown`, async () => {
      const res = await page(`/${slug}`, "text/markdown");
      assert.equal(res.status, 200);
      assert.match(await res.text(), /^# /);
    });
  }

  test("unknown path returns a real 404 with a Markdown body", async () => {
    const res = await page("/some-path-that-does-not-exist", "text/markdown");
    assert.equal(res.status, 404);
    assert.equal(res.headers.get("Content-Type"), "text/markdown; charset=utf-8");
    const body = await res.text();
    assert.ok(body.length >= 20);
    assert.match(body, /llms\.txt/);
    assert.match(body, /sitemap\.xml/);
  });

  test("unknown path returns a real 404 HTML page to browsers", async () => {
    const res = await page("/nope", "text/html");
    assert.equal(res.status, 404);
    assert.match(res.headers.get("Vary"), /Accept/);
    assert.match(await res.text(), /404: page not found/);
  });

  test("HEAD returns headers without a body", async () => {
    const res = await page("/", "text/markdown", "HEAD");
    assert.equal(res.status, 200);
    assert.equal(res.headers.get("Content-Type"), "text/markdown; charset=utf-8");
    assert.equal(await res.text(), "");
  });

  test("security headers are set on generated responses", async () => {
    const res = await page("/", "text/markdown");
    assert.equal(res.headers.get("X-Content-Type-Options"), "nosniff");
    assert.equal(res.headers.get("X-Frame-Options"), "DENY");
  });

  test("non-page assets pass straight through", async () => {
    let called = false;
    const r = req("/styles.css", { headers: { Accept: "text/markdown" } });
    await handlePage(r, env, () => { called = true; return new Response("css"); });
    assert.ok(called);
  });
});

describe("middleware", () => {
  test("hands /api requests to the API route", async () => {
    let called = false;
    await middleware({ request: req("/api/v1/tools"), env, next: () => { called = true; return new Response("{}"); } });
    assert.ok(called);
  });
});

describe("handleApi", () => {
  const api = (p, method = "GET") => handleApi(req(p, { method }), env);

  test("index lists links", async () => {
    for (const p of ["/api", "/api/v1", "/api/v1/"]) {
      const res = await api(p);
      assert.equal(res.status, 200, p);
      assert.equal(res.headers.get("Content-Type"), "application/json; charset=utf-8");
      assert.ok((await res.json()).links.openapi);
    }
  });

  test("tools list matches the generated catalog", async () => {
    const res = await api("/api/v1/tools");
    const data = await res.json();
    assert.equal(data.count, data.tools.length);
    assert.ok(data.tools.some((t) => t.name === "get_ephemeris"));
    assert.equal(res.headers.get("Access-Control-Allow-Origin"), "*");
  });

  test(".json suffix is accepted", async () => {
    assert.equal((await api("/api/v1/sources.json")).status, 200);
  });

  test("single tool by name", async () => {
    const data = await (await api("/api/v1/tools/get_ephemeris")).json();
    assert.equal(data.name, "get_ephemeris");
    assert.deepEqual(data.inputSchema.required.sort(), ["start", "stop", "target"]);
  });

  test("unknown tool is a JSON 404 listing valid names", async () => {
    const res = await api("/api/v1/tools/get_ephemerides");
    assert.equal(res.status, 404);
    const { error } = await res.json();
    assert.equal(error.code, "tool_not_found");
    assert.match(error.hint, /get_ephemeris/);
    assert.match(error.docs, /^https:\/\//);
  });

  test("unknown endpoint is a JSON 404", async () => {
    const res = await api("/api/v2/whatever");
    assert.equal(res.status, 404);
    assert.equal(res.headers.get("Content-Type"), "application/json; charset=utf-8");
    const { error } = await res.json();
    assert.equal(error.code, "not_found");
    assert.ok(error.message && error.hint);
  });

  test("writes are a JSON 405 with Allow", async () => {
    const res = await api("/api/v1/tools", "POST");
    assert.equal(res.status, 405);
    assert.equal(res.headers.get("Allow"), "GET, HEAD, OPTIONS");
    assert.equal((await res.json()).error.code, "method_not_allowed");
  });

  test("OPTIONS preflight succeeds", async () => {
    const res = await api("/api/v1/tools", "OPTIONS");
    assert.equal(res.status, 204);
    assert.match(res.headers.get("Access-Control-Allow-Methods"), /GET/);
  });

  test("asset failure becomes a JSON 500", async () => {
    const broken = { ASSETS: { fetch: async () => new Response("", { status: 503 }) } };
    const res = await handleApi(req("/api/v1/tools"), broken);
    assert.equal(res.status, 500);
    assert.equal((await res.json()).error.code, "internal_error");
  });
});

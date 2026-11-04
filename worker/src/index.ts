// findings.afh.org: a read-only view of the R2 bucket the afh-findings CLI publishes into.
//
//   /                       all findings (from _registry/index.json)
//   /Fnnnn/...              the latest version, served in place
//   /Fnnnn/vN/...           a fixed version (never changes)
//   /Fnnnn[/vN]/_about      files, checksums, history and citation
//   /about /feed.xml /index.json /index.csv /sitemap.xml /robots.txt /_static/bar.js
//
// Only versions listed in the registry are served, so a half-finished upload is never
// visible. Withdrawn findings answer 410 everywhere.

import { STATIC_FILES } from "./generated/static";
import { atom, csv, publicIndex, sitemap } from "./feeds";
import { headHtml, injectHead, pageMeta } from "./meta";
import * as pages from "./pages";
import type { Env, FindingEntry, Index, Manifest } from "./types";

const INDEX_KEY = "_registry/index.json";
const INDEX_TTL_MS = 15_000;
const SHORT = "public, max-age=60";
const IMMUTABLE = "public, max-age=31536000, immutable";
const BASE_HEADERS: Record<string, string> = {
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
};

let indexCache: { index: Index; at: number } | null = null;
const manifestCache = new Map<string, Manifest>();

export function resetCaches(): void {
  indexCache = null;
  manifestCache.clear();
}

async function loadIndex(env: Env): Promise<Index> {
  const now = Date.now();
  if (indexCache && now - indexCache.at < INDEX_TTL_MS) return indexCache.index;
  const obj = await env.FINDINGS.get(INDEX_KEY);
  const index: Index = obj ? await obj.json() : { schema: "afh-findings-index/1", updated: null, findings: {} };
  indexCache = { index, at: now };
  return index;
}

async function loadManifest(env: Env, id: string, version: number): Promise<Manifest | null> {
  const key = `${id}/v${version}/finding.json`;
  const hit = manifestCache.get(key);
  if (hit) return hit;
  const obj = await env.FINDINGS.get(key);
  if (!obj) return null;
  const manifest: Manifest = await obj.json();
  if (manifestCache.size > 500) manifestCache.clear();
  manifestCache.set(key, manifest);
  return manifest;
}

function respond(body: BodyInit | null, status: number, type: string, cache = SHORT, extra: Record<string, string> = {}): Response {
  return new Response(body, { status, headers: { ...BASE_HEADERS, "content-type": type, "cache-control": cache, ...extra } });
}

const html = (body: string, status = 200) => respond(body, status, "text/html; charset=utf-8");
const redirect = (to: string, status = 301) => respond(null, status, "text/plain", SHORT, { location: to });
const notFound = () => respond(pages.notFound(), 404, "text/html; charset=utf-8");

function headOnly(req: Request, res: Response): Response {
  return req.method === "HEAD" ? new Response(null, { status: res.status, headers: res.headers }) : res;
}

const decoded = new Map<string, Uint8Array>();

// bar.js, fonts.css, the font files and their licenses, and the favicon, built into the Worker
// from ../static by scripts/embed-static.mjs.
function serveStatic(rel: string): Response {
  const file = STATIC_FILES[rel];
  if (!file) return notFound();
  let body: BodyInit;
  if (file.base64 !== undefined) {
    let bytes = decoded.get(rel);
    if (!bytes) {
      bytes = Uint8Array.from(atob(file.base64), (c) => c.charCodeAt(0));
      decoded.set(rel, bytes);
    }
    body = bytes;
  } else {
    body = file.text ?? "";
  }
  // Font files are named by family and never change in place; the rest can change on deploy.
  const cache = rel.endsWith(".woff2") ? IMMUTABLE : "public, max-age=3600";
  return respond(body, 200, file.type, cache);
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    if (req.method !== "GET" && req.method !== "HEAD") {
      return respond("Method not allowed", 405, "text/plain", SHORT, { allow: "GET, HEAD" });
    }
    try {
      return headOnly(req, await route(req, env));
    } catch (err) {
      console.error(err);
      return respond("Something went wrong. Please try again.", 500, "text/plain; charset=utf-8", "no-store");
    }
  },
} satisfies ExportedHandler<Env>;

async function route(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  let path: string;
  try {
    path = decodeURIComponent(url.pathname);
  } catch {
    return notFound();
  }
  const site = env.SITE_URL.replace(/\/$/, "");
  switch (path) {
    case "/":
      return html(pages.home(publicIndex(await loadIndex(env))));
    case "/about":
    case "/about/":
      return html(pages.about(site, env.FEEDBACK_URL));
    case "/index.json":
      return respond(JSON.stringify(publicIndex(await loadIndex(env)), null, 1), 200, "application/json; charset=utf-8", SHORT, {
        "access-control-allow-origin": "*",
      });
    case "/index.csv":
      return respond(csv(publicIndex(await loadIndex(env)), site), 200, "text/csv; charset=utf-8");
    case "/feed.xml":
      return respond(atom(await loadIndex(env), site), 200, "application/atom+xml; charset=utf-8");
    case "/sitemap.xml":
      return respond(sitemap(await loadIndex(env), site), 200, "application/xml; charset=utf-8");
    case "/robots.txt":
      return respond(`User-agent: *\nAllow: /\nSitemap: ${site}/sitemap.xml\n`, 200, "text/plain; charset=utf-8");
    case "/favicon.ico":
      return serveStatic("favicon.svg");
  }
  if (path.startsWith("/_static/")) return serveStatic(path.slice("/_static/".length));

  const m = /^\/(F\d{4})(\/.*)?$/.exec(path);
  if (!m) return notFound();
  const [, id, rest] = m;
  if (rest === undefined) return redirect(`/${id}/${url.search}`);
  if (/(^|\/)\.\.?(\/|$)/.test(rest)) return notFound();

  const index = await loadIndex(env);
  const finding = index.findings[id];
  if (!finding) return notFound();
  if (finding.state === "withdrawn") return respond(pages.withdrawn(finding), 410, "text/html; charset=utf-8");

  let version = finding.latest;
  let sub = rest; // starts with "/"
  let pinned = false;
  const vm = /^\/v(\d+)(\/.*)?$/.exec(rest);
  if (vm) {
    version = Number(vm[1]);
    if (!finding.versions.some((v) => v.version === version)) return notFound();
    if (vm[2] === undefined) return redirect(`/${id}/v${version}/${url.search}`);
    sub = vm[2];
    pinned = true;
  }
  return serveVersion(req, env, finding, version, sub, pinned, site);
}

async function serveVersion(
  req: Request,
  env: Env,
  finding: FindingEntry,
  version: number,
  sub: string,
  pinned: boolean,
  site: string,
): Promise<Response> {
  const manifest = await loadManifest(env, finding.id, version);
  if (!manifest) return notFound();
  const urlBase = pinned ? `/${finding.id}/v${version}/` : `/${finding.id}/`;
  const meta = pageMeta(finding, manifest, env);
  const canonicalFor = (rel: string) => `/${finding.id}/${rel}`;

  let rel = sub.slice(1);
  if (rel === "_about" || rel === "_about/") {
    const page = pages.findingAbout(finding, manifest, site);
    return injectHead(html(page), headHtml(meta, site, canonicalFor("_about"), false));
  }
  if (rel === "") rel = manifest.entry;

  const isDir = rel.endsWith("/");
  const dir = rel.replace(/\/$/, "");
  const hasChildren = manifest.files.some((f) => f.path.startsWith(`${dir}/`));
  if (isDir || (hasChildren && !manifest.files.some((f) => f.path === rel))) {
    if (!isDir) return redirect(`${urlBase}${rel}/`);
    if (manifest.files.some((f) => f.path === `${dir}/index.html`)) {
      rel = `${dir}/index.html`;
    } else if (hasChildren) {
      return injectHead(html(pages.listing(manifest, urlBase, dir)), headHtml(meta, site, canonicalFor(`${dir}/`), false));
    } else {
      return notFound();
    }
  }

  const key = `${finding.id}/v${version}/${rel}`;
  const isHtml = /\.html?$/i.test(rel);
  const range = req.headers.has("range") && !isHtml ? req.headers : undefined;
  const obj = await env.FINDINGS.get(key, isHtml ? {} : { onlyIf: req.headers, range });
  if (obj === null) return notFound();

  const headers = new Headers(BASE_HEADERS);
  obj.writeHttpMetadata(headers);
  headers.set("cache-control", pinned && !isHtml ? IMMUTABLE : SHORT);
  if (!isHtml) headers.set("etag", obj.httpEtag);
  if (!("body" in obj)) return new Response(null, { status: 304, headers });

  if (isHtml) {
    if (!headers.get("content-type")) headers.set("content-type", "text/html; charset=utf-8");
    return injectHead(new Response(obj.body, { status: 200, headers }), headHtml(meta, site, canonicalFor(rel === manifest.entry ? "" : rel)));
  }
  if (range && obj.range && "offset" in obj.range) {
    const offset = obj.range.offset ?? 0;
    const length = obj.range.length ?? obj.size - offset;
    headers.set("content-range", `bytes ${offset}-${offset + length - 1}/${obj.size}`);
    headers.set("content-length", String(length));
    return new Response(obj.body, { status: 206, headers });
  }
  headers.set("accept-ranges", "bytes");
  return new Response(obj.body, { status: 200, headers });
}

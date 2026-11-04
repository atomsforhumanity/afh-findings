import { env } from "cloudflare:workers";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import bucket from "./fixtures/bucket.json";
import worker, { resetCaches } from "../src/index";

const SITE = "https://findings.afh.org";
const testEnv = { ...env, SITE_URL: SITE, FEEDBACK_URL: "mailto:findings@example.org" };

function fromB64(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function get(path: string, init?: RequestInit): Promise<Response> {
  return worker.fetch(new Request(SITE + path, init), testEnv);
}

beforeAll(async () => {
  const objects = bucket as Record<string, { content_type: string; data: string }>;
  for (const [key, obj] of Object.entries(objects)) {
    await env.FINDINGS.put(key, fromB64(obj.data), { httpMetadata: { contentType: obj.content_type } });
  }
});

beforeEach(() => resetCaches());

describe("site pages", () => {
  it("lists findings, newest change first, without withdrawn content", async () => {
    const res = await get("/");
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain("GPU single points cost six times less");
    expect(body).toContain("v2 corrected 2026-10-05");
    expect(body).toContain("retracted 2026-10-20");
    expect(body).toContain("Withdrawn 2026-10-16");
    expect(body).not.toContain("should never have been public");
    expect(body.indexOf('data-id="F0001"')).toBeLessThan(body.indexOf('data-id="F0002"'));
  });

  it("serves about, feed, json, csv, sitemap, robots and bar.js", async () => {
    expect((await get("/about")).status).toBe(200);
    const feed = await (await get("/feed.xml")).text();
    expect(feed).toContain("<feed");
    expect(feed).toContain("F0001 v2 (corrected)");
    expect(feed).not.toContain("partner");
    const json = (await (await get("/index.json")).json()) as { findings: Record<string, { title?: string; state: string }> };
    expect(json.findings.F0004).toEqual({ id: "F0004", state: "withdrawn", state_date: "2026-10-16T10:00:00Z", state_reason: "Contained partner data" });
    expect(await (await get("/index.csv")).text()).toMatch(/^id,version,title/);
    expect(await (await get("/sitemap.xml")).text()).toContain(`${SITE}/F0002/`);
    expect(await (await get("/robots.txt")).text()).toContain("Sitemap:");
    const bar = await get("/_static/bar.js");
    expect(bar.headers.get("content-type")).toContain("javascript");
    expect(await bar.text()).toContain("afh-finding-bar");
  });

  it("answers 404 and 405 sensibly", async () => {
    expect((await get("/F9999/")).status).toBe(404);
    expect((await get("/nope")).status).toBe(404);
    expect((await get("/F0001/v9/")).status).toBe(404);
    expect((await get("/F0001/v2/..%2Fv1/index.html")).status).toBe(404);
    expect((await get("/", { method: "POST" })).status).toBe(405);
  });
});

describe("finding pages", () => {
  it("redirects to the trailing slash", async () => {
    const res = await get("/F0001");
    expect(res.status).toBe(301);
    expect(res.headers.get("location")).toBe("/F0001/");
    expect((await get("/F0001/v1")).headers.get("location")).toBe("/F0001/v1/");
  });

  it("serves the latest version in place, with the bar and citation tags", async () => {
    const res = await get("/F0001/");
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain("F0001 version 2");
    expect(body).toContain('<meta name="citation_title"');
    expect(body).toContain(`<link rel="canonical" href="${SITE}/F0001/">`);
    const meta = JSON.parse(body.split('id="afh-finding">')[1].split("</script>")[0]);
    expect(meta).toMatchObject({ id: "F0001", version: 2, latest: 2, stacks_url: "https://thestacks.org/publications/x" });
    expect(body.indexOf("citation_title")).toBeGreaterThan(body.indexOf("</title>"));
    expect(res.headers.get("cache-control")).toBe("public, max-age=60");
  });

  it("marks old versions as outdated and points to the latest", async () => {
    const body = await (await get("/F0001/v1/")).text();
    expect(body).toContain("F0001 version 1");
    const meta = JSON.parse(body.split('id="afh-finding">')[1].split("</script>")[0]);
    expect(meta).toMatchObject({ version: 1, latest: 2, latest_change: { type: "corrected" } });
  });

  it("injects into pages without a head tag", async () => {
    const body = await (await get("/F0002/")).text();
    expect(body).toContain('id="afh-finding"');
    expect(body.indexOf("citation_title")).toBeGreaterThan(body.indexOf("</title>"));
  });

  it("serves versioned files as immutable and latest ones briefly", async () => {
    const pinned = await get("/F0001/v2/data/results.csv");
    expect(pinned.status).toBe(200);
    expect(pinned.headers.get("cache-control")).toContain("immutable");
    expect(pinned.headers.get("content-type")).toContain("text/plain");
    expect(await pinned.text()).toContain("molecule,cpu_s,gpu_s");
    const latest = await get("/F0001/data/results.csv");
    expect(latest.headers.get("cache-control")).toBe("public, max-age=60");
  });

  it("supports range requests and conditional requests on data", async () => {
    const part = await get("/F0001/v2/data/blob.bin", { headers: { range: "bytes=0-9" } });
    expect(part.status).toBe(206);
    expect(part.headers.get("content-range")).toBe("bytes 0-9/2048");
    expect(new Uint8Array(await part.arrayBuffer())).toEqual(new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]));
    const full = await get("/F0001/v2/data/blob.bin");
    const etag = full.headers.get("etag")!;
    const again = await get("/F0001/v2/data/blob.bin", { headers: { "if-none-match": etag } });
    expect(again.status).toBe(304);
  });

  it("lists folders that have no index.html", async () => {
    const res = await get("/F0001/v2/reproduce/");
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain('href="run.py"');
    expect(body).toContain('href="inputs/"');
    expect((await get("/F0001/v2/reproduce")).headers.get("location")).toBe("/F0001/v2/reproduce/");
  });

  it("generates the files & history page", async () => {
    const body = await (await get("/F0001/_about")).text();
    expect(body).toContain("<h2>History</h2>");
    expect(body).toContain("A timing counted twice");
    expect(body).toContain("F0001-v2.zip");
    expect(body).toContain("SHA256SUMS");
    expect(body).toContain("Ada Example");
    expect(body).toContain("CC-BY-4.0"); // data falls back to CC-BY because a source is CC-BY
  });

  it("keeps retracted findings readable with their state", async () => {
    const res = await get("/F0003/");
    expect(res.status).toBe(200);
    const meta = JSON.parse((await res.text()).split('id="afh-finding">')[1].split("</script>")[0]);
    expect(meta).toMatchObject({ state: "retracted", state_reason: "The benchmark set was mislabelled" });
  });

  it("answers 410 for every path of a withdrawn finding", async () => {
    for (const path of ["/F0004/", "/F0004/v1/", "/F0004/v1/data/results.csv", "/F0004/_about"]) {
      const res = await get(path);
      expect(res.status).toBe(410);
      expect(await res.text()).not.toContain("partner numbers");
    }
  });

  it("answers HEAD without a body", async () => {
    const res = await get("/F0001/v2/data/results.csv", { method: "HEAD" });
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("");
  });
});

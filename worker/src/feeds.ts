// Machine-readable views of the registry. Withdrawn findings keep only their notice.

import type { FindingEntry, Index } from "./types";

export function publicIndex(index: Index): Index {
  const findings: Record<string, FindingEntry> = {};
  for (const [id, f] of Object.entries(index.findings)) {
    if (f.state === "withdrawn") {
      findings[id] = {
        id,
        state: "withdrawn",
        state_date: f.state_date,
        state_reason: f.state_reason,
      } as FindingEntry;
    } else {
      findings[id] = f;
    }
  }
  return { ...index, findings };
}

const xml = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c] as string);

export function atom(index: Index, siteUrl: string, limit = 100): string {
  type Entry = { at: string; id: string; title: string; link: string; summary: string; authors: string[] };
  const entries: Entry[] = [];
  for (const f of Object.values(index.findings)) {
    if (f.state === "withdrawn") continue;
    for (const v of f.versions) {
      const label = v.version === 1 ? `${f.id}` : `${f.id} v${v.version} (${v.change?.type ?? "updated"})`;
      entries.push({
        at: v.published,
        id: `${siteUrl}/${f.id}/v${v.version}/`,
        title: `${label}: ${f.title}`,
        link: `${siteUrl}/${f.id}/v${v.version}/`,
        summary: v.change ? `${v.change.summary} · ${f.claim}` : f.claim,
        authors: f.authors.map((a) => a.name),
      });
    }
    if (f.state === "retracted" && f.state_date) {
      entries.push({
        at: f.state_date,
        id: `${siteUrl}/${f.id}/#retracted-${f.state_date}`,
        title: `${f.id} retracted: ${f.title}`,
        link: `${siteUrl}/${f.id}/`,
        summary: f.state_reason ?? "Retracted.",
        authors: f.authors.map((a) => a.name),
      });
    }
  }
  entries.sort((a, b) => b.at.localeCompare(a.at));
  const updated = entries[0]?.at ?? index.updated ?? new Date().toISOString();
  const body = entries
    .slice(0, limit)
    .map(
      (e) => `<entry>
<title>${xml(e.title)}</title>
<id>${xml(e.id)}</id>
<link href="${xml(e.link)}"/>
<updated>${xml(e.at)}</updated>
${e.authors.map((a) => `<author><name>${xml(a)}</name></author>`).join("")}
<summary>${xml(e.summary)}</summary>
</entry>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>AFH Findings</title>
<subtitle>Early results from Atoms for Humanity</subtitle>
<id>${xml(siteUrl)}/</id>
<link rel="self" href="${xml(siteUrl)}/feed.xml"/>
<link href="${xml(siteUrl)}/"/>
<updated>${xml(updated)}</updated>
${body}
</feed>
`;
}

const csvCell = (v: unknown) => {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
};

export function csv(index: Index, siteUrl: string): string {
  const header = [
    "id", "version", "title", "authors", "project", "kind", "status", "state",
    "first_published", "updated", "url", "doi", "stacks_url",
  ];
  const rows = Object.values(index.findings)
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((f) =>
      f.state === "withdrawn"
        ? [f.id, "", "", "", "", "", "", "withdrawn", "", f.state_date, `${siteUrl}/${f.id}/`, "", ""]
        : [
            f.id, f.latest, f.title, f.authors.map((a) => a.name).join("; "), f.project, f.kind, f.status,
            f.state, f.first_published, f.updated, `${siteUrl}/${f.id}/`, f.doi, f.stacks_url,
          ],
    );
  return [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\n") + "\n";
}

export function sitemap(index: Index, siteUrl: string): string {
  const urls = [`<url><loc>${xml(siteUrl)}/</loc></url>`, `<url><loc>${xml(siteUrl)}/about</loc></url>`];
  for (const f of Object.values(index.findings)) {
    if (f.state === "withdrawn") continue;
    urls.push(`<url><loc>${xml(siteUrl)}/${xml(f.id)}/</loc><lastmod>${xml(f.updated.slice(0, 10))}</lastmod></url>`);
  }
  return `<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join("\n")}
</urlset>
`;
}

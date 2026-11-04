// What gets added to every finding page: citation tags, the finding's description as JSON,
// and the header bar script. Mirrors src/afh_findings/page.py.

import { esc } from "./html";
import type { Env, FindingEntry, Manifest } from "./types";

export interface PageMeta {
  id: string;
  version: number;
  latest: number;
  title: string;
  authors: { name: string; orcid?: string }[];
  kind: string;
  project: string;
  status: string;
  published: string;
  first_published: string;
  license: Record<string, string> | null;
  state: string;
  state_reason: string | null;
  state_date: string | null;
  superseded_by: string | null;
  doi: string | null;
  stacks_url: string | null;
  latest_change: { type: string; summary: string } | null;
  latest_published: string | null;
  private_code: string[];
  version_url: string;
  latest_url: string;
  about: string;
  zip: string;
  feedback_url: string | null;
  preview: boolean;
}

export function pageMeta(f: FindingEntry, m: Manifest, env: Env): PageMeta {
  const latest = f.versions[f.versions.length - 1];
  return {
    id: m.id,
    version: m.version,
    latest: f.latest,
    title: m.title,
    authors: m.authors.map((a) => (a.orcid ? { name: a.name, orcid: a.orcid } : { name: a.name })),
    kind: m.kind,
    project: m.project,
    status: m.status,
    published: m.published,
    first_published: f.first_published,
    license: m.license ?? null,
    state: f.state,
    state_reason: f.state_reason,
    state_date: f.state_date,
    superseded_by: f.superseded_by,
    doi: f.doi,
    stacks_url: f.stacks_url,
    latest_change: latest?.change ?? null,
    latest_published: latest?.published ?? null,
    private_code: m.private_code ?? [],
    version_url: `/${m.id}/v${m.version}/`,
    latest_url: `/${m.id}/`,
    about: `/${m.id}/v${m.version}/_about`,
    zip: `/${m.id}/v${m.version}/${m.id}-v${m.version}.zip`,
    feedback_url: env.FEEDBACK_URL || null,
    preview: false,
  };
}

const slashDate = (iso: string) => iso.slice(0, 10).replaceAll("-", "/");

export function headHtml(meta: PageMeta, siteUrl: string, canonicalPath: string, bar = true): string {
  const tag = (name: string, content: string) => `<meta name="${name}" content="${esc(content)}">`;
  const parts = [`<link rel="canonical" href="${esc(siteUrl + canonicalPath)}">`];
  parts.push(tag("citation_title", meta.title));
  for (const a of meta.authors) parts.push(tag("citation_author", a.name));
  parts.push(tag("citation_publication_date", slashDate(meta.first_published)));
  parts.push(tag("citation_online_date", slashDate(meta.published)));
  parts.push(tag("citation_technical_report_institution", "Atoms for Humanity"));
  parts.push(tag("citation_technical_report_number", `${meta.id} v${meta.version}`));
  if (meta.doi) parts.push(tag("citation_doi", meta.doi));
  if (bar) {
    const json = JSON.stringify(meta).replaceAll("<", "\\u003c");
    parts.push(`<script type="application/json" id="afh-finding">${json}</script>`);
    parts.push(`<script src="/_static/bar.js" defer></script>`);
  }
  return parts.join("");
}

// Stream the page through HTMLRewriter, adding `head` after </title>, else before </head>,
// else at the end of the document.
export function injectHead(response: Response, head: string): Response {
  let done = false;
  return new HTMLRewriter()
    .on("title", {
      element(el) {
        if (!done) {
          el.after(head, { html: true });
          done = true;
        }
      },
    })
    .on("head", {
      element(el) {
        el.onEndTag((end) => {
          if (!done) {
            end.before(head, { html: true });
            done = true;
          }
        });
      },
    })
    .onDocument({
      end(end) {
        if (!done) {
          end.append(head, { html: true });
          done = true;
        }
      },
    })
    .transform(response);
}

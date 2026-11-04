// The site's own pages: the list of findings, About, a finding's files & history page,
// folder listings, the withdrawn notice and 404. Styled to match afh.org (see html.ts).

import { REPO_URL, authorList, day, esc, formatBytes, layout } from "./html";
import type { FindingEntry, Index, Manifest } from "./types";

const SITE_NAME = "AFH Findings";
const KIND_LABEL: Record<string, string> = {
  result: "Result",
  method: "Method",
  resource: "Resource",
  "informative-failure": "Informative failure",
};
const kindLabel = (k: string) => KIND_LABEL[k] ?? k;
const byNumberDesc = (a: { id: string }, b: { id: string }) => b.id.localeCompare(a.id);

function changeTag(f: FindingEntry): string {
  const v = f.versions[f.versions.length - 1];
  if (!v || v.version === 1) return "";
  const type = v.change?.type ?? "updated";
  const cls = type === "corrected" || type === "weakened" ? "warn" : "info";
  return `<span class="tag ${cls}" title="${esc(v.change?.summary ?? "")}">v${v.version} · ${esc(type)} ${esc(day(v.published))}</span>`;
}

function statusTag(status: string): string {
  return status === "verified"
    ? `<span class="tag verified" title="A script published with it recomputes its numbers from its data">✓ Verified</span>`
    : `<span class="tag">${esc(status)}</span>`;
}

function homeItem(f: FindingEntry): string {
  if (f.state === "withdrawn") {
    return `<li class="withdrawn" data-id="${esc(f.id)}" data-state="withdrawn" data-updated="${esc(f.updated ?? f.state_date ?? "")}"
      data-text="${esc(f.id.toLowerCase())}"><div class="finding-label"><span class="fid">${esc(f.id)}</span></div>
      <p>Withdrawn ${esc(day(f.state_date))}.</p></li>`;
  }
  const authors = f.authors.map((a) => a.name);
  const attrs = [
    `data-id="${esc(f.id)}"`,
    `data-kind="${esc(f.kind)}"`,
    `data-project="${esc(f.project)}"`,
    `data-status="${esc(f.status)}"`,
    `data-state="${esc(f.state)}"`,
    `data-superseded="${f.superseded_by ? "1" : ""}"`,
    `data-authors="${esc(authors.join("|"))}"`,
    `data-updated="${esc(f.updated)}"`,
    `data-text="${esc(`${f.id} ${f.title} ${f.claim} ${f.keywords.join(" ")} ${authors.join(" ")}`.toLowerCase())}"`,
  ].join(" ");
  const classes = [f.state === "retracted" ? "retracted" : "", f.superseded_by ? "superseded" : ""].join(" ").trim();
  const extras: string[] = [];
  if (f.state === "retracted") extras.push(`<span class="tag bad" title="${esc(f.state_reason)}">Retracted ${esc(day(f.state_date))}</span>`);
  if (f.superseded_by) extras.push(`<span>Superseded by <a href="/${esc(f.superseded_by)}/">${esc(f.superseded_by)}</a></span>`);
  if (f.builds_on.length)
    extras.push(
      `<span>Builds on ${f.builds_on.map((r) => `<a href="/${esc(r)}/">${esc(r.split("/")[0])}</a>`).join(", ")}</span>`,
    );
  if (f.doi) extras.push(`<a href="https://doi.org/${esc(f.doi)}">DOI</a>`);
  if (f.stacks_url) extras.push(`<a href="${esc(f.stacks_url)}">On The Stacks</a>`);
  return `<li class="${classes}" ${attrs}>
  <div class="finding-label"><span class="fid">${esc(f.id)}</span><span>${esc(kindLabel(f.kind))}</span><span>${esc(f.project)}</span></div>
  <h2 class="finding-title"><a href="/${esc(f.id)}/">${esc(f.title)}</a></h2>
  <p class="claim">${esc(f.claim)}</p>
  <div class="meta">
    <span>${esc(authorList(f.authors))}</span>
    <span>${esc(day(f.first_published))}</span>
    ${statusTag(f.status)}
    ${changeTag(f)}
    ${extras.join("\n    ")}
  </div>
</li>`;
}

function options(values: string[], label: string, name: string, show: (v: string) => string = (v) => v): string {
  const unique = [...new Set(values)].sort((a, b) => a.localeCompare(b));
  return `<select name="${name}" aria-label="${label}"><option value="">${label}: all</option>${unique
    .map((v) => `<option value="${esc(v)}">${esc(show(v))}</option>`)
    .join("")}</select>`;
}

const FILTER_JS = `
(() => {
  const form = document.getElementById("filters");
  const list = document.getElementById("list");
  const count = document.getElementById("count");
  const items = [...list.children];
  const params = new URLSearchParams(location.search);
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = params.get(el.name) === "1";
    else if (params.has(el.name)) el.value = params.get(el.name);
  }
  const orders = {
    newest: (a, b) => b.dataset.id.localeCompare(a.dataset.id),
    oldest: (a, b) => a.dataset.id.localeCompare(b.dataset.id),
    changed: (a, b) => (b.dataset.updated || "").localeCompare(a.dataset.updated || ""),
  };
  function apply() {
    const q = form.q.value.trim().toLowerCase();
    const want = { kind: form.kind.value, project: form.project.value, status: form.status.value };
    const author = form.author.value;
    const showOld = form.superseded.checked;
    let shown = 0;
    for (const li of [...items].sort(orders[form.sort.value] || orders.newest)) {
      list.appendChild(li);
      const d = li.dataset;
      const filtered = Object.values(want).some(Boolean) || author;
      const ok = (!q || (d.text || "").includes(q))
        && Object.entries(want).every(([k, v]) => !v || d[k] === v)
        && (!author || (d.authors || "").split("|").includes(author))
        && (showOld || !d.superseded)
        && (d.state !== "withdrawn" || !filtered);
      li.hidden = !ok;
      if (ok) shown++;
    }
    count.textContent = shown === items.length ? items.length + (items.length === 1 ? " finding" : " findings")
      : shown + " of " + items.length + " findings";
    const next = new URLSearchParams();
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === "checkbox") { if (el.checked) next.set(el.name, "1"); }
      else if (el.value && !(el.name === "sort" && el.value === "newest")) next.set(el.name, el.value);
    }
    const qs = next.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }
  form.addEventListener("input", apply);
  form.addEventListener("submit", (e) => e.preventDefault());
  apply();
})();`;

export function home(index: Index): string {
  const findings = Object.values(index.findings).sort(byNumberDesc);
  const visible = findings.filter((f) => f.state !== "withdrawn");
  const n = findings.length;
  const body = `
<p class="eyebrow">Findings</p>
<h1>Results from our research, as we find them.</h1>
<p class="lede">Each finding is one claim with the data and code behind it, published as soon as we understand it.
Findings are not peer-reviewed; every one is versioned, and corrections are made in public.
<a href="/about">How findings work</a>.</p>
<form id="filters" class="filters" role="search">
  <input type="search" name="q" placeholder="Search findings" aria-label="Search findings">
  ${options(visible.map((f) => f.kind), "Kind", "kind", kindLabel)}
  ${options(visible.map((f) => f.project), "Project", "project")}
  ${options(visible.flatMap((f) => f.authors.map((a) => a.name)), "Author", "author")}
  ${options(visible.map((f) => f.status), "Status", "status")}
  <select name="sort" aria-label="Order"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="changed">Recently changed</option></select>
  <label><input type="checkbox" name="superseded" value="1"> Show superseded</label>
</form>
<p id="count" class="count">${n} ${n === 1 ? "finding" : "findings"}</p>
<ol id="list" class="findings">${findings.map(homeItem).join("\n")}</ol>
${n ? "" : "<p>No findings yet.</p>"}
<script>${FILTER_JS}</script>`;
  return layout({
    title: SITE_NAME,
    body,
    current: "/",
    description: "Results from Atoms for Humanity's research, published as we find them.",
  });
}

export function about(siteUrl: string, feedbackUrl: string | undefined): string {
  const feedback = feedbackUrl
    ? `<p>Found a problem? <a href="${esc(feedbackUrl)}">Tell us</a>; every finding page also has a link. We
correct findings in public.</p>`
    : "";
  const body = `
<p class="eyebrow">About</p>
<h1>How findings work</h1>
<p class="lede">Atoms for Humanity publishes results here as soon as we understand them, rather than waiting for a
paper. A finding is small: one claim, the numbers behind it, where it holds, what was not tested, and the data and
code to check it.</p>
<div class="prose">
<h2>What to expect</h2>
<ul>
<li><strong>Not peer-reviewed.</strong> We read each other's findings, but none has been through formal review.
A finding marked <em>verified</em> ships a script that recomputes its numbers from its own data, and that script
passed when it was published.</li>
<li><strong>Versioned.</strong> When later work changes a finding, we publish a new version and say how it changed:
corrected, expanded, strengthened, weakened or revised. Older versions stay readable at
<code>/F0001/v1/</code>, marked as older.</li>
<li><strong>Corrected in public.</strong> A finding that turns out to be wrong is retracted, not deleted: it stays
up with the reason. Only content that should never have been public, such as personal or partner data, is withdrawn,
and a notice stays at its address.</li>
<li><strong>Written with AI assistance.</strong> We use AI tools for analysis code and drafting. The named authors
checked each finding and are responsible for every claim in it.</li>
</ul>
<h2>Citing a finding</h2>
<p>Every finding page has a <em>Cite</em> button. Cite the version you read, for example
<code>${esc(siteUrl)}/F0001/v2/</code>, since the latest version can change. Findings that settle into a longer
write-up are published on <a href="https://thestacks.org">The Stacks</a>, which gives them a DOI, and the finding
links to it.</p>
<h2>Reusing our work</h2>
<p>Unless a finding says otherwise, text and figures are
<a href="https://creativecommons.org/licenses/by/4.0/">CC-BY-4.0</a>, data is
<a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0</a> (CC-BY-4.0 when it derives from CC-BY
sources, which you should credit too), and code is MIT. Each version's <em>Files &amp; history</em> page lists its
files with SHA-256 checksums, and its zip holds everything. We follow the Astera Institute's
<a href="https://astera.org/open-science/">open science policy</a>.</p>
<h2>For machines</h2>
<p>An <a href="/feed.xml">Atom feed</a> of new findings and versions, <a href="/index.json">index.json</a>,
<a href="/index.csv">index.csv</a> and a <a href="/sitemap.xml">sitemap</a>. Each version's
<code>finding.json</code> describes it. The site and its publishing tool are
<a href="${REPO_URL}">open source</a>.</p>
${feedback}
</div>`;
  return layout({ title: `About · ${SITE_NAME}`, body, current: "/about" });
}

function citeText(m: Manifest, f: FindingEntry, siteUrl: string): string {
  const year = day(f.first_published).slice(0, 4);
  const where = f.doi ? `https://doi.org/${f.doi}` : `${siteUrl}/${m.id}/v${m.version}/`;
  return `${authorList(m.authors)} (${year}). ${m.title}. AFH Findings ${m.id}, version ${m.version}. ${where}`;
}

function materials(items: { path: string; description?: string }[], none: string | null, base: string): string {
  if (none) return `<p class="muted">None: ${esc(none)}</p>`;
  return `<ul class="prose">${items
    .map((i) => {
      const isUrl = /^https?:\/\//.test(i.path);
      const href = isUrl ? i.path : base + i.path;
      return `<li><a href="${esc(href)}"><code>${esc(i.path)}</code></a>${i.description ? `: ${esc(i.description)}` : ""}</li>`;
    })
    .join("")}</ul>`;
}

export function findingAbout(f: FindingEntry, m: Manifest, siteUrl: string): string {
  const base = `/${m.id}/v${m.version}/`;
  const notices: string[] = [];
  if (f.state === "retracted")
    notices.push(`<div class="notice bad"><strong>Retracted</strong> ${esc(day(f.state_date))}: ${esc(f.state_reason)}</div>`);
  if (m.version < f.latest)
    notices.push(
      `<div class="notice warn">This is version ${m.version}. The latest is <a href="/${esc(m.id)}/_about">version ${f.latest}</a>.</div>`,
    );
  const versions = [...f.versions]
    .reverse()
    .map(
      (v) => `<tr><td><a href="/${esc(m.id)}/v${v.version}/">v${v.version}</a>${v.version === m.version ? " (this)" : ""}</td>
      <td>${esc(day(v.published))}</td>
      <td>${v.change ? `<span class="tag ${v.change.type === "corrected" || v.change.type === "weakened" ? "warn" : "info"}">${esc(v.change.type)}</span> ${esc(v.change.summary)}` : "First version"}</td>
      <td>${esc(v.publisher ?? "")}</td></tr>`,
    )
    .join("");
  const events = f.events
    .filter((e) => e.type !== "link")
    .map((e) => `<li>${esc(day(String(e.at)))}: ${esc(e.type)}${e.reason ? ` (${esc(e.reason)})` : ""}${e.superseded_by ? ` by ${esc(e.superseded_by)}` : ""}</li>`)
    .join("");
  const files = [...m.files]
    .sort((a, b) => a.path.localeCompare(b.path))
    .map(
      (file) => `<tr><td><a href="${esc(base + file.path)}"><code>${esc(file.path)}</code></a></td><td>${esc(formatBytes(file.size))}</td>
      <td><code title="${esc(file.sha256)}">${esc(file.sha256.slice(0, 12))}…</code></td></tr>`,
    )
    .join("");
  const authors = m.authors
    .map(
      (a) =>
        `${a.orcid ? `<a href="https://orcid.org/${esc(a.orcid)}">${esc(a.name)}</a>` : esc(a.name)}${a.affiliation ? ` <span class="muted">(${esc(a.affiliation)})</span>` : ""}`,
    )
    .join(", ");
  const upstream = m.upstream.length
    ? `<h2>Sources</h2><ul class="prose">${m.upstream
        .map((u) => {
          const link = u.doi ? `https://doi.org/${u.doi}` : u.url;
          return `<li>${link ? `<a href="${esc(link)}">${esc(u.name)}</a>` : esc(u.name)}${u.license ? ` · ${esc(u.license)}` : ""}${u.note ? ` · <span class="muted">${esc(u.note)}</span>` : ""}</li>`;
        })
        .join("")}</ul>`
    : "";
  const fact = (label: string, value: string) => (value ? `<dt>${label}</dt><dd>${value}</dd>` : "");
  const profiles = Object.keys(m.profiles ?? {});
  const privateCode = m.private_code?.length
    ? `<p class="notice warn">Some code used here is not public: ${m.private_code.map((c) => esc(c)).join(", ")}.</p>`
    : "";
  const body = `
<a class="back" href="${esc(base)}">← Read ${esc(m.id)} version ${m.version}</a>
${notices.join("")}
<p class="eyebrow"><span class="mono">${esc(m.id)}</span> · Version ${m.version} · ${esc(kindLabel(m.kind))} · ${esc(m.project)}</p>
<h1 class="long">${esc(m.title)}</h1>
<p class="lede">${esc(m.claim)}</p>
<dl class="facts">
${fact("Authors", authors)}
${fact("Status", statusTag(m.status))}
${fact("Published", `${esc(day(m.published))}${m.publisher ? ` by ${esc(m.publisher)}` : ""}${m.version > 1 ? ` · first version ${esc(day(f.first_published))}` : ""}`)}
${fact("Licenses", `Text ${esc(m.license.text)} · data ${esc(m.license.data)} · code ${esc(m.license.code)}`)}
${fact("Check", m.check ? `<code>${esc(m.check)}</code> recomputes the numbers from the data; it passed at publish.` : "")}
${fact("Rules met", `Core standard${profiles.length ? `, ${profiles.map(esc).join(", ")}` : ""}`)}
${fact("Builds on", m.builds_on.map((r) => `<a href="/${esc(r)}/">${esc(r)}</a>`).join(", "))}
${fact("DOI", f.doi ? `<a href="https://doi.org/${esc(f.doi)}">${esc(f.doi)}</a>` : "")}
${fact("Write-up", f.stacks_url ? `<a href="${esc(f.stacks_url)}">On The Stacks</a>` : "")}
${fact("Formerly", (m.formerly ?? []).map((x) => (/^https?:\/\//.test(x) ? `<a href="${esc(x)}">${esc(x)}</a>` : esc(x))).join("<br>"))}
</dl>
<div class="actions"><a class="button" href="${esc(base + `${m.id}-v${m.version}.zip`)}">Download everything</a>
<a href="${esc(base + "SHA256SUMS")}">SHA256SUMS</a><a href="${esc(base + "finding.json")}">finding.json</a></div>
<h2>Not tested</h2>
<ul class="prose">${m.scope.not_tested.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
<h2>Data</h2>
${materials(m.data, m.data_none, base)}
<h2>Code</h2>
${materials(m.code, m.code_none, base)}
${privateCode}
${upstream}
<h2>Cite</h2>
<pre>${esc(citeText(m, f, siteUrl))}</pre>
<h2>History</h2>
<div class="table-wrap"><table><tr><th>Version</th><th>Date</th><th>Change</th><th>Published by</th></tr>${versions}</table></div>
${events ? `<ul class="prose">${events}</ul>` : ""}
<h2>Files</h2>
<div class="table-wrap"><table><tr><th>File</th><th>Size</th><th>SHA-256</th></tr>${files}</table></div>`;
  return layout({ title: `${m.id} v${m.version}: files & history · ${SITE_NAME}`, body, description: m.claim });
}

export function listing(m: Manifest, urlBase: string, dir: string): string {
  const prefix = dir ? `${dir}/` : "";
  const entries = new Map<string, number | null>();
  for (const file of m.files) {
    if (!file.path.startsWith(prefix)) continue;
    const rest = file.path.slice(prefix.length);
    const slash = rest.indexOf("/");
    if (slash === -1) entries.set(rest, file.size);
    else entries.set(rest.slice(0, slash + 1), null);
  }
  const rows = [...entries.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, size]) => `<tr><td><a href="${esc(name)}"><code>${esc(name)}</code></a></td><td>${size === null ? "" : esc(formatBytes(size))}</td></tr>`)
    .join("");
  const body = `
<a class="back" href="${esc(urlBase)}">← ${esc(m.id)}: ${esc(m.title)}</a>
<p class="eyebrow"><span class="mono">${esc(m.id)}</span> · Version ${m.version} · Files</p>
<h1 class="long"><code>${esc(prefix || "/")}</code></h1>
<div class="table-wrap" style="margin-top:2rem"><table><tr><th>Name</th><th>Size</th></tr>${prefix ? `<tr><td><a href="../"><code>../</code></a></td><td></td></tr>` : ""}${rows}</table></div>`;
  return layout({ title: `${m.id}/${prefix} · ${SITE_NAME}`, body });
}

export function withdrawn(f: FindingEntry): string {
  const body = `
<p class="eyebrow"><span class="mono">${esc(f.id)}</span> · Withdrawn</p>
<h1>${esc(f.id)} was withdrawn</h1>
<p class="lede">Withdrawn on ${esc(day(f.state_date))}${f.state_reason ? `: ${esc(f.state_reason)}` : "."}</p>
<p class="prose">Findings are withdrawn only when their content should not have been public. Findings that turned
out to be wrong are retracted instead and stay readable. <a href="/">All findings</a>.</p>`;
  return layout({ title: `${f.id} withdrawn · ${SITE_NAME}`, body });
}

export function notFound(): string {
  return layout({
    title: `Not found · ${SITE_NAME}`,
    body: `<p class="eyebrow">404</p><h1>Nothing is published here.</h1>
<p class="lede">Findings live at addresses like <code>/F0001/</code>. <a href="/">See all findings</a>.</p>`,
  });
}

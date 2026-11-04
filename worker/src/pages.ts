// The site's own pages: the list of findings, About, a finding's files & history page,
// folder listings, the withdrawn notice and 404.

import { authorList, day, esc, formatBytes, layout } from "./html";
import type { FindingEntry, Index, Manifest } from "./types";

const SITE_NAME = "AFH Findings";

function lastChange(f: FindingEntry): string {
  const v = f.versions[f.versions.length - 1];
  if (!v || v.version === 1) return `new ${day(f.first_published)}`;
  return `v${v.version} ${v.change?.type ?? "updated"} ${day(v.published)}`;
}

function changeClass(f: FindingEntry): string {
  const v = f.versions[f.versions.length - 1];
  return v?.change ? `change-${esc(v.change.type)}` : "";
}

function homeItem(f: FindingEntry): string {
  if (f.state === "withdrawn") {
    return `<li class="withdrawn" data-state="withdrawn" data-text="${esc(f.id.toLowerCase())}"
      data-updated="${esc(f.updated)}" data-id="${esc(f.id)}">
      <span class="fid">${esc(f.id)}</span><span class="muted">Withdrawn ${esc(day(f.state_date))}.</span></li>`;
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
  if (f.state === "retracted") extras.push(`<span class="chip change-corrected">retracted ${esc(day(f.state_date))}</span>`);
  if (f.superseded_by) extras.push(`<span>superseded by <a href="/${esc(f.superseded_by)}/">${esc(f.superseded_by)}</a></span>`);
  if (f.builds_on.length)
    extras.push(
      `<span>builds on ${f.builds_on
        .map((r) => `<a href="/${esc(r)}/">${esc(r.split("/")[0])}</a>`)
        .join(", ")}</span>`,
    );
  if (f.doi) extras.push(`<a href="https://doi.org/${esc(f.doi)}">DOI</a>`);
  if (f.stacks_url) extras.push(`<a href="${esc(f.stacks_url)}">The Stacks</a>`);
  return `<li class="${classes}" ${attrs}>
  <div><span class="fid">${esc(f.id)}</span><a class="title" href="/${esc(f.id)}/">${esc(f.title)}</a></div>
  <p class="claim">${esc(f.claim)}</p>
  <div class="meta">
    <span>${esc(authorList(f.authors))}</span>
    <span class="chip">${esc(f.kind)}</span>
    <span>${esc(f.project)}</span>
    <span class="chip ${f.status === "verified" ? "verified" : ""}">${esc(f.status)}</span>
    <span class="chip ${changeClass(f)}">${esc(lastChange(f))}</span>
    ${extras.join("\n    ")}
  </div>
</li>`;
}

function options(values: string[], label: string, name: string): string {
  const unique = [...new Set(values)].sort((a, b) => a.localeCompare(b));
  return `<select name="${name}" aria-label="${label}"><option value="">${label}: all</option>${unique
    .map((v) => `<option value="${esc(v)}">${esc(v)}</option>`)
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
  function apply() {
    const q = form.q.value.trim().toLowerCase();
    const want = { kind: form.kind.value, project: form.project.value, status: form.status.value };
    const author = form.author.value;
    const showOld = form.superseded.checked;
    const sort = form.sort.value;
    let shown = 0;
    const sorted = [...items].sort((a, b) => sort === "id"
      ? a.dataset.id.localeCompare(b.dataset.id)
      : (b.dataset.updated || "").localeCompare(a.dataset.updated || ""));
    for (const li of sorted) {
      list.appendChild(li);
      const d = li.dataset;
      let ok = (!q || (d.text || "").includes(q))
        && Object.entries(want).every(([k, v]) => !v || d[k] === v)
        && (!author || (d.authors || "").split("|").includes(author))
        && (showOld || !d.superseded)
        && (d.state !== "withdrawn" || (!want.kind && !want.project && !want.status && !author));
      li.hidden = !ok;
      if (ok) shown++;
    }
    count.textContent = shown === items.length ? items.length + " findings" : shown + " of " + items.length + " findings";
    const next = new URLSearchParams();
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === "checkbox") { if (el.checked) next.set(el.name, "1"); }
      else if (el.value && !(el.name === "sort" && el.value === "updated")) next.set(el.name, el.value);
    }
    const qs = next.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }
  form.addEventListener("input", apply);
  form.addEventListener("submit", (e) => e.preventDefault());
  apply();
})();`;

export function home(index: Index): string {
  const findings = Object.values(index.findings).sort((a, b) => (b.updated ?? "").localeCompare(a.updated ?? ""));
  const visible = findings.filter((f) => f.state !== "withdrawn");
  const body = `
<header>
  <h1>Atoms for Humanity: Findings</h1>
  <p class="lede">Early results from our research, published as soon as we understand them. Each finding is one
  claim with the data and code behind it. They are not peer-reviewed; every one is versioned, and corrections are
  made in public.</p>
  <nav class="nav"><a href="/about">About &amp; how to cite</a><a href="/feed.xml">Feed</a>
  <a href="/index.json">JSON</a><a href="/index.csv">CSV</a></nav>
</header>
<form id="filters" class="filters" role="search">
  <input type="search" name="q" placeholder="Search claims" aria-label="Search claims">
  ${options(visible.map((f) => f.kind), "Kind", "kind")}
  ${options(visible.map((f) => f.project), "Project", "project")}
  ${options(visible.flatMap((f) => f.authors.map((a) => a.name)), "Author", "author")}
  ${options(visible.map((f) => f.status), "Status", "status")}
  <select name="sort" aria-label="Sort"><option value="updated">Recently changed</option><option value="id">By number</option></select>
  <label><input type="checkbox" name="superseded" value="1"> show superseded</label>
</form>
<p id="count" class="count">${findings.length} findings</p>
${findings.length ? `<ol id="list" class="findings">${findings.map(homeItem).join("\n")}</ol>` : `<ol id="list" class="findings"></ol><p>No findings yet.</p>`}
<footer>Text and figures CC-BY-4.0, data CC0 unless a finding says otherwise, code MIT.
Atoms for Humanity, Astera Institute.</footer>
<script>${FILTER_JS}</script>`;
  return layout({
    title: SITE_NAME,
    body,
    description: "Early results from Atoms for Humanity, published as soon as we understand them.",
  });
}

export function about(siteUrl: string, feedbackUrl: string | undefined): string {
  const feedback = feedbackUrl
    ? `<p>Found a problem? <a href="${esc(feedbackUrl)}">Tell us</a>. We correct findings in public.</p>`
    : "";
  const body = `
<p><a href="/">← All findings</a></p>
<h1>About AFH Findings</h1>
<p class="lede">Atoms for Humanity publishes results here as soon as we understand them, rather than waiting for a
paper. A finding is small: one claim, the numbers behind it, where it holds, what was not tested, and the data and
code to check it.</p>
<h2>What to expect</h2>
<ul>
<li><strong>Not peer-reviewed.</strong> We read each other's findings, but nothing here has been through formal
review. Some are marked <em>verified</em>: a script published with the finding recomputes its numbers from its
data, and it passed when the finding was published.</li>
<li><strong>Versioned.</strong> When later work changes a finding, we publish a new version and say how it changed
(corrected, expanded, strengthened, weakened or revised). Older versions stay readable at <code>/F0001/v1/</code>, with a
note pointing to the latest.</li>
<li><strong>Corrected in public.</strong> A finding that turns out to be wrong is retracted, not deleted: it stays
up with the reason. Only content that should never have been public (for example personal or partner data) is
withdrawn, and a notice stays at its address.</li>
<li><strong>Written with AI assistance.</strong> We use AI tools for analysis code and drafting. The named authors
checked each finding and are responsible for every claim in it.</li>
</ul>
<h2>Citing a finding</h2>
<p>Every finding page has a <em>Cite</em> button. Cite the version you read, for example
<code>${esc(siteUrl)}/F0001/v2/</code>, since the latest version can change. Findings that settle into a longer
write-up are published on <a href="https://thestacks.org">The Stacks</a>, which gives them a DOI; the finding links
to it.</p>
<h2>Reusing our work</h2>
<p>Unless a finding says otherwise: text and figures are <a href="https://creativecommons.org/licenses/by/4.0/">CC-BY-4.0</a>,
data is <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0</a> (CC-BY-4.0 when it derives from
CC-BY sources, which you should credit too), and code is MIT. Each version's <em>Files &amp; history</em> page
lists its files with SHA-256 checksums, and its zip holds everything.</p>
<h2>For machines</h2>
<p><a href="/feed.xml">Atom feed</a> of new findings and versions · <a href="/index.json">index.json</a> ·
<a href="/index.csv">index.csv</a> · <a href="/sitemap.xml">sitemap</a>. Each version's
<code>finding.json</code> describes it.</p>
${feedback}
<p class="muted">Atoms for Humanity is part of the <a href="https://astera.org">Astera Institute</a>, which publishes
openly under its <a href="https://astera.org/open-science/">open science policy</a>.</p>`;
  return layout({ title: `About · ${SITE_NAME}`, body });
}

function citeText(m: Manifest, f: FindingEntry, siteUrl: string): string {
  const year = day(f.first_published).slice(0, 4);
  const where = f.doi ? `https://doi.org/${f.doi}` : `${siteUrl}/${m.id}/v${m.version}/`;
  return `${authorList(m.authors)} (${year}). ${m.title}. AFH Findings ${m.id}, version ${m.version}. ${where}`;
}

function materials(items: { path: string; description?: string }[], none: string | null, base: string): string {
  if (none) return `<p class="muted">None: ${esc(none)}</p>`;
  return `<ul>${items
    .map((i) => {
      const isUrl = /^https?:\/\//.test(i.path);
      const href = isUrl ? i.path : base + i.path;
      return `<li><a href="${esc(href)}">${esc(i.path)}</a>${i.description ? ` · ${esc(i.description)}` : ""}</li>`;
    })
    .join("")}</ul>`;
}

export function findingAbout(f: FindingEntry, m: Manifest, siteUrl: string): string {
  const base = `/${m.id}/v${m.version}/`;
  const notices: string[] = [];
  if (f.state === "retracted")
    notices.push(`<div class="notice bad"><strong>Retracted</strong> ${esc(day(f.state_date))}: ${esc(f.state_reason)}</div>`);
  if (m.version < f.latest)
    notices.push(`<div class="notice warn">This is version ${m.version}. The latest is <a href="/${esc(m.id)}/_about">version ${f.latest}</a>.</div>`);
  const versions = [...f.versions]
    .reverse()
    .map(
      (v) => `<tr><td><a href="/${esc(m.id)}/v${v.version}/">v${v.version}</a>${v.version === m.version ? " (this)" : ""}</td>
      <td>${esc(day(v.published))}</td><td>${v.change ? `<span class="chip change-${esc(v.change.type)}">${esc(v.change.type)}</span> ${esc(v.change.summary)}` : "First version"}</td>
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
      (file) => `<tr><td><a href="${esc(base + file.path)}">${esc(file.path)}</a></td><td>${esc(formatBytes(file.size))}</td>
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
    ? `<h2>Builds on</h2><ul>${m.upstream
        .map((u) => {
          const link = u.doi ? `https://doi.org/${u.doi}` : u.url;
          return `<li>${link ? `<a href="${esc(link)}">${esc(u.name)}</a>` : esc(u.name)}${u.license ? ` · ${esc(u.license)}` : ""}${u.note ? ` · ${esc(u.note)}` : ""}</li>`;
        })
        .join("")}</ul>`
    : "";
  const buildsOn = m.builds_on.length
    ? `<p>Other findings: ${m.builds_on.map((r) => `<a href="/${esc(r)}/">${esc(r)}</a>`).join(", ")}</p>`
    : "";
  const privateCode = m.private_code?.length
    ? `<p class="notice warn">Some code used here is not public: ${m.private_code.map((c) => esc(c)).join(", ")}.</p>`
    : "";
  const cite = citeText(m, f, siteUrl);
  const body = `
<p><a href="/">← All findings</a> · <a href="${esc(base)}">Read ${esc(m.id)} v${m.version}</a></p>
${notices.join("")}
<p class="muted">${esc(m.id)} · version ${m.version} · ${esc(m.kind)} · ${esc(m.project)} ·
<span class="chip ${m.status === "verified" ? "verified" : ""}">${esc(m.status)}</span></p>
<h1>${esc(m.title)}</h1>
<p>${esc(m.claim)}</p>
<table>
<tr><th>Authors</th><td>${authors}</td></tr>
<tr><th>Published</th><td>${esc(day(m.published))}${m.publisher ? ` by ${esc(m.publisher)}` : ""}${m.version > 1 ? ` · first version ${esc(day(f.first_published))}` : ""}</td></tr>
<tr><th>Licenses</th><td>text ${esc(m.license.text)} · data ${esc(m.license.data)} · code ${esc(m.license.code)}</td></tr>
${m.check ? `<tr><th>Check</th><td><code>${esc(m.check)}</code> recomputes the numbers from the data; it passed at publish.</td></tr>` : ""}
${Object.keys(m.profiles ?? {}).length ? `<tr><th>Rules met</th><td>core standard, ${Object.keys(m.profiles).map(esc).join(", ")}</td></tr>` : `<tr><th>Rules met</th><td>core standard</td></tr>`}
${f.doi ? `<tr><th>DOI</th><td><a href="https://doi.org/${esc(f.doi)}">${esc(f.doi)}</a></td></tr>` : ""}
${f.stacks_url ? `<tr><th>Write-up</th><td><a href="${esc(f.stacks_url)}">On The Stacks</a></td></tr>` : ""}
</table>
<h2>Not tested</h2>
<ul>${m.scope.not_tested.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
<h2>Data</h2>
${materials(m.data, m.data_none, base)}
<h2>Code</h2>
${materials(m.code, m.code_none, base)}
${privateCode}
${upstream}
${buildsOn}
<h2>Cite</h2>
<pre>${esc(cite)}</pre>
<h2>History</h2>
<table><tr><th>Version</th><th>Date</th><th>Change</th><th>Published by</th></tr>${versions}</table>
${events ? `<ul>${events}</ul>` : ""}
<h2>Files</h2>
<p><a href="${esc(base + `${m.id}-v${m.version}.zip`)}">Download everything (${esc(m.id)}-v${m.version}.zip)</a> ·
<a href="${esc(base + "SHA256SUMS")}">SHA256SUMS</a> · <a href="${esc(base + "finding.json")}">finding.json</a></p>
<table><tr><th>File</th><th>Size</th><th>SHA-256</th></tr>${files}</table>`;
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
    .map(([name, size]) => `<tr><td><a href="${esc(name)}">${esc(name)}</a></td><td>${size === null ? "" : esc(formatBytes(size))}</td></tr>`)
    .join("");
  const body = `
<p><a href="${esc(urlBase)}">← ${esc(m.id)}: ${esc(m.title)}</a></p>
<h1><code>${esc(prefix || "/")}</code></h1>
<table><tr><th>Name</th><th>Size</th></tr>${prefix ? `<tr><td><a href="../">../</a></td><td></td></tr>` : ""}${rows}</table>`;
  return layout({ title: `${m.id}/${prefix} · ${SITE_NAME}`, body });
}

export function withdrawn(f: FindingEntry): string {
  const body = `
<p><a href="/">← All findings</a></p>
<h1>${esc(f.id)} was withdrawn</h1>
<p>Withdrawn on ${esc(day(f.state_date))}${f.state_reason ? `: ${esc(f.state_reason)}` : "."}</p>
<p class="muted">Findings are withdrawn only when their content should not have been public. Findings that turned out
to be wrong are retracted instead and stay readable.</p>`;
  return layout({ title: `${f.id} withdrawn · ${SITE_NAME}`, body });
}

export function notFound(): string {
  return layout({
    title: `Not found · ${SITE_NAME}`,
    body: `<p><a href="/">← All findings</a></p><h1>Not found</h1><p>Nothing is published at this address.</p>`,
  });
}

// The header bar on every finding page: identity, status, cite, files, and notices about
// older, superseded or retracted versions. Styled like afh.org. It lives in a Shadow DOM so
// the page's styles and the bar's can't affect each other, and sits in its own layer above
// the page so fixed headers or sidebars on the page can't draw over it.
// Data comes from <script type="application/json" id="afh-finding">.
(() => {
  const source = document.getElementById("afh-finding");
  if (!source || customElements.get("afh-finding-bar")) return;
  let m;
  try {
    m = JSON.parse(source.textContent);
  } catch {
    return;
  }

  // The brand typefaces are declared for the whole document (Shadow DOM can't declare fonts).
  if (!document.querySelector("link[data-afh-fonts]")) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/_static/fonts.css";
    link.dataset.afhFonts = "";
    document.head.appendChild(link);
  }

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const day = (iso) => (iso ? String(iso).slice(0, 10) : "");
  const origin = location.origin;
  const versionUrl = origin + m.version_url;
  const year = day(m.first_published).slice(0, 4);
  const names = m.authors.map((a) => a.name);
  const nameList = names.length > 1 ? names.slice(0, -1).join(", ") + " and " + names.at(-1) : names[0] || "";
  const kinds = { result: "Result", method: "Method", resource: "Resource", "informative-failure": "Informative failure" };

  const citeText =
    `${nameList} (${year}). ${m.title}. AFH Findings ${m.id}, version ${m.version}. ` +
    (m.doi ? `https://doi.org/${m.doi}` : versionUrl);
  const bibtex = [
    `@techreport{afh-${m.id}-v${m.version},`,
    `  author = {${names.map((n) => `{${n}}`).join(" and ")}},`,
    `  title = {${m.title}},`,
    `  institution = {Atoms for Humanity},`,
    `  type = {AFH Findings},`,
    `  number = {${m.id} v${m.version}},`,
    `  year = {${year}},`,
    `  url = {${versionUrl}},`,
    ...(m.doi ? [`  doi = {${m.doi}},`] : []),
    `}`,
  ].join("\n");

  // Full-width banners only for previews and retractions; older or superseded versions get a
  // tag in the bar's single row.
  let banner = "";
  let notice = "";
  if (m.preview) {
    banner = `<div class="banner preview">Preview: not published. The number and version are placeholders.</div>`;
  } else if (m.state === "retracted") {
    banner = `<div class="banner bad"><strong>Retracted</strong> ${esc(day(m.state_date))}: ${esc(m.state_reason)}</div>`;
  }
  if (!m.preview && m.superseded_by) {
    notice = `<a class="tag warn" href="/${esc(m.superseded_by)}/">Superseded by ${esc(m.superseded_by)}</a>`;
  } else if (!m.preview && m.version < m.latest) {
    const change = m.latest_change ? ` · ${esc(m.latest_change.type)} ${esc(day(m.latest_published))}` : "";
    const why = m.latest_change ? esc(m.latest_change.summary) : "";
    notice = `<a class="tag warn" href="${esc(m.latest_url)}" title="${why}">Older version · latest is v${m.latest}${change}</a>`;
  }

  // A GitHub "new issue" link opens our issue form with this finding already named.
  let feedback = m.feedback_url;
  if (feedback && /github\.com\/.+\/issues\/new$/.test(feedback)) {
    const q = new URLSearchParams({ template: "problem-with-a-finding.yml", title: `${m.id} v${m.version}: ` });
    feedback += `?${q}`;
  }

  const authorsHtml = m.authors
    .map((a) =>
      a.orcid ? `<a href="https://orcid.org/${esc(a.orcid)}" title="ORCID ${esc(a.orcid)}">${esc(a.name)}</a>` : esc(a.name),
    )
    .join(", ");
  const extras = [];
  if (m.doi) extras.push(`<a href="https://doi.org/${esc(m.doi)}">DOI</a>`);
  if (m.stacks_url) extras.push(`<a href="${esc(m.stacks_url)}">On The Stacks</a>`);
  if (m.private_code && m.private_code.length)
    extras.push(`<span class="muted" title="${esc(m.private_code.join(", "))}">Some code is not public</span>`);

  const mark = `<svg class="mark" viewBox="0 0 64 64" aria-hidden="true"><g class="orbit"><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(30 32 32)"/><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(-30 32 32)"/><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(90 32 32)"/></g><circle class="nucleus" cx="32" cy="32" r="7"/><path class="earth" d="M27 31c4-4 7-2 10-5M27 35c4-2 7 3 11 0"/></svg>`;

  const css = `
    :host { all: initial; display: block; position: relative; z-index: 2147483000; }
    .bar {
      --bg: #f8f7f3; --bg-2: #fcfcfa; --ink: #202a33; --ink-2: #4e5e6a; --muted: #5e6d78; --heading: #17324a;
      --blue: #3868b8; --blue-light: #7fa6df; --blue-soft: #eaf0f8; --green: #496e5c; --green-soft: #e7efe9;
      --border: #d9dee3; --border-strong: #9baec0; --focus: #b1cbef;
      --warn-bg: #f7efdc; --warn-fg: #76561a; --warn-line: #dcc48f; --bad-bg: #f7e5e1; --bad-fg: #8a2f22;
      --prev-bg: #eaf0f8; --prev-fg: #17324a;
      font: 400 14.5px/1.45 "Source Sans 3 Variable", "Segoe UI", system-ui, sans-serif;
      color: var(--ink); background: var(--bg); border-bottom: 1px solid var(--border);
      -webkit-font-smoothing: antialiased; text-align: left;
    }
    @media (prefers-color-scheme: dark) {
      .bar {
        --bg: #17324a; --bg-2: #1c3b58; --ink: #f8f7f3; --ink-2: #d3dde7; --muted: #b4c5d5; --heading: #fcfcfa;
        --blue: #b1cbef; --blue-soft: #244868; --green: #a9d3bb; --green-soft: #244a45;
        --border: #456077; --border-strong: #6c88a2;
        --warn-bg: #3e3a25; --warn-fg: #f1d993; --warn-line: #7e6d3b; --bad-bg: #4a2c2c; --bad-fg: #f6b9ae;
        --prev-bg: #244868; --prev-fg: #fcfcfa;
      }
    }
    a { color: var(--ink-2); text-decoration: none; }
    a:hover { color: var(--blue); text-decoration: underline; text-decoration-color: var(--blue-light); text-underline-offset: .2em; }
    .row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; padding: 9px 20px; }
    .brand { display: inline-flex; align-items: center; gap: 8px; color: var(--heading); font-weight: 600; white-space: nowrap; }
    .brand:hover { color: var(--heading); }
    .brand span { color: var(--blue); font-weight: 600; }
    .mark { width: 22px; height: 22px; overflow: visible; }
    .orbit { fill: none; stroke: currentColor; stroke-width: 2.2px; }
    .nucleus { fill: var(--blue); }
    .earth { fill: none; stroke: var(--bg); stroke-width: 2px; stroke-linecap: round; }
    .id { font: 500 13px/1.4 "Geist Mono Variable", ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--heading); white-space: nowrap; }
    .muted { color: var(--muted); }
    .tag { display: inline-flex; align-items: center; border: 1px solid var(--border-strong); border-radius: 3px; padding: 1px 7px;
           font: 600 10.5px/1.5 "Source Sans 3 Variable", "Segoe UI", system-ui, sans-serif; letter-spacing: .07em;
           text-transform: uppercase; color: var(--ink-2); white-space: nowrap; }
    .tag.verified { border-color: transparent; background: var(--green-soft); color: var(--green); }
    a.tag.warn { border-color: var(--warn-line); background: var(--warn-bg); color: var(--warn-fg); text-decoration: none; }
    a.tag.warn:hover { text-decoration: underline; }
    .who { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 12rem; color: var(--ink-2); }
    .actions { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
    button { all: unset; cursor: pointer; color: var(--ink-2); }
    button:hover { color: var(--blue); text-decoration: underline; text-decoration-color: var(--blue-light); text-underline-offset: .2em; }
    button:focus-visible, a:focus-visible { outline: 2px solid var(--focus); outline-offset: 3px; border-radius: 2px; }
    .banner { padding: 9px 20px; border-bottom: 1px solid var(--border); }
    .banner.bad { background: var(--bad-bg); color: var(--bad-fg); }
    .banner.preview { background: var(--prev-bg); color: var(--prev-fg); }
    .cite { display: none; margin: 0 20px 14px; padding: 12px 16px 14px; background: var(--bg-2);
            border: 1px solid var(--border); border-radius: 4px; box-shadow: 0 8px 24px rgba(23, 50, 74, .12); max-width: 56rem; }
    .cite.open { display: block; }
    .label { display: flex; justify-content: space-between; align-items: baseline; margin-top: 8px; }
    .label span { color: var(--muted); font: 600 10.5px/1.5 "Source Sans 3 Variable", system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; }
    pre { font: 12.5px/1.5 "Geist Mono Variable", ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--bg);
          color: var(--ink); border: 1px solid var(--border); padding: 9px 11px; border-radius: 3px;
          white-space: pre-wrap; word-break: break-word; margin: 6px 0 0; }
  `;

  class FindingBar extends HTMLElement {
    connectedCallback() {
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>${css}</style>
        <div class="bar" role="banner" aria-label="About this finding">
          ${banner}
          <div class="row">
            <a class="brand" href="/" title="All findings">${mark}<span>Findings</span></a>
            <span class="id">${esc(m.id)} · v${m.version}</span>
            ${notice}
            <span class="tag ${m.status === "verified" ? "verified" : ""}">${m.status === "verified" ? "✓ Verified" : esc(m.status)}</span>
            <span class="tag">${esc(kinds[m.kind] || m.kind)}</span>
            <span class="who">${authorsHtml} <span class="muted">· ${esc(day(m.published))}</span></span>
            <span class="actions">
              ${extras.join("")}
              <button type="button" data-action="cite" aria-expanded="false" aria-controls="cite">Cite</button>
              <a href="${esc(m.about)}">Files &amp; history</a>
              <a href="${esc(m.zip)}" download>Download</a>
              ${feedback ? `<a href="${esc(feedback)}">Report a problem</a>` : ""}
            </span>
          </div>
          <div class="cite" id="cite" role="region" aria-label="Cite this finding">
            <div class="label"><span>Text</span><button type="button" data-copy="text">Copy</button></div>
            <pre>${esc(citeText)}</pre>
            <div class="label"><span>BibTeX</span><button type="button" data-copy="bibtex">Copy</button></div>
            <pre>${esc(bibtex)}</pre>
          </div>
        </div>`;
      const panel = root.getElementById("cite");
      const toggle = root.querySelector('[data-action="cite"]');
      toggle.addEventListener("click", () => {
        const open = panel.classList.toggle("open");
        toggle.setAttribute("aria-expanded", String(open));
      });
      root.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && panel.classList.contains("open")) {
          panel.classList.remove("open");
          toggle.setAttribute("aria-expanded", "false");
          toggle.focus();
        }
      });
      root.querySelectorAll("[data-copy]").forEach((b) =>
        b.addEventListener("click", async () => {
          const text = b.dataset.copy === "text" ? citeText : bibtex;
          try {
            await navigator.clipboard.writeText(text);
            b.textContent = "Copied";
          } catch {
            b.textContent = "Select and copy";
          }
          setTimeout(() => (b.textContent = "Copy"), 1500);
        }),
      );
    }
  }
  customElements.define("afh-finding-bar", FindingBar);
  // Insert before <body>, not inside it, so the bar spans the window whatever margins,
  // max-width or flex layout the page gives its body.
  const mount = () => {
    if (!document.body || document.querySelector("afh-finding-bar")) return;
    document.documentElement.insertBefore(document.createElement("afh-finding-bar"), document.body);
  };
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();

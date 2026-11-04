// The header bar on every finding page: identity, status, cite, files, and warnings about
// old, superseded or retracted versions. It lives in a Shadow DOM so the page's styles and
// the bar's styles can't affect each other. Data comes from <script id="afh-finding">.
(() => {
  const source = document.getElementById("afh-finding");
  if (!source || customElements.get("afh-finding-bar")) return;
  let m;
  try {
    m = JSON.parse(source.textContent);
  } catch {
    return;
  }

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const day = (iso) => (iso ? String(iso).slice(0, 10) : "");
  const origin = location.origin;
  const versionUrl = origin + m.version_url;
  const year = day(m.first_published).slice(0, 4);
  const names = m.authors.map((a) => a.name);
  const nameList = names.length > 1 ? names.slice(0, -1).join(", ") + " and " + names.at(-1) : names[0] || "";

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

  // Banners (a full-width row) only for previews and retractions. Older or superseded
  // versions get a chip in the bar's single row, so pages with fixed headers or sidebars
  // (which sit just below the top of the window) aren't covered.
  let banner = "";
  let notice = "";
  if (m.preview) {
    banner = `<div class="banner preview">Preview: not published. The number and version are placeholders.</div>`;
  } else if (m.state === "retracted") {
    banner = `<div class="banner bad"><strong>Retracted</strong> ${esc(day(m.state_date))}: ${esc(m.state_reason)}</div>`;
  }
  if (!m.preview && m.superseded_by) {
    notice = `<a class="chip warn" href="/${esc(m.superseded_by)}/">Superseded by ${esc(m.superseded_by)}</a>`;
  } else if (!m.preview && m.version < m.latest) {
    const change = m.latest_change ? ` (${esc(m.latest_change.type)} ${esc(day(m.latest_published))})` : "";
    const why = m.latest_change ? esc(m.latest_change.summary) : "";
    notice = `<a class="chip warn" href="${esc(m.latest_url)}" title="${why}">Older version · latest is v${m.latest}${change}</a>`;
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
  if (m.doi) extras.push(`<a href="https://doi.org/${esc(m.doi)}">DOI ${esc(m.doi)}</a>`);
  if (m.stacks_url) extras.push(`<a href="${esc(m.stacks_url)}">On The Stacks</a>`);
  if (m.private_code && m.private_code.length)
    extras.push(`<span title="${esc(m.private_code.join(", "))}">Some code is not public</span>`);

  const css = `
    :host { all: initial; display: block; }
    .bar {
      --bg: #f6f5f1; --fg: #1d1d1b; --muted: #6b6b66; --rule: #e2e1dc; --accent: #2a5db0;
      --warn-bg: #fff4d6; --warn-fg: #6b4d00; --bad-bg: #fde4e1; --bad-fg: #8a1c11;
      --prev-bg: #ece6fb; --prev-fg: #4b2a9a;
      font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--fg);
      background: var(--bg); border-bottom: 1px solid var(--rule);
    }
    @media (prefers-color-scheme: dark) {
      .bar {
        --bg: #1c1c1a; --fg: #e8e7e3; --muted: #9a9993; --rule: #33332f; --accent: #8ab4f8;
        --warn-bg: #3a2f10; --warn-fg: #f5d67a; --bad-bg: #3d1713; --bad-fg: #f7a39a;
        --prev-bg: #2a2140; --prev-fg: #c9b6ff;
      }
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; padding: 6px 16px; }
    .id { font-weight: 600; white-space: nowrap; }
    .site { font-weight: 600; color: var(--fg); white-space: nowrap; }
    .muted { color: var(--muted); }
    .chip { border: 1px solid var(--muted); border-radius: 4px; padding: 0 5px; font-size: 11.5px; color: var(--muted); white-space: nowrap; }
    .chip.verified { border-color: #2e7d4f; color: #2e7d4f; }
    a.chip.warn { background: var(--warn-bg); color: var(--warn-fg); border-color: var(--warn-fg); text-decoration: none; }
    a.chip.warn:hover { text-decoration: underline; }
    .who { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 12rem; }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; }
    button { all: unset; cursor: pointer; color: var(--accent); }
    button:hover { text-decoration: underline; }
    button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .banner { padding: 7px 16px; border-bottom: 1px solid var(--rule); }
    .banner.warn { background: var(--warn-bg); color: var(--warn-fg); }
    .banner.bad { background: var(--bad-bg); color: var(--bad-fg); }
    .banner.preview { background: var(--prev-bg); color: var(--prev-fg); }
    .banner a { color: inherit; text-decoration: underline; }
    .cite { display: none; padding: 4px 16px 12px; }
    .cite.open { display: block; }
    pre { font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--rule);
          color: var(--fg); padding: 8px 10px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; margin: 6px 0; }
    .label { display: flex; justify-content: space-between; align-items: baseline; margin-top: 6px; }
  `;

  class FindingBar extends HTMLElement {
    connectedCallback() {
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>${css}</style>
        <div class="bar" role="banner" aria-label="About this finding">
          ${banner}
          <div class="row">
            <a class="site" href="/">AFH Findings</a>
            <span class="id">${esc(m.id)} · v${m.version}</span>
            ${notice}
            <span class="chip ${m.status === "verified" ? "verified" : ""}">${esc(m.status)}</span>
            <span class="chip">${esc(m.kind)}</span>
            <span class="who">${authorsHtml} <span class="muted">· ${esc(day(m.published))}</span></span>
            <span class="actions">
              ${extras.join("")}
              <button type="button" data-action="cite" aria-expanded="false">Cite</button>
              <a href="${esc(m.about)}">Files &amp; history</a>
              <a href="${esc(m.zip)}" download>Download</a>
              ${feedback ? `<a href="${esc(feedback)}">Report a problem</a>` : ""}
            </span>
          </div>
          <div class="cite" id="cite">
            <div class="label"><span class="muted">Text</span><button type="button" data-copy="text">Copy</button></div>
            <pre>${esc(citeText)}</pre>
            <div class="label"><span class="muted">BibTeX</span><button type="button" data-copy="bibtex">Copy</button></div>
            <pre>${esc(bibtex)}</pre>
          </div>
        </div>`;
      const panel = root.getElementById("cite");
      root.querySelector('[data-action="cite"]').addEventListener("click", (e) => {
        const open = panel.classList.toggle("open");
        e.currentTarget.setAttribute("aria-expanded", String(open));
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

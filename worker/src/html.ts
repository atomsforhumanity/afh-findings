// Shared HTML helpers and the site's look, matched to afh.org: Source Serif 4 headings,
// Source Sans 3 text, Geist Mono for identifiers, the warm paper background, ink and blue,
// and the navy of its footer and dark sections (used here for dark mode).

export function esc(value: unknown): string {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
  );
}

export const day = (iso: string | null | undefined): string => (iso ? iso.slice(0, 10) : "");

export function authorList(authors: { name: string }[]): string {
  const names = authors.map((a) => a.name);
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

export const REPO_URL = "https://github.com/atomsforhumanity/afh-findings";

// The Atoms for Humanity mark, as on afh.org.
export const BRAND_MARK = `<svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true"><g class="orbit"><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(30 32 32)"/><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(-30 32 32)"/><ellipse cx="32" cy="32" rx="25" ry="9" transform="rotate(90 32 32)"/></g><circle class="nucleus" cx="32" cy="32" r="7"/><path class="earth" d="M27 31c4-4 7-2 10-5M27 35c4-2 7 3 11 0"/></svg>`;

export const CSS = `
:root{
--bg:#f8f7f3;--bg-2:#fcfcfa;--ink:#202a33;--ink-2:#4e5e6a;--muted:#5e6d78;--heading:#17324a;
--blue:#3868b8;--blue-light:#7fa6df;--blue-soft:#eaf0f8;--green:#496e5c;--green-soft:#e7efe9;
--border:#d9dee3;--border-strong:#9baec0;--focus:#b1cbef;
--warn-bg:#f7efdc;--warn-fg:#76561a;--warn-line:#dcc48f;--bad-bg:#f7e5e1;--bad-fg:#8a2f22;--bad-line:#e2b0a6;
--navy:#17324a;
--serif:"Source Serif 4 Variable",Georgia,"Times New Roman",serif;
--sans:"Source Sans 3 Variable","Segoe UI",system-ui,sans-serif;
--mono:"Geist Mono Variable",ui-monospace,SFMono-Regular,Menlo,monospace;
--content:1240px;--gutter:clamp(1.25rem,5vw,5rem);--prose:44rem;--list:58rem;
color-scheme:light}
@media (prefers-color-scheme:dark){:root{
--bg:#17324a;--bg-2:#1c3b58;--ink:#f8f7f3;--ink-2:#d3dde7;--muted:#b4c5d5;--heading:#fcfcfa;
--blue:#b1cbef;--blue-light:#7fa6df;--blue-soft:#244868;--green:#a9d3bb;--green-soft:#244a45;
--border:#456077;--border-strong:#6c88a2;--focus:#b1cbef;
--warn-bg:#3e3a25;--warn-fg:#f1d993;--warn-line:#7e6d3b;--bad-bg:#4a2c2c;--bad-fg:#f6b9ae;--bad-line:#8c4b43;
--navy:#10263a;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;min-width:320px;background:var(--bg);color:var(--ink);font:400 1.0625rem/1.65 var(--sans);
text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration-color:var(--blue-light);text-underline-offset:.22em}
a:hover{color:var(--blue)}
:focus-visible{outline:2px solid var(--focus);outline-offset:4px;border-radius:2px}
.wrap{max-width:var(--content);margin:0 auto;padding:0 var(--gutter)}
.skip{position:absolute;left:-999px}.skip:focus{left:1rem;top:1rem;z-index:20;background:var(--bg);padding:.4rem .7rem}

.site-header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--border)}
.site-header .wrap{display:flex;align-items:center;justify-content:space-between;gap:1.5rem;min-height:72px}
.brand{display:inline-flex;align-items:center;gap:.65rem;color:var(--heading);text-decoration:none;white-space:nowrap}
.brand:hover{color:var(--heading)}
.brand-mark{flex:none;width:1.9rem;height:1.9rem;overflow:visible}
.brand-mark .orbit{fill:none;stroke:currentColor;stroke-width:1.5px}
.brand-mark .nucleus{fill:var(--blue)}
.brand-mark .earth{fill:none;stroke:var(--bg);stroke-width:1.4px;stroke-linecap:round}
.wordmark{font-weight:600;font-size:1.15rem;letter-spacing:-.02em}
.section-name{font-weight:500;font-size:1.15rem;color:var(--blue);letter-spacing:-.01em;padding-left:.75rem;border-left:1px solid var(--border-strong)}
.site-nav{display:flex;align-items:center;gap:clamp(.9rem,1.6vw,1.6rem)}
.site-nav a{color:var(--ink-2);font-size:.96rem;font-weight:500;text-decoration:none}
.site-nav a:hover,.site-nav a[aria-current=page]{color:var(--heading);text-decoration:underline;text-decoration-color:var(--blue)}
@media (max-width:720px){.wordmark,.site-nav .wide{display:none}.section-name{border:0;padding:0}}

main{padding:clamp(3rem,7vw,5.5rem) 0 clamp(4rem,8vw,6.5rem)}
.eyebrow{color:var(--blue);font:600 .78rem/1.4 var(--sans);letter-spacing:.09em;text-transform:uppercase;margin:0 0 1.2rem}
.eyebrow .mono{font:500 .82rem/1.4 var(--mono);letter-spacing:.02em;text-transform:none}
h1,h2{color:var(--heading);font-family:var(--serif);font-weight:450;letter-spacing:-.03em;line-height:1.12;text-wrap:balance}
h1{font-size:clamp(2.4rem,5vw,3.9rem);margin:0;max-width:24ch}
h1.long{font-size:clamp(2rem,3.6vw,2.9rem);max-width:28ch}
h2{font-size:clamp(1.6rem,2.6vw,2.1rem);margin:3.2rem 0 1rem}
h3{color:var(--heading);font:600 1.15rem/1.3 var(--sans);letter-spacing:-.01em;margin:2rem 0 .6rem}
.lede{max-width:var(--prose);color:var(--ink-2);font-size:clamp(1.12rem,1.5vw,1.32rem);line-height:1.6;margin:1.4rem 0 0}
.prose{max-width:var(--prose)}
.prose li+li{margin-top:.4rem}
.back{display:inline-block;margin-bottom:2rem;color:var(--ink-2);font-size:.95rem;text-decoration:none}
.back:hover{text-decoration:underline;text-decoration-color:var(--blue)}

.tag{display:inline-flex;align-items:center;gap:.3rem;border:1px solid var(--border-strong);border-radius:3px;
padding:.08rem .45rem;font:600 .7rem/1.5 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.tag.verified{border-color:transparent;background:var(--green-soft);color:var(--green)}
.tag.info{border-color:transparent;background:var(--blue-soft);color:var(--heading)}
.tag.warn{border-color:var(--warn-line);background:var(--warn-bg);color:var(--warn-fg)}
.tag.bad{border-color:var(--bad-line);background:var(--bad-bg);color:var(--bad-fg)}
.notice{max-width:var(--prose);padding:.8rem 1rem;border-radius:3px;margin:0 0 2rem;border:1px solid}
.notice.warn{background:var(--warn-bg);color:var(--warn-fg);border-color:var(--warn-line)}
.notice.bad{background:var(--bad-bg);color:var(--bad-fg);border-color:var(--bad-line)}
.notice a{color:inherit}

.filters{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin:3rem 0 0;max-width:var(--list)}
.filters input[type=search]{flex:1 1 18rem}
.filters input,.filters select{font:inherit;font-size:.95rem;min-height:42px;padding:.45rem .7rem;border:1px solid var(--border-strong);
border-radius:3px;background:var(--bg-2);color:var(--ink)}
.filters label{display:flex;gap:.45rem;align-items:center;font-size:.93rem;color:var(--ink-2)}
.count{color:var(--muted);font-size:.9rem;margin:1.2rem 0 0}
ol.findings{list-style:none;margin:.8rem 0 0;padding:0;max-width:var(--list);border-top:1px solid var(--border)}
ol.findings>li{padding:1.9rem 0;border-bottom:1px solid var(--border)}
.finding-label{display:flex;flex-wrap:wrap;gap:.2rem .7rem;align-items:baseline;color:var(--blue);
font:600 .74rem/1.4 var(--sans);letter-spacing:.09em;text-transform:uppercase;margin-bottom:.55rem}
.finding-label .fid{font:500 .84rem/1.4 var(--mono);letter-spacing:.02em;text-transform:none}
.finding-title{font:450 clamp(1.35rem,2.2vw,1.65rem)/1.25 var(--serif);letter-spacing:-.02em;margin:0;max-width:none;text-wrap:balance}
.finding-title a{text-decoration:none}
.finding-title a:hover{text-decoration:underline;text-decoration-color:var(--blue-light)}
.claim{color:var(--ink-2);margin:.65rem 0 .9rem;max-width:var(--prose);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.meta{display:flex;flex-wrap:wrap;gap:.4rem .9rem;align-items:center;color:var(--muted);font-size:.92rem}
.meta a{color:var(--ink-2)}
li.retracted .finding-title a{text-decoration:line-through;text-decoration-thickness:1px}
li.retracted,li.superseded{opacity:.8}
li.withdrawn{color:var(--muted)}

.table-wrap{overflow-x:auto;max-width:var(--list)}
table{border-collapse:collapse;width:100%;font-size:.96rem}
th,td{text-align:left;vertical-align:top;padding:.65rem 1rem .65rem 0;border-bottom:1px solid var(--border)}
th{color:var(--muted);font:600 .74rem/1.5 var(--sans);letter-spacing:.07em;text-transform:uppercase;white-space:nowrap}
dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:.55rem 1.6rem;max-width:var(--list);margin:2.4rem 0 0;
padding:1.4rem 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
dl.facts dt{color:var(--muted);font:600 .74rem/1.9 var(--sans);letter-spacing:.07em;text-transform:uppercase}
dl.facts dd{margin:0}
@media (max-width:560px){dl.facts{grid-template-columns:1fr;gap:.1rem}dl.facts dd{margin-bottom:.7rem}}
code,.mono{font-family:var(--mono);font-size:.86em}
pre{font:400 .85rem/1.55 var(--mono);background:var(--bg-2);border:1px solid var(--border);border-radius:3px;
padding:.9rem 1rem;white-space:pre-wrap;word-break:break-word;max-width:var(--list)}
.button{display:inline-flex;align-items:center;gap:.6rem;min-height:44px;padding:.65rem 1.1rem;border:1px solid var(--blue);
border-radius:3px;color:var(--heading);font-weight:600;font-size:.98rem;text-decoration:none;background:transparent}
.button:hover{background:var(--blue-soft);color:var(--heading)}
.actions{display:flex;flex-wrap:wrap;gap:.8rem 1.4rem;align-items:center;margin:1.4rem 0}

.site-footer{background:var(--navy);color:#f8f7f3;padding:clamp(3.5rem,6vw,5rem) 0 1.5rem;
--blue:#b1cbef;--bg:var(--navy)}
.site-footer .cols{display:grid;grid-template-columns:minmax(240px,1.6fr) 1fr 1fr;gap:clamp(2rem,4vw,4rem)}
.site-footer .brand{color:#fcfcfa}
.site-footer .tagline{font-family:var(--serif);font-size:1.3rem;line-height:1.5;color:#d3dde7;max-width:22rem;margin:1.3rem 0 0}
.site-footer h2{font:600 .85rem/1.4 var(--sans);letter-spacing:.025em;color:#f8f7f3;margin:.3rem 0 1.2rem}
.site-footer ul{list-style:none;margin:0;padding:0}
.site-footer li+li{margin-top:.6rem}
.site-footer a{color:#d3dde7;text-decoration:none}
.site-footer a:hover{color:#b1cbef;text-decoration:underline}
.footer-bottom{border-top:1px solid #456077;color:#b4c5d5;margin-top:clamp(2.5rem,5vw,4rem);padding-top:1.2rem;
font-size:.85rem;display:flex;flex-wrap:wrap;justify-content:space-between;gap:.5rem 2rem}
@media (max-width:720px){.site-footer .cols{grid-template-columns:1fr 1fr}.site-footer .cols>:first-child{grid-column:1/-1}}
`;

function header(current: string): string {
  const nav = (href: string, label: string, cls = "") =>
    `<a href="${href}"${cls ? ` class="${cls}"` : ""}${current === href ? ' aria-current="page"' : ""}>${label}</a>`;
  return `<header class="site-header"><div class="wrap">
<a class="brand" href="/" aria-label="AFH Findings home">${BRAND_MARK}<span class="wordmark">Atoms for Humanity</span><span class="section-name">Findings</span></a>
<nav class="site-nav" aria-label="Site">
${nav("/", "All findings")}
${nav("/about", "About")}
${nav("/feed.xml", "Feed", "wide")}
<a href="https://www.afh.org" class="wide">afh.org ↗</a>
</nav></div></header>`;
}

function footer(): string {
  const year = new Date().getUTCFullYear();
  return `<footer class="site-footer"><div class="wrap">
<div class="cols">
<div><a class="brand" href="https://www.afh.org">${BRAND_MARK}<span class="wordmark">Atoms for Humanity</span></a>
<p class="tagline">Results from our research, published as we find them.</p></div>
<div><h2>Findings</h2><ul>
<li><a href="/">All findings</a></li><li><a href="/about">About &amp; citing</a></li>
<li><a href="/feed.xml">Atom feed</a></li><li><a href="/index.json">index.json</a> · <a href="/index.csv">csv</a></li>
<li><a href="${REPO_URL}">Source ↗</a></li></ul></div>
<div><h2>Atoms for Humanity</h2><ul>
<li><a href="https://www.afh.org">afh.org ↗</a></li>
<li><a href="https://github.com/atomsforhumanity">GitHub ↗</a></li></ul></div>
</div>
<div class="footer-bottom"><span>© ${year} Atoms for Humanity</span>
<span>Text and figures CC-BY-4.0 · data CC0 unless a finding says otherwise · code MIT</span></div>
</div></footer>`;
}

export function layout(opts: {
  title: string;
  body: string;
  head?: string;
  description?: string;
  current?: string;
}): string {
  const description = opts.description ? `<meta name="description" content="${esc(opts.description)}">` : "";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(opts.title)}</title>
${description}
<link rel="preload" href="/_static/fonts/source-serif-4.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/_static/fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/_static/fonts.css">
<link rel="alternate" type="application/atom+xml" title="AFH Findings" href="/feed.xml">
<link rel="icon" type="image/svg+xml" href="/_static/favicon.svg">
<style>${CSS}</style>
${opts.head ?? ""}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
${header(opts.current ?? "")}
<main id="main"><div class="wrap">
${opts.body}
</div></main>
${footer()}
</body>
</html>`;
}

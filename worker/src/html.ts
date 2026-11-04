// Shared HTML helpers and the site's look: plain, text-first, light and dark.

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

export const CSS = `
:root{--bg:#fdfdfc;--fg:#1d1d1b;--muted:#6b6b66;--rule:#e2e1dc;--accent:#2a5db0;--soft:#f3f2ee;
--good:#2e7d4f;--warn-bg:#fff4d6;--warn-fg:#6b4d00;--bad-bg:#fde4e1;--bad-fg:#8a1c11}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#e8e7e3;--muted:#9a9993;--rule:#33332f;
--accent:#8ab4f8;--soft:#20201e;--good:#6cc193;--warn-bg:#3a2f10;--warn-fg:#f5d67a;--bad-bg:#3d1713;--bad-fg:#f7a39a}}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
max-width:50rem;margin:0 auto;padding:2rem 16px 4rem}
a{color:var(--accent)}
h1{font-size:1.6rem;line-height:1.25;margin:.2rem 0 .6rem}
h2{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid var(--rule);padding-bottom:.2rem}
.muted{color:var(--muted)}
.lede{max-width:40rem}
.nav{display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.92rem;margin:.6rem 0 1.4rem}
.chip{display:inline-block;border:1px solid var(--muted);border-radius:4px;padding:0 .35rem;font-size:.75rem;
color:var(--muted);line-height:1.5;white-space:nowrap}
.chip.verified{border-color:var(--good);color:var(--good)}
.chip.change-corrected,.chip.change-weakened{border-color:var(--warn-fg);color:var(--warn-fg);background:var(--warn-bg)}
.notice{padding:.6rem .9rem;border-radius:4px;margin:1rem 0}
.notice.warn{background:var(--warn-bg);color:var(--warn-fg)}
.notice.bad{background:var(--bad-bg);color:var(--bad-fg)}
table{border-collapse:collapse;width:100%;font-size:.9rem;display:block;overflow-x:auto}
td,th{border-bottom:1px solid var(--rule);padding:.35rem .5rem;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:500}
code,pre{font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--soft);padding:.7rem .9rem;border-radius:4px;white-space:pre-wrap;word-break:break-word}
.filters{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 .4rem}
.filters input[type=search]{flex:1 1 16rem}
.filters input,.filters select{font:inherit;font-size:.92rem;padding:.3rem .45rem;border:1px solid var(--rule);
border-radius:4px;background:var(--bg);color:var(--fg)}
.filters label{font-size:.9rem;color:var(--muted);display:flex;align-items:center;gap:.3rem}
ol.findings{list-style:none;padding:0;margin:0}
ol.findings li{padding:1rem 0;border-bottom:1px solid var(--rule)}
ol.findings li.retracted .title{text-decoration:line-through;text-decoration-thickness:1px}
ol.findings li.retracted,ol.findings li.superseded{opacity:.75}
.fid{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85rem;color:var(--muted);margin-right:.4rem}
.title{font-weight:600;font-size:1.05rem;text-decoration:none}
.title:hover{text-decoration:underline}
.claim{margin:.3rem 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{font-size:.85rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:.2rem .7rem;align-items:center}
.count{font-size:.85rem;color:var(--muted);margin:.4rem 0}
footer{margin-top:3rem;font-size:.85rem;color:var(--muted)}
`;

export function layout(opts: { title: string; body: string; head?: string; description?: string }): string {
  const description = opts.description ? `<meta name="description" content="${esc(opts.description)}">` : "";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(opts.title)}</title>
${description}
<link rel="alternate" type="application/atom+xml" title="AFH Findings" href="/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='5' fill='%232a5db0'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='5.5' fill='none' stroke='%232a5db0' stroke-width='2'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='5.5' fill='none' stroke='%232a5db0' stroke-width='2' transform='rotate(60 16 16)'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='5.5' fill='none' stroke='%232a5db0' stroke-width='2' transform='rotate(120 16 16)'/%3E%3C/svg%3E">
<style>${CSS}</style>
${opts.head ?? ""}
</head>
<body>
${opts.body}
</body>
</html>`;
}

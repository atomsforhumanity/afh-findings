"""What gets added to every published HTML page.

The Worker and `afh-findings preview` add the same three things to a page's <head>:
citation meta tags, a JSON description of the finding, and /_static/bar.js, which draws
the header bar (ID, version, status, cite, files, warnings about old or retracted
versions) in a Shadow DOM so it can't clash with the page's own styles.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any


def meta(
    manifest: dict[str, Any],
    *,
    latest: int,
    latest_change: dict[str, str] | None = None,
    latest_published: str | None = None,
    state: str = "active",
    state_reason: str | None = None,
    state_date: str | None = None,
    superseded_by: str | None = None,
    doi: str | None = None,
    stacks_url: str | None = None,
    first_published: str | None = None,
    feedback_url: str | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    fid, v = manifest["id"], manifest["version"]
    archive = f"{fid}-v{v}.zip"
    return {
        "id": fid,
        "version": v,
        "latest": latest,
        "title": manifest["title"],
        "authors": [{k: a[k] for k in ("name", "orcid") if k in a} for a in manifest["authors"]],
        "kind": manifest["kind"],
        "project": manifest["project"],
        "status": manifest["status"],
        "published": manifest["published"],
        "first_published": first_published or manifest["published"],
        "license": manifest.get("license"),
        "state": state,
        "state_reason": state_reason,
        "state_date": state_date,
        "superseded_by": superseded_by,
        "doi": doi,
        "stacks_url": stacks_url,
        "latest_change": latest_change,
        "latest_published": latest_published,
        "private_code": manifest.get("private_code", []),
        "version_url": f"/{fid}/v{v}/",
        "latest_url": f"/{fid}/",
        "about": f"/{fid}/v{v}/_about",
        "zip": f"/{fid}/v{v}/{archive}",
        "feedback_url": feedback_url,
        "preview": preview,
    }


def head_html(m: dict[str, Any], site_url: str, canonical_path: str) -> str:
    def tag(name: str, content: str) -> str:
        return f'<meta name="{name}" content="{html.escape(content, quote=True)}">'

    parts = [f'<link rel="canonical" href="{html.escape(site_url + canonical_path, quote=True)}">']
    parts.append(tag("citation_title", m["title"]))
    for a in m["authors"]:
        parts.append(tag("citation_author", a["name"]))
    parts.append(tag("citation_publication_date", m["first_published"][:10].replace("-", "/")))
    parts.append(tag("citation_online_date", m["published"][:10].replace("-", "/")))
    parts.append(tag("citation_technical_report_institution", "Atoms for Humanity"))
    parts.append(tag("citation_technical_report_number", f"{m['id']} v{m['version']}"))
    if m.get("doi"):
        parts.append(tag("citation_doi", m["doi"]))
    data = json.dumps(m, ensure_ascii=False).replace("<", "\\u003c")
    parts.append(f'<script type="application/json" id="afh-finding">{data}</script>')
    parts.append('<script src="/_static/bar.js" defer></script>')
    return "".join(parts)


_TITLE_END = re.compile(r"</title\s*>", re.I)
_HEAD_END = re.compile(r"</head\s*>", re.I)
_BODY_START = re.compile(r"<body[\s>]", re.I)


def inject(page: str, head: str) -> str:
    """Put `head` after </title>, else before </head>, else before <body>, else at the end."""
    for pattern, after in ((_TITLE_END, True), (_HEAD_END, False), (_BODY_START, False)):
        m = pattern.search(page)
        if m:
            at = m.end() if after else m.start()
            return page[:at] + head + page[at:]
    return page + head

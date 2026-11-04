"""Check the links inside a bundle's HTML pages.

Rules: relative links must stay inside the bundle and point at something that exists;
links to other findings are site-absolute and pinned to a version (/F0001/v3/...);
scripts and stylesheets from other sites work today but break offline, so they warn.
"""

from __future__ import annotations

import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from afh_findings.issues import Issue, error, warning

URL_ATTRS = {
    "a": "href",
    "link": "href",
    "script": "src",
    "img": "src",
    "iframe": "src",
    "source": "src",
    "video": "src",
    "audio": "src",
    "embed": "src",
    "track": "src",
    "object": "data",
}
FINDING_LINK = re.compile(r"^/F\d{4}(/v\d+)?(/|$)")
PINNED = re.compile(r"^/F\d{4}/v\d+(/|$)")
SITE_PAGES = {"/", "/about", "/feed.xml", "/index.json", "/index.csv"}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str, int]] = []  # (tag, url, line)
        self.stylesheets: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = URL_ATTRS.get(tag)
        if not attr:
            return
        values = dict(attrs)
        url = values.get(attr)
        if not url:
            return
        kind = tag
        if tag == "link":
            rel = (values.get("rel") or "").lower().split()
            if "stylesheet" in rel:
                kind = "stylesheet"
            elif rel and set(rel) <= {"preconnect", "dns-prefetch", "canonical", "alternate"}:
                return
        self.refs.append((kind, url.strip(), self.getpos()[0]))


def html_refs(text: str) -> list[tuple[str, str, int]]:
    parser = _Collector()
    parser.feed(text)
    parser.close()
    return parser.refs


def check(bundle_dir: Path, files: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    # Files the tool adds at publish, and the generated About page, are valid targets.
    present = set(files) | {"LICENSE.md", "SHA256SUMS", "finding.json", "_about"}
    dirs = {posixpath.dirname(f) for f in files}
    for d in list(dirs):
        while d:
            d = posixpath.dirname(d)
            dirs.add(d)
    for rel in files:
        if not rel.lower().endswith((".html", ".htm")):
            continue
        text = (bundle_dir / rel).read_text(encoding="utf-8", errors="replace")
        base = posixpath.dirname(rel)
        for kind, url, line in html_refs(text):
            where = f"{rel}:{line}"
            if "{{" in url:
                continue
            parts = urlsplit(url)
            if parts.scheme in ("mailto", "tel", "javascript", "data", "blob"):
                continue
            if parts.scheme in ("http", "https") or url.startswith("//"):
                if kind in ("script", "stylesheet"):
                    issues.append(
                        warning(
                            "external",
                            f"{kind} loaded from {parts.netloc}; copy it into the bundle so"
                            " the page works offline and in archives",
                            where,
                        )
                    )
                continue
            if parts.scheme:
                continue
            path = unquote(parts.path)
            if not path:
                continue  # "#anchor" or "?query"
            if path.startswith("/"):
                if FINDING_LINK.match(path):
                    if not PINNED.match(path):
                        issues.append(
                            warning(
                                "unpinned",
                                f"{url} follows the latest version; pin it as /Fnnnn/vN/ if"
                                " this page depends on what it says now",
                                where,
                            )
                        )
                elif path.rstrip("/") not in {p.rstrip("/") for p in SITE_PAGES}:
                    issues.append(warning("absolute", f"{url} points outside this finding", where))
                continue
            target = posixpath.normpath(posixpath.join(base, path))
            if target == ".." or target.startswith("../"):
                issues.append(
                    error(
                        "outside",
                        f"{url} leaves the bundle; link other findings as /Fnnnn/vN/... and"
                        " anything else by full URL",
                        where,
                    )
                )
                continue
            if target == ".":
                continue
            if target not in present and target not in dirs:
                issues.append(
                    error("broken", f"{url} points at a file that is not in the bundle", where)
                )
    return issues

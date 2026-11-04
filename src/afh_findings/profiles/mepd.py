"""mepd findings: reaction-path results with their level of theory, sampling and report layout.

Adapted from the rules Jan Estrada Pabon built for mepd-findings:
- the page has Background, Approach, Results and Details sections, and Background
  links out for readers who need more;
- the scope says the level of theory, the software and how the tested items were chosen;
- every upstream dataset or program has a DOI or URL and a license;
- tables are plain .csv, not .csv.gz (macOS Archive Utility misreads gzipped CSV).
"""

from __future__ import annotations

from html.parser import HTMLParser

from afh_findings import manifest as mf
from afh_findings.issues import Issue, error

NAME = "mepd"
NAMESPACE = "mepd"
REQUIRES = ["reproducible"]
SECTIONS = ["Background", "Approach", "Results", "Details"]
SCHEMA = {
    "type": "object",
    "required": ["level_of_theory", "software", "sampling"],
    "properties": {
        "level_of_theory": {"type": "string", "minLength": 2},
        "software": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "sampling": {
            "description": "How the tested items were chosen, and the bias that implies.",
            "type": "string",
            "minLength": 10,
        },
        "chemical_domain": {"type": "string"},
        "settings": {"type": "object"},
    },
}


class _Sections(HTMLParser):
    """Collect h2 headings and whether each section has an external link."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self.external_links: dict[str, int] = {}
        self._in_h2 = False
        self._text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self._in_h2, self._text = True, ""
        elif tag == "a" and self.headings:
            href = dict(attrs).get("href") or ""
            if href.startswith(("http://", "https://")):
                current = self.headings[-1]
                self.external_links[current] = self.external_links.get(current, 0) + 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._in_h2:
            self._in_h2 = False
            self.headings.append(" ".join(self._text.split()))

    def handle_data(self, data: str) -> None:
        if self._in_h2:
            self._text += data


def check(source: mf.Source, files: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    entry = source.core.get("entry", mf.DEFAULT_ENTRY)
    if entry in files and entry.endswith((".html", ".htm")):
        parser = _Sections()
        parser.feed((source.bundle_dir / entry).read_text(encoding="utf-8", errors="replace"))
        found = {h.lower(): h for h in parser.headings}
        for name in SECTIONS:
            if name.lower() not in found:
                issues.append(error(NAME, f"the page needs a <h2>{name}</h2> section", entry))
        background = found.get("background")
        if background and not parser.external_links.get(background):
            issues.append(
                error(
                    NAME,
                    "Background needs at least one link for readers outside the project",
                    entry,
                )
            )
    for u in source.core.get("upstream", []) or []:
        if not isinstance(u, dict):
            continue
        if not (u.get("doi") or u.get("url")):
            issues.append(
                error(NAME, f"upstream {u.get('name')!r} needs a doi or url", mf.SOURCE_NAME)
            )
        if not u.get("license"):
            issues.append(
                error(NAME, f"upstream {u.get('name')!r} needs a license", mf.SOURCE_NAME)
            )
    for rel in files:
        if rel.startswith("data/") and rel.endswith(".csv.gz"):
            issues.append(
                error(
                    NAME,
                    "ship tables as plain .csv, or .csv.zip if too big (Archive Utility misreads .csv.gz)",
                    rel,
                )
            )
    return issues

"""Move Jan Estrada Pabon's mepd findings from public.afh.org to findings.afh.org.

Kept as the record of exactly what changed in the move.

    # 1. Build one bundle per published version, with a finding.yaml for each.
    uv run python scripts/migrations/mepd_findings_2026_11.py prepare BUNDLES YAMLS OUT
    # 2. Publish them, in order, with their original dates.
    AFH_FINDINGS_BUCKET=afh-findings-test uv run python scripts/migrations/mepd_findings_2026_11.py publish OUT

BUNDLES holds the published files of each version, OLD_ID/vN/ (the pages and files from
public.afh.org/reports/jan/mepd-findings/, merged with each version's zip and checked
against its published SHA256SUMS). YAMLS holds Jan's finding.yaml from his repo at the
commits that carried each version, OLD_ID/vN/<date>_<commit>.yaml.

What changes, and nothing else:
- Numbers: the six published findings are renumbered in order (F0002 was never published).
  Mentions in pages and READMEs are renumbered; code is left byte for byte as published.
- Links: back-links to the old index and versions, the old zip name, and the mepd manual
  (which the pages linked outside the bundle, where it was never published; the bundles
  carry a copy) point at their new addresses. Links to large files that were never
  published with an older version are removed, keeping their text. "Related Fnnnn"
  lines become links, pinned to the version that was current then.
- Records: each version gets a finding.yaml built from Jan's record for that version.
- Status: a version whose published check.py does not pass on its published files moves
  over as preliminary, without a check (old F0003 v1: its expected_numbers.json carries 16
  numbers of the then-unfinished version 2).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

OLD_TO_NEW = {
    "F0001": "F0001",
    "F0003": "F0002",
    "F0004": "F0003",
    "F0005": "F0004",
    "F0006": "F0005",
    "F0007": "F0006",
}
KIND = {"F0001": "resource"}  # a benchmark set; the others are results
OLD_BASE = "https://public.afh.org/reports/jan/mepd-findings"
AUTHOR = {"name": "Jan Estrada Pabon", "orcid": "0000-0002-8063-8623"}
RENUMBER_SUFFIXES = {".html", ".md"}
ID = re.compile(r"\bF000(\d)\b")


def renumber_text(text: str) -> str:
    text = re.sub(r"\bF0002 \(in preparation\)", "a later finding (in preparation)", text)
    return ID.sub(lambda m: OLD_TO_NEW.get(m.group(0), m.group(0)), text)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def page_claim(html: str) -> str:
    m = re.search(r"<blockquote>\s*<p>\s*<strong>Finding\.</strong>(.*?)</p>", html, re.S)
    return norm(m.group(1)) if m else ""


def pick_yaml(candidates: list[Path], html: str) -> tuple[dict[str, Any], Path, bool]:
    """The record whose claim matches the published page; else the latest one."""
    claim = page_claim(html)
    parsed = [(p, yaml.safe_load(p.read_text())) for p in sorted(candidates)]
    for p, d in reversed(parsed):
        if norm(str(d.get("claim", ""))) == claim:
            return d, p, True
    return parsed[-1][1], parsed[-1][0], False


def version_dates(records: dict[str, dict[int, dict[str, Any]]]) -> dict[str, dict[int, str]]:
    """Publication date of every version, from the newest record's history."""
    dates: dict[str, dict[int, str]] = {}
    for old, versions in records.items():
        newest = versions[max(versions)]
        dates[old] = {int(h["version"]): str(h["date"]) for h in newest.get("history", [])}
        for v in versions:
            dates[old].setdefault(v, str(newest.get("context", {}).get("date", "2026-10-01")))
    return dates


def pinned(old_ref: str, on_date: str, dates: dict[str, dict[int, str]]) -> str | None:
    """New-ID reference to the version of old_ref that was current on on_date."""
    if old_ref not in OLD_TO_NEW or old_ref not in dates:
        return None
    current = [v for v, d in dates[old_ref].items() if d <= on_date]
    return f"{OLD_TO_NEW[old_ref]}/v{max(current) if current else 1}"


def rewrite_links(
    html: str,
    *,
    old: str,
    new: str,
    version: int,
    latest: int,
    bundle: Path,
    rel_dir: str,
    on_date: str,
    dates: dict[str, dict[int, str]],
) -> str:
    is_latest_page = version == latest and rel_dir == ""

    def fix(m: re.Match[str]) -> str:
        attr, url = m.group(1), m.group(2)
        path, _, frag = url.partition("#")
        frag = f"#{frag}" if frag else ""
        if rel_dir == "":
            if path == "../":
                return f'{attr}="/"'
            if path == "../../":
                return f'{attr}="/"'
            if re.fullmatch(r"v\d+/", path):
                return f'{attr}="/{new}/{path}"'
            if path == f"{old}.zip":
                return f'{attr}="{{{{FINDING_ID}}}}-v{{{{FINDING_VERSION}}}}.zip"'
            if path.startswith("../manual/channels.html"):
                copy = "reproduce/mepd-manual-channels.html"
                if (bundle / copy).exists():
                    return f'{attr}="{copy}{frag}"'
        return m.group(0)

    html = re.sub(r'\b(href|src)="([^"]*)"', fix, html)
    if not is_latest_page and rel_dir == "":
        # On an older version's page, "../" meant the latest version; it now means the list.
        pass

    # Links to large files that were never published with this version: keep the text.
    def drop_missing(m: re.Match[str]) -> str:
        target = m.group(1)
        return m.group(0) if (bundle / target).exists() else m.group(2)

    html = re.sub(r'<a href="(data/large/[^"#]+)">(.*?)</a>', drop_missing, html, flags=re.S)

    # "Related Fnnnn" lines become links to the version current at the time.
    def related(m: re.Match[str]) -> str:
        ref = pinned(m.group(1), on_date, dates)
        return f'<li>Related <a href="/{ref}/">{ref.split("/")[0]}</a></li>' if ref else m.group(0)

    return re.sub(r"<li>Related (F\d{4})</li>", related, html)


def old_page_backlinks(html: str, new: str) -> str:
    """Older versions' pages: '../' was the latest version, '../../' the list."""
    html = html.replace('href="../../"', 'href="/"')
    return html.replace('href="../"', f'href="/{new}/"')


def materials(record: dict[str, Any], bundle: Path) -> tuple[list[Any], list[Any]]:
    data = []
    for f in record.get("evidence", {}).get("files", []) or []:
        path = f.get("path") if isinstance(f, dict) else f
        if path and (bundle / path).exists():
            item = {"path": path}
            if isinstance(f, dict) and f.get("description"):
                item["description"] = " ".join(str(f["description"]).split())
            data.append(item)
    if not data and (bundle / "data").is_dir():
        data = [{"path": "data/"}]
    code: list[Any] = [p for p in ("check.py", "reproduce/") if (bundle / p.rstrip("/")).exists()]
    for c in record.get("reproduce", {}).get("code", []) or []:
        if (
            isinstance(c, dict)
            and c.get("repo", "").startswith("https://github.com/")
            and c.get("commit")
        ):
            repo = c["repo"].removesuffix(".git")
            code.append(f"{repo}@{c['commit']}")
    return data, code


def upstream_and_links(
    record: dict[str, Any], old: str, on_date: str, dates
) -> tuple[list[Any], list[str]]:
    upstream, builds_on = [], []
    for u in record.get("upstream", []) or []:
        url = str(u.get("url", "") or "")
        m = re.match(r"findings/(F\d{4})-", url) or re.match(r"(F\d{4})\b", str(u.get("name", "")))
        if m and m.group(1) in OLD_TO_NEW:
            if m.group(1) != old and (ref := pinned(m.group(1), on_date, dates)):
                builds_on.append(ref)
            continue
        if m:  # an unpublished finding (F0002)
            continue
        item: dict[str, Any] = {"name": renumber_text(str(u.get("name", "")))}
        doi = u.get("doi") or (
            url.removeprefix("https://doi.org/") if url.startswith("https://doi.org/") else None
        )
        if doi:
            item["doi"] = doi
        elif url:
            item["url"] = url
        if u.get("license"):
            item["license"] = u["license"]
        note = {
            "references": "reference",
            "isDerivedFrom": "data this builds on",
            "requires": "software used",
        }.get(str(u.get("relation", "")))
        if note:
            item["note"] = note
        upstream.append(item)
    for key in ("refines", "related"):
        for ref in record.get(key, []) or []:
            if ref != old and (p := pinned(ref, on_date, dates)) and p not in builds_on:
                builds_on.append(p)
    return upstream, sorted(set(builds_on))


def mepd_block(record: dict[str, Any]) -> dict[str, Any]:
    scope = record.get("scope", {}) or {}
    software = scope.get("software", {})
    if isinstance(software, dict):
        software = [f"{k}: {v}" for k, v in software.items()]
    sampling = (scope.get("tested_on") or {}).get("sampling") or "Not recorded for this version."
    block: dict[str, Any] = {
        "level_of_theory": " ".join(str(scope.get("level_of_theory", "not recorded")).split()),
        "software": [renumber_text(str(s)) for s in software] or ["not recorded"],
        "sampling": renumber_text(" ".join(str(sampling).split())),
    }
    domain = scope.get("chemical_domain")
    if isinstance(domain, dict) and domain.get("dataset"):
        block["chemical_domain"] = renumber_text(str(domain["dataset"]))
    elif isinstance(domain, str):
        block["chemical_domain"] = renumber_text(domain)
    if isinstance(scope.get("settings"), dict):
        block["settings"] = {k: renumber_text(str(v)) for k, v in scope["settings"].items()}
    return block


def original_check_passes(published: Path) -> bool:
    """Run the version's check.py on a fresh copy of its files exactly as published."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "bundle"
        shutil.copytree(published, work, ignore=shutil.ignore_patterns(".jan-SHA256SUMS"))
        proc = subprocess.run(
            [sys.executable, "-I", "check.py"], cwd=work, capture_output=True, timeout=1800
        )
        return proc.returncode == 0


def prepare(bundles: Path, yamls: Path, out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    records: dict[str, dict[int, dict[str, Any]]] = {}
    chosen: dict[tuple[str, int], tuple[dict[str, Any], Path, bool]] = {}
    for old in OLD_TO_NEW:
        for vdir in sorted((bundles / old).glob("v*"), key=lambda p: int(p.name[1:])):
            v = int(vdir.name[1:])
            html = (vdir / "index.html").read_text()
            rec = pick_yaml(list((yamls / old / f"v{v}").glob("*.yaml")), html)
            chosen[(old, v)] = rec
            records.setdefault(old, {})[v] = rec[0]
    dates = version_dates(records)
    plan = []
    for old, new in OLD_TO_NEW.items():
        latest = max(records[old])
        for v in sorted(records[old]):
            record, source, exact = chosen[(old, v)]
            src = bundles / old / f"v{v}"
            dst = out / new / f"v{v}"
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".jan-SHA256SUMS"))
            on_date = dates[old][v]
            for p in dst.rglob("*"):
                if not p.is_file() or p.suffix not in RENUMBER_SUFFIXES:
                    continue
                text = p.read_text()
                rel_dir = str(p.parent.relative_to(dst)) if p.parent != dst else ""
                if p.suffix == ".html":
                    text = rewrite_links(
                        text,
                        old=old,
                        new=new,
                        version=v,
                        latest=latest,
                        bundle=dst,
                        rel_dir=rel_dir,
                        on_date=on_date,
                        dates=dates,
                    )
                    if v != latest and rel_dir == "":
                        text = old_page_backlinks(text, new)
                    text = text.replace(f"{old}.zip", "{{FINDING_ID}}-v{{FINDING_VERSION}}.zip")
                p.write_text(renumber_text(text))
            check_ok = (dst / "check.py").exists() and original_check_passes(src)
            data, code = materials(record, dst)
            upstream, builds_on = upstream_and_links(record, old, on_date, dates)
            scope = record.get("scope", {}) or {}
            core: dict[str, Any] = {
                "title": renumber_text(" ".join(str(record["title"]).split())),
                "claim": renumber_text(" ".join(str(record["claim"]).split())),
                "authors": [AUTHOR],
                "project": "mepd",
                "kind": KIND.get(old, "result"),
                "status": record.get("status", "preliminary") if check_ok else "preliminary",
                "keywords": record.get("keywords", []),
                "scope": {
                    "not_tested": [
                        renumber_text(" ".join(str(t).split())) for t in scope.get("not_tested", [])
                    ]
                    or ["Not recorded for this version."]
                },
                "data": data or {"none": "No data files were published with this version."},
                "code": code or {"none": "No code was published with this version."},
                "upstream": upstream,
                "builds_on": builds_on,
                "formerly": [
                    f"{old} version {v}",
                    f"{OLD_BASE}/{old}/" + ("" if v == latest else f"v{v}/"),
                ],
                "check": "python3 -I check.py" if check_ok else None,
                "license": {"text": "CC-BY-4.0", "data": "CC-BY-4.0", "code": "MIT"},
                # Run hosts recorded in the input archives; already public, and harmless.
                "privacy_allow": ["afh-c01"],
                "mepd": mepd_block(record),
                "private": {
                    "migrated_from": f"{old} v{v}",
                    "jan_record": source.name,
                    "claim_matched_page": exact,
                    "published_check_passes": check_ok,
                },
            }
            core = {k: val for k, val in core.items() if val not in (None, [])}
            (dst / "finding.yaml").write_text(
                yaml.safe_dump(core, sort_keys=False, allow_unicode=True, width=100)
            )
            change = None
            if v > 1:
                h = next((h for h in record.get("history", []) if int(h["version"]) == v), {})
                kind = (
                    h.get("change")
                    if h.get("change")
                    in ("corrected", "expanded", "strengthened", "weakened", "revised")
                    else "revised"
                )
                change = {
                    "type": kind,
                    "summary": renumber_text(" ".join(str(h.get("summary", "Updated.")).split())),
                }
            plan.append(
                {
                    "old": old,
                    "new": new,
                    "version": v,
                    "dir": str(dst),
                    "published_at": f"{on_date}T12:{v:02d}:00Z",
                    "change": change,
                    "claim_matched_page": exact,
                    # Without a passing check the mepd rules can't be met; record core-only instead.
                    "skip_profiles": not check_ok,
                }
            )
            print(
                f"{old} v{v} -> {new} v{v}  {on_date}  record {source.name}{'' if exact else '  (claim differs from page!)'}"
                f"{'' if check_ok else '  (published check fails: preliminary)'}"
            )
    (out / "plan.json").write_text(json.dumps(plan, indent=1))


def publish_all(out: Path, yes: bool) -> None:
    from afh_findings import config, publish, registry
    from afh_findings.store import open_store

    cfg = config.load()
    cfg.publisher = "Jan Estrada Pabon"
    store = open_store(cfg)
    plan = json.loads((out / "plan.json").read_text())
    print(f"publishing {len(plan)} versions to {store.describe()}")
    index, _ = registry.load(store)
    for step in plan:
        f = index["findings"].get(step["new"])
        if f and step["version"] in {x["version"] for x in f["versions"]}:
            print(f"  {step['new']} v{step['version']} already published; skipping")
            continue
        result = publish.publish(
            Path(step["dir"]),
            cfg,
            store,
            revise=step["new"] if step["version"] > 1 else None,
            change=step["change"],
            published_at=step["published_at"],
            confirm=lambda s: yes,
            log=lambda m: None,
            skip_profiles=step.get("skip_profiles", False),
        )
        if (result.finding_id, result.version) != (step["new"], step["version"]):
            sys.exit(
                f"expected {step['new']} v{step['version']}, got {result.finding_id} v{result.version}; stopping"
            )
        print(f"  {step['old']} v{step['version']} -> {result.url}")
        index, _ = registry.load(store)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif sys.argv[1] == "publish":
        publish_all(Path(sys.argv[2]), "--yes" in sys.argv)
    else:
        sys.exit(__doc__)

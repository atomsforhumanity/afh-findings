"""Publish sample findings with the real publisher and dump the bucket for the Worker tests.

    uv run python scripts/make_worker_fixture.py worker/test/fixtures/bucket.json

The Worker tests load this into their local R2, so they serve exactly what the CLI writes.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

from afh_findings import publish
from afh_findings.config import Config
from afh_findings.store import FileStore

YAML = """\
title: {title}
claim: >
  {claim}
authors:
  - name: Ada Example
    orcid: 0000-0002-1825-0097
  - name: Grace Sample
project: {project}
kind: {kind}
status: preliminary
keywords: [fixture]
scope:
  not_tested: [Anything outside this fixture]
data:
  - path: data/results.csv
code:
  - path: reproduce/
upstream:
  - name: Example dataset
    doi: 10.5281/zenodo.0000000
    license: CC-BY-4.0
{extra}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{{{{FINDING_ID}}}}: {title}</title>
<style>body{{font-family:serif}}</style></head>
<body><h1>{{{{FINDING_ID}}}} version {{{{FINDING_VERSION}}}}: {title}</h1>
<p>{body}</p><p><a href="data/results.csv">data</a> · <a href="reproduce/">scripts</a></p></body></html>
"""

# A page with no <head> or <body> tags, like some hand-written ones.
BARE_PAGE = """<!doctype html><html lang=en><meta charset=utf-8><title>Bare</title>
<p>No head tag. <a href="data/results.csv">data</a> <a href="reproduce/">scripts</a></p>
"""


def bundle(
    root: Path,
    *,
    title: str,
    claim: str,
    body: str,
    project: str = "infrastructure",
    kind: str = "result",
    extra: str = "",
    page: str | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "finding.yaml").write_text(
        YAML.format(title=title, claim=claim, project=project, kind=kind, extra=extra)
    )
    (root / "index.html").write_text(page or PAGE.format(title=title, body=body))
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "results.csv").write_text("molecule,cpu_s,gpu_s\nA,120,20\nB,900,150\n")
    (root / "reproduce" / "inputs").mkdir(parents=True, exist_ok=True)
    (root / "reproduce" / "run.py").write_text("print('rerun')\n")
    (root / "reproduce" / "inputs" / "mol.xyz").write_text("1\nH atom\nH 0 0 0\n")
    (root / "data" / "blob.bin").write_bytes(bytes(range(256)) * 8)
    return root


def main(out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        store = FileStore(t / "store")
        cfg = Config(store=f"file:{store.root}", publisher="Ada Example")
        quiet = {"network": False, "log": lambda _m: None}

        a = bundle(
            t / "a",
            title="GPU single points cost six times less than CPU ones on our hardware",
            claim="Median 6.1 times cheaper for 12 molecules of 50 to 200 atoms.",
            body="First version.",
        )
        publish.publish(a, cfg, store, published_at="2026-10-01T10:00:00Z", **quiet)
        (a / "index.html").write_text(
            PAGE.format(title="GPU single points cost 5.8x less", body="Corrected.")
        )
        publish.publish(
            a,
            cfg,
            store,
            revise="F0001",
            published_at="2026-10-05T10:00:00Z",
            change={"type": "corrected", "summary": "A timing counted twice"},
            **quiet,
        )

        b = bundle(
            t / "b",
            title="An unguided explorer finds both Diels-Alder diastereomers here",
            claim="Given only the two reactants, the explorer found endo and exo adducts.",
            body="Explorer.",
            project="mepd-demo",
            extra="builds_on: [F0001/v1]",
            page=BARE_PAGE,
        )
        publish.publish(b, cfg, store, published_at="2026-10-10T10:00:00Z", **quiet)

        c = bundle(
            t / "c",
            title="A screening shortcut that turned out to be wrong in general",
            claim="Skipping the IRC check looked safe on 50 reactions but was wrong.",
            body="Retracted.",
            kind="informative-failure",
        )
        publish.publish(c, cfg, store, published_at="2026-10-12T10:00:00Z", **quiet)
        publish.set_status(
            store,
            "F0003",
            "retract",
            reason="The benchmark set was mislabelled",
            at="2026-10-20T10:00:00Z",
        )

        d = bundle(
            t / "d",
            title="A result whose files should never have been public at all",
            claim="These numbers came from a partner and were not ours to share.",
            body="Withdrawn.",
        )
        publish.publish(d, cfg, store, published_at="2026-10-15T10:00:00Z", **quiet)
        publish.set_status(
            store, "F0004", "withdraw", reason="Contained partner data", at="2026-10-16T10:00:00Z"
        )
        publish.set_status(
            store,
            "F0001",
            "link",
            stacks_url="https://thestacks.org/publications/x",
            at="2026-10-21T10:00:00Z",
        )

        dump = {}
        for key in store.list(""):
            dump[key] = {
                "content_type": store.content_type(key) or "application/octet-stream",
                "data": base64.b64encode((store.root / key).read_bytes()).decode(),
            }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dump, indent=0, sort_keys=True))
    print(f"wrote {len(dump)} objects to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("worker/test/fixtures/bucket.json"))

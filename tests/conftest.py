from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from afh_findings.config import Config
from afh_findings.store import FileStore

FINDING_YAML = """\
title: GPU DFT costs six times less than CPU DFT per single point on our hardware
claim: >
  For 12 molecules of 50 to 200 atoms, one wB97X-D3/def2-TZVP single point cost a median
  of 6.1 times less on one GPU than on 32 CPU cores.
authors:
  - name: Ada Example
    orcid: 0000-0002-1825-0097
project: infrastructure
kind: result
status: preliminary
keywords: [cost, gpu]
scope:
  not_tested:
    - Systems over 200 atoms
data:
  - path: data/results.csv
    description: one row per calculation
code:
  - path: reproduce/
upstream: []
private:
  notes: the run lived on a scratch disk
"""

PAGE = """\
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{{FINDING_ID}}: GPU costs less</title></head>
<body>
<h1>{{FINDING_ID}} v{{FINDING_VERSION}}</h1>
<p>Data: <a href="data/results.csv">results</a>, scripts: <a href="reproduce/">reproduce</a>.</p>
</body></html>
"""


def make_bundle(
    root: Path,
    *,
    yaml_text: str = FINDING_YAML,
    page: str = PAGE,
    extra: dict[str, str] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "finding.yaml").write_text(textwrap.dedent(yaml_text))
    (root / "index.html").write_text(page)
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "results.csv").write_text(
        "molecule,atoms,cpu_s,gpu_s\nA,50,120,20\nB,200,900,150\n"
    )
    (root / "reproduce").mkdir(exist_ok=True)
    (root / "reproduce" / "run.py").write_text("print('rerun')\n")
    for rel, text in (extra or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    return make_bundle(tmp_path / "bundle")


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(
        store=f"file:{tmp_path / 'store'}", publisher="Ada Example", internal_hosts=["secret-host"]
    )


@pytest.fixture
def store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "store")

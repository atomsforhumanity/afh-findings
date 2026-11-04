from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from conftest import FINDING_YAML, make_bundle

from afh_findings import bundle, checks, publish, registry
from afh_findings.store import FileStore, PreconditionFailed


def pub(bundle_dir, cfg, store, **kw):
    return publish.publish(bundle_dir, cfg, store, network=False, log=lambda _m: None, **kw)


def test_publish_numbers_and_files(bundle_dir, cfg, store):
    r1 = pub(bundle_dir, cfg, store)
    r2 = pub(bundle_dir, cfg, store)
    assert (r1.finding_id, r1.version, r2.finding_id) == ("F0001", 1, "F0002")
    index, _ = registry.load(store)
    assert set(index["findings"]) == {"F0001", "F0002"}
    keys = set(store.list("F0001/v1/"))
    assert {
        "F0001/v1/index.html",
        "F0001/v1/finding.json",
        "F0001/v1/SHA256SUMS",
        "F0001/v1/LICENSE.md",
        "F0001/v1/F0001-v1.zip",
        "F0001/v1/F0001-v1.zip.sha256",
        "F0001/v1/data/results.csv",
        "F0001/v1/reproduce/run.py",
    } == keys
    page = store.get("F0001/v1/index.html")[0].decode()
    assert "F0001 v1" in page and "{{" not in page
    manifest = json.loads(store.get("F0001/v1/finding.json")[0])
    assert "private" not in manifest and "scratch disk" not in json.dumps(manifest)
    assert manifest["license"] == {"text": "CC-BY-4.0", "data": "CC0-1.0", "code": "MIT"}
    assert manifest["authors"][0]["affiliation"] == cfg.affiliation
    assert store.content_type("F0001/v1/index.html").startswith("text/html")
    assert publish.verify(store, "F0001") == []


def test_archive_is_byte_reproducible_and_complete(bundle_dir, cfg, tmp_path):
    checked = checks.check_bundle(bundle_dir, cfg, network=False)
    kw = dict(
        finding_id="F0009",
        version=2,
        published="2026-11-04T12:00:00Z",
        publisher="Ada",
        change=None,
        profiles={},
        private_code=[],
        affiliation=None,
        site_url="https://findings.afh.org",
        tool_version="t",
    )
    a = bundle.build(checked.source, checked.files, tmp_path / "a", **kw)
    b = bundle.build(checked.source, checked.files, tmp_path / "b", **kw)
    za, zb = (x.root / "F0009-v2.zip" for x in (a, b))
    assert za.read_bytes() == zb.read_bytes()
    names = set(zipfile.ZipFile(za).namelist())
    assert "F0009-v2/SHA256SUMS" in names and "F0009-v2/finding.json" in names
    sums = (a.root / "SHA256SUMS").read_text().splitlines()
    for line in sums:
        digest, rel = line.split("  ")
        assert hashlib.sha256((a.root / rel).read_bytes()).hexdigest() == digest


def test_revise_needs_change_and_adds_version(bundle_dir, cfg, store):
    pub(bundle_dir, cfg, store)
    with pytest.raises(publish.PublishError, match="needs --change"):
        pub(bundle_dir, cfg, store, revise="F0001")
    r = pub(
        bundle_dir,
        cfg,
        store,
        revise="F0001",
        change={"type": "corrected", "summary": "fixed a unit"},
    )
    assert (r.finding_id, r.version) == ("F0001", 2)
    f = registry.load(store)[0]["findings"]["F0001"]
    assert f["latest"] == 2 and f["versions"][1]["change"]["type"] == "corrected"
    assert store.get("F0001/v1/index.html") is not None  # v1 untouched


def test_claimed_number_is_skipped(bundle_dir, cfg, store):
    # Someone else claimed F0001 but hasn't reached the registry yet.
    store.put_bytes(
        "F0001/v1/finding.json",
        b'{"published": "2026-01-01T00:00:00Z"}',
        "application/json",
        if_none_match=True,
    )
    r = pub(bundle_dir, cfg, store)
    assert r.finding_id == "F0002"


def test_interrupted_publish_resumes(bundle_dir, cfg, store, monkeypatch):
    real_put = FileStore.put_file
    calls = {"n": 0}

    def flaky(self, key, path, ctype, metadata=None):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("network dropped")
        return real_put(self, key, path, ctype, metadata)

    monkeypatch.setattr(FileStore, "put_file", flaky)
    with pytest.raises(OSError):
        pub(bundle_dir, cfg, store, published_at="2026-11-04T10:00:00Z")
    assert registry.load(store)[0]["findings"] == {}  # not visible
    monkeypatch.setattr(FileStore, "put_file", real_put)
    r = pub(bundle_dir, cfg, store)
    assert r.resumed and r.finding_id == "F0001" and r.skipped >= 2
    assert publish.verify(store, "F0001") == []


def test_nothing_is_overwritten(bundle_dir, cfg, store):
    pub(bundle_dir, cfg, store)
    with pytest.raises(PreconditionFailed):
        store.put_bytes("F0001/v1/finding.json", b"{}", "application/json", if_none_match=True)


def test_builds_on_must_exist(tmp_path, cfg, store):
    b = make_bundle(tmp_path / "b", yaml_text=FINDING_YAML + "builds_on: [F0007/v1]\n")
    with pytest.raises(publish.PublishError, match="builds_on"):
        pub(b, cfg, store)


def test_check_command_runs_from_published_copy(tmp_path, cfg, store):
    text = (
        FINDING_YAML
        + "check: python3 -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('SHA256SUMS').exists() else 3)\"\n"
    )
    r = pub(make_bundle(tmp_path / "ok", yaml_text=text), cfg, store)
    assert r.finding_id == "F0001"
    bad = FINDING_YAML + 'check: python3 -c "import sys; sys.exit(4)"\n'
    with pytest.raises(publish.PublishError, match="failed"):
        pub(make_bundle(tmp_path / "bad", yaml_text=bad), cfg, store)


def test_status_events_and_rebuild(bundle_dir, cfg, store):
    pub(bundle_dir, cfg, store)
    pub(bundle_dir, cfg, store)
    pub(
        bundle_dir,
        cfg,
        store,
        revise="F0001",
        change={"type": "expanded", "summary": "more molecules"},
    )
    publish.set_status(store, "F0002", "retract", reason="wrong basis set", by="Ada")
    publish.set_status(store, "F0001", "link", stacks_url="https://thestacks.org/publications/x")
    with pytest.raises(publish.PublishError):
        publish.set_status(store, "F0002", "withdraw")  # needs a reason
    live, _ = registry.load(store)
    rebuilt, incomplete = registry.rebuild(store)
    assert incomplete == []
    strip = lambda idx: {k: {kk: vv for kk, vv in v.items()} for k, v in idx["findings"].items()}  # noqa: E731
    assert strip(rebuilt) == strip(live)
    assert live["findings"]["F0002"]["state"] == "retracted"
    assert live["findings"]["F0001"]["stacks_url"].endswith("/x")


def test_withdrawn_cannot_be_revised(bundle_dir, cfg, store):
    pub(bundle_dir, cfg, store)
    publish.set_status(store, "F0001", "withdraw", reason="contained partner data")
    with pytest.raises(publish.PublishError, match="withdrawn"):
        pub(bundle_dir, cfg, store, revise="F0001", change={"type": "corrected", "summary": "x"})


def test_supersedes_marks_the_old_finding(tmp_path, cfg, store):
    pub(make_bundle(tmp_path / "a"), cfg, store)
    pub(make_bundle(tmp_path / "b", yaml_text=FINDING_YAML + "supersedes: F0001\n"), cfg, store)
    assert registry.load(store)[0]["findings"]["F0001"]["superseded_by"] == "F0002"


def test_skip_profiles_is_recorded(tmp_path, cfg, store):
    text = FINDING_YAML.replace("project: infrastructure", "project: mepd") + (
        "mepd:\n  level_of_theory: g-xTB\n  software: [mepd]\n  sampling: all of them, in file order\n"
    )
    b = make_bundle(tmp_path / "b", yaml_text=text)
    with pytest.raises(publish.PublishError):
        pub(b, cfg, store)  # the mepd rules aren't met
    r = pub(b, cfg, store, skip_profiles=True)
    manifest = json.loads(store.get(f"{r.finding_id}/v1/finding.json")[0])
    assert manifest["profiles"] == {} and manifest["mepd"]["level_of_theory"] == "g-xTB"

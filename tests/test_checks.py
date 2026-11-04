from __future__ import annotations

from pathlib import Path

from conftest import FINDING_YAML, PAGE, make_bundle

from afh_findings import checks


def codes(checked: checks.Checked, level: str = "error") -> set[str]:
    return {i.code for i in checked.issues if i.level == level}


def test_good_bundle_passes(bundle_dir, cfg):
    checked = checks.check_bundle(bundle_dir, cfg, network=False)
    assert checked.ok, checked.issues
    assert "finding.yaml" not in checked.files
    assert checked.profiles == []


def test_missing_not_tested_is_an_error(tmp_path, cfg):
    text = FINDING_YAML.replace(
        "  not_tested:\n    - Systems over 200 atoms\n", "  not_tested: []\n"
    )
    b = make_bundle(tmp_path / "b", yaml_text=text)
    checked = checks.check_bundle(b, cfg, network=False)
    assert "schema" in codes(checked)


def test_unknown_key_is_an_error(tmp_path, cfg):
    b = make_bundle(tmp_path / "b", yaml_text=FINDING_YAML + "mepd:\n  level_of_theory: g-xTB\n")
    assert "schema" in codes(checks.check_bundle(b, cfg, network=False))


def test_verified_needs_check(tmp_path, cfg):
    b = make_bundle(
        tmp_path / "b", yaml_text=FINDING_YAML.replace("status: preliminary", "status: verified")
    )
    assert "verified" in codes(checks.check_bundle(b, cfg, network=False))


def test_link_leaving_bundle_and_broken_link(tmp_path, cfg):
    page = PAGE.replace(
        "</body>", '<a href="../F0001/">other</a><a href="data/missing.csv">x</a></body>'
    )
    checked = checks.check_bundle(make_bundle(tmp_path / "b", page=page), cfg, network=False)
    assert {"outside", "broken"} <= codes(checked)


def test_cross_finding_links_and_external_scripts(tmp_path, cfg):
    page = PAGE.replace(
        "</body>",
        '<a href="/F0001/v3/data/x.csv">pinned</a><a href="/F0002/">latest</a>'
        '<script src="https://cdn.example.org/lib.js"></script>'
        '<link rel="preconnect" href="https://fonts.gstatic.com"></body>',
    )
    checked = checks.check_bundle(make_bundle(tmp_path / "b", page=page), cfg, network=False)
    assert checked.ok
    assert {"unpinned", "external"} <= codes(checked, "warning")


def test_privacy_scan_blocks_and_allows(tmp_path, cfg):
    b = make_bundle(
        tmp_path / "b",
        extra={"reproduce/notes.txt": "ran on secret-host from /home/ada/runs at 192.168.8.6\n"},
    )
    checked = checks.check_bundle(b, cfg, network=False)
    found = [i.message for i in checked.issues if i.code == "privacy" and i.level == "error"]
    assert any("home path" in m for m in found)
    assert any("private network" in m for m in found)
    assert any("internal name" in m for m in found)
    allowed = FINDING_YAML + "privacy_allow: ['/home/ada', 'secret-host', '192.168.8.6']\n"
    b2 = make_bundle(
        tmp_path / "b2",
        yaml_text=allowed,
        extra={"reproduce/notes.txt": "ran on secret-host from /home/ada/runs at 192.168.8.6\n"},
    )
    assert checks.check_bundle(b2, cfg, network=False).ok


def test_privacy_scan_looks_inside_archives(tmp_path, cfg):
    import io
    import tarfile

    b = make_bundle(tmp_path / "b")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as tf:
        data = b"token " + b"ghp" + b"_abcdefghijklmnopqrstuvwxyz0123\n"  # fake, split up
        info = tarfile.TarInfo("inputs/run.sh")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    (b / "data" / "inputs.tar.xz").write_bytes(buf.getvalue())
    checked = checks.check_bundle(b, cfg, network=False)
    assert any(i.code == "privacy" and "credential" in i.message for i in checked.issues)


def test_reserved_and_excluded_files(tmp_path, cfg):
    b = make_bundle(
        tmp_path / "b", extra={"SHA256SUMS": "x", "_hidden.txt": "x", "__pycache__/a.pyc": "x"}
    )
    checked = checks.check_bundle(b, cfg, network=False)
    assert "reserved" in codes(checked)
    assert not any("__pycache__" in f for f in checked.files)


def test_listed_data_must_exist(tmp_path, cfg):
    b = make_bundle(
        tmp_path / "b", yaml_text=FINDING_YAML.replace("data/results.csv", "data/nope.csv")
    )
    assert "data" in codes(checks.check_bundle(b, cfg, network=False))


def test_template_text_must_be_replaced(tmp_path, cfg):
    b = make_bundle(tmp_path / "b", yaml_text=FINDING_YAML.replace("Ada Example", "Your Name"))
    assert "template" in codes(checks.check_bundle(b, cfg, network=False))


def test_mepd_project_requires_its_profile(tmp_path, cfg):
    text = FINDING_YAML.replace("project: infrastructure", "project: mepd")
    checked = checks.check_bundle(make_bundle(tmp_path / "b", yaml_text=text), cfg, network=False)
    assert set(checked.profiles) == {"mepd", "reproducible"}
    messages = " ".join(i.message for i in checked.issues if i.level == "error")
    assert "mepd:" in messages  # namespace block required
    assert "check" in messages  # reproducible needs a check command


def test_mepd_profile_passes_when_followed(tmp_path, cfg):
    text = FINDING_YAML.replace("project: infrastructure", "project: mepd") + (
        "check: python check.py\n"
        "upstream:\n  - {name: Reaction-QM, doi: 10.5281/zenodo.18551029, license: CC-BY-4.0}\n  - {name: g-xTB, url: https://github.com/grimme-lab/g-xtb}\n"
        "mepd:\n  level_of_theory: g-xTB\n  software: [mepd 0.9, g-xTB 2.0.1]\n"
        "  sampling: the first 500 reactions in file order, not random\n"
    ).replace("upstream: []\n", "")
    page = PAGE.replace(
        "</body>",
        '<h2>Background</h2><p>See <a href="https://example.org">this</a>.</p>'
        "<h2>Approach</h2><h2>Results</h2><h2>Details</h2></body>",
    )
    b = make_bundle(
        tmp_path / "b",
        yaml_text=text,
        page=page,
        extra={"reproduce/README.md": "# Rerun\n", "check.py": "print('ok')\n"},
    )
    checked = checks.check_bundle(b, cfg, network=False)
    assert checked.ok, [str(i) for i in checked.issues]


def test_local_profile_file(tmp_path, cfg, bundle_dir):
    rules = tmp_path / "rules.py"
    rules.write_text(
        "from afh_findings.issues import error\nNAME='strict'\n"
        "def check(source, files):\n    return [error('strict', 'no')]\n"
    )
    checked = checks.check_bundle(bundle_dir, cfg, profile_files=[Path(rules)], network=False)
    assert "strict" in codes(checked)


def test_version_numbers_are_not_addresses(tmp_path, cfg):
    text = 'deps = ["nvidia-curand==10.4.0.35", "lib>=10.1.2.3", "v10.0.0.1"]\nserver at 10.0.0.5\n'
    b = make_bundle(tmp_path / "b", extra={"reproduce/deps.py": text})
    hits = [
        i.message for i in checks.check_bundle(b, cfg, network=False).issues if i.code == "privacy"
    ]
    assert len(hits) == 1 and "10.0.0.5" in hits[0]

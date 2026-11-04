from __future__ import annotations

import json

from afh_findings import config, page


def test_inject_after_title_and_without_head():
    m = {
        "id": "F0001",
        "version": 1,
        "title": 'A <b>"claim"</b>',
        "authors": [{"name": "Ada"}],
        "first_published": "2026-11-04T00:00:00Z",
        "published": "2026-11-04T00:00:00Z",
    }
    head = page.head_html(m, "https://findings.afh.org", "/F0001/")
    out = page.inject("<html><meta charset=utf-8><title>x</title><body>hi</body>", head)
    assert out.index("citation_title") > out.index("</title>")
    assert "&lt;b&gt;" in out  # meta content escaped
    data = out.split('id="afh-finding">', 1)[1].split("</script>", 1)[0]
    assert "<b>" not in data and json.loads(data)["title"] == m["title"]
    assert page.inject("plain", "X") == "plainX"


def test_config_layers(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('publisher = "Ada"\nbucket = "test-bucket"\ninternal_hosts = ["lab-box"]\n')
    cfg = config.load(
        path, env={"AFH_FINDINGS_ACCOUNT_ID": "abc", "AFH_FINDINGS_SITE_URL": "https://x.org/"}
    )
    assert cfg.publisher == "Ada" and cfg.bucket == "test-bucket"
    assert cfg.r2_endpoint == "https://abc.r2.cloudflarestorage.com"
    assert cfg.site_url == "https://x.org"
    assert "lab-box" in cfg.internal_hosts and "melodi" in cfg.internal_hosts

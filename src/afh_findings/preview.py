"""Serve a bundle locally the way findings.afh.org will: at /Fnnnn/, with the header bar."""

from __future__ import annotations

import html
import json
import posixpath
import tempfile
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from afh_findings import __version__, bundle, checks, page, registry
from afh_findings.config import Config


def bar_js() -> bytes:
    packaged = resources.files("afh_findings").joinpath("static/bar.js")
    if packaged.is_file():
        return packaged.read_bytes()
    return (Path(__file__).resolve().parents[2] / "static" / "bar.js").read_bytes()


def listing(prefix: str, rel_dir: str, files: list[dict[str, Any]]) -> str:
    rel_dir = rel_dir.strip("/")
    base = rel_dir + "/" if rel_dir else ""
    entries: dict[str, int | None] = {}
    for f in files:
        if not f["path"].startswith(base):
            continue
        rest = f["path"][len(base) :]
        head, _, tail = rest.partition("/")
        entries[head + ("/" if tail else "")] = None if tail else f["size"]
    rows = "".join(
        f'<li><a href="{html.escape(name)}">{html.escape(name)}</a>'
        + (f" <small>{size:,} bytes</small>" if size is not None else "")
        + "</li>"
        for name, size in sorted(entries.items())
    )
    title = html.escape(f"{prefix}{base}")
    return (
        f"<!doctype html><meta charset=utf-8><title>{title}</title>"
        f"<body style='font:15px/1.6 system-ui;max-width:46rem;margin:2rem auto;padding:0 16px'>"
        f"<h1 style='font-size:1.2rem'>{title}</h1><ul>{rows}</ul></body>"
    )


class Handler(BaseHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        root: Path,
        source: Path,
        values: dict[str, str],
        meta: dict[str, Any],
        site_url: str,
        **kwargs: Any,
    ) -> None:
        self.root, self.source, self.values = root, source, values
        self.meta, self.site_url = meta, site_url
        super().__init__(*args, **kwargs)

    def _resolve(self, rel: str) -> Path | None:
        """Live file from the bundle (so edits show on reload), else a generated one."""
        for base in (self.source, self.root):
            target = (base / rel).resolve()
            if (target == base.resolve() or base.resolve() in target.parents) and target.exists():
                if base is self.source and target.name == "finding.yaml":
                    continue
                return target
        return None

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter
        pass

    def _send(
        self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        fid, v = self.meta["id"], self.meta["version"]
        path = unquote(urlsplit(self.path).path)
        if path == "/_static/bar.js":
            return self._send(200, bar_js(), "text/javascript; charset=utf-8")
        if path in ("/", f"/{fid}", f"/{fid}/v{v}"):
            return self._send(HTTPStatus.FOUND, b"", "text/plain", {"Location": f"/{fid}/"})
        for prefix in (f"/{fid}/v{v}/", f"/{fid}/"):
            if path.startswith(prefix):
                rel = path[len(prefix) :]
                break
        else:
            return self._send(404, b"not part of this preview", "text/plain; charset=utf-8")
        manifest = json.loads((self.root / "finding.json").read_text())
        if rel in ("_about", "_about/"):
            body = f"<!doctype html><meta charset=utf-8><title>{fid} about</title><pre>{html.escape(json.dumps(manifest, indent=2))}</pre>"
            return self._send(200, body.encode(), "text/html; charset=utf-8")
        if rel == "":
            rel = manifest["entry"]
        target = self._resolve(rel.rstrip("/") or ".")
        if target is None:
            return self._send(404, b"not found", "text/plain; charset=utf-8")
        if rel.endswith("/") or target.is_dir():
            if not rel.endswith("/"):
                return self._send(
                    HTTPStatus.MOVED_PERMANENTLY, b"", "text/plain", {"Location": path + "/"}
                )
            index = target / "index.html"
            if index.is_file():
                target, rel = index, posixpath.join(rel, "index.html")
            else:
                body = listing(f"/{fid}/", rel, manifest["files"])
                return self._send(
                    200,
                    page.inject(body, self._head(rel)).encode(),
                    "text/html; charset=utf-8",
                )
        if not target.is_file():
            return self._send(404, b"not found", "text/plain; charset=utf-8")
        ctype = bundle.content_type(rel)
        data = target.read_bytes()
        if Path(rel).suffix.lower() in bundle.PLACEHOLDER_SUFFIXES:
            data = bundle.substitute(data.decode("utf-8", errors="replace"), self.values).encode()
        if ctype.startswith("text/html"):
            data = page.inject(data.decode("utf-8", errors="replace"), self._head(rel)).encode()
        self._send(200, data, ctype)

    def _head(self, rel: str) -> str:
        return page.head_html(self.meta, self.site_url, f"/{self.meta['id']}/{rel}")


def serve(
    bundle_dir: Path, cfg: Config, *, port: int, finding_id: str, version: int, log=print
) -> None:
    checked = checks.check_bundle(bundle_dir, cfg, network=False)
    for issue in checked.issues:
        log(f"  {issue}")
    if checked.source is None:
        raise SystemExit("cannot preview: finding.yaml is missing or unreadable")
    with tempfile.TemporaryDirectory(prefix="afh-findings-preview-") as tmp:
        built = bundle.build(
            checked.source,
            checked.files,
            Path(tmp) / "version",
            finding_id=finding_id,
            version=version,
            published=registry.now(),
            publisher=cfg.publisher,
            change=None,
            profiles={n: "preview" for n in checked.profiles},
            private_code=[],
            affiliation=cfg.affiliation,
            site_url=cfg.site_url,
            tool_version=f"afh-findings {__version__}",
        )
        meta = page.meta(built.manifest, latest=version, preview=True)
        values = bundle.placeholder_values(
            finding_id, version, built.manifest["published"], cfg.site_url
        )
        handler = partial(
            Handler,
            root=built.root,
            source=bundle_dir.resolve(),
            values=values,
            meta=meta,
            site_url=cfg.site_url,
        )
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        log(f"preview of {bundle_dir} at http://127.0.0.1:{port}/{finding_id}/  (Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

"""Collect a bundle's files and build the exact bytes that get published."""

from __future__ import annotations

import fnmatch
import hashlib
import mimetypes
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from afh_findings import manifest as mf
from afh_findings.issues import Issue, error, warning

# Never published: tool and editor clutter.
DEFAULT_EXCLUDES = [
    ".git",
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    ".ipynb_checkpoints",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "Thumbs.db",
]
# Written by the tool; a bundle may not carry its own.
GENERATED = {"finding.json", "SHA256SUMS", "LICENSE.md"}
PLACEHOLDER_SUFFIXES = {".html", ".htm", ".md"}
LARGE_FILE = 2 * 1024**3
STORED_SUFFIXES = {
    ".zip",
    ".gz",
    ".xz",
    ".bz2",
    ".zst",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".webm",
    ".pdf",
    ".h5",
    ".npz",
    ".parquet",
}
TEXT_TYPES = {
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
    ".xyz",
    ".inp",
    ".out",
    ".log",
    ".in",
    ".cfg",
    ".ini",
    ".r",
    ".jl",
    ".f90",
    ".c",
    ".h",
    ".cpp",
    ".rs",
    ".ts",
    ".sdf",
    ".mol",
    ".mol2",
    ".pdb",
    ".cif",
    ".gjf",
    ".com",
}
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    size: int
    content_type: str

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


def content_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in (".html", ".htm"):
        return "text/html; charset=utf-8"
    if suffix in TEXT_TYPES or PurePosixPath(path).name in ("SHA256SUMS", "README", "LICENSE"):
        return "text/plain; charset=utf-8"
    if suffix == ".js" or suffix == ".mjs":
        return "text/javascript; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".svg":
        return "image/svg+xml"
    guess, _ = mimetypes.guess_type(path)
    return guess or "application/octet-stream"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _excluded(rel: PurePosixPath, patterns: list[str]) -> bool:
    for part in rel.parts:
        if any(fnmatch.fnmatch(part, p) for p in patterns):
            return True
    return any(fnmatch.fnmatch(str(rel), p) for p in patterns)


def collect(
    bundle_dir: Path, extra_excludes: list[str] | None = None
) -> tuple[list[str], list[Issue]]:
    """Relative POSIX paths of every file to publish (finding.yaml is replaced by finding.json)."""
    patterns = DEFAULT_EXCLUDES + list(extra_excludes or [])
    files: list[str] = []
    issues: list[Issue] = []
    for root, dirs, names in os.walk(bundle_dir):
        root_path = Path(root)
        rel_root = PurePosixPath(root_path.relative_to(bundle_dir).as_posix())
        dirs[:] = sorted(d for d in dirs if not _excluded(rel_root / d, patterns))
        for d in dirs:
            if (root_path / d).is_symlink():
                issues.append(
                    error("symlink", "symlinked folders are not published", str(rel_root / d))
                )
        for name in sorted(names):
            rel_path = rel_root / name if str(rel_root) != "." else PurePosixPath(name)
            if _excluded(rel_path, patterns):
                continue
            if (root_path / name).is_symlink():
                issues.append(
                    error("symlink", "symlinks are not published; copy the file in", str(rel_path))
                )
                continue
            if str(rel_path) == mf.SOURCE_NAME:
                continue
            files.append(str(rel_path))
    for rel in files:
        first = rel.split("/", 1)[0]
        if rel in GENERATED:
            issues.append(error("reserved", f"{rel} is written by afh-findings; remove it", rel))
        elif first.startswith("_"):
            issues.append(error("reserved", "top-level names starting with '_' are reserved", rel))
        elif fnmatch.fnmatch(rel, "F[0-9][0-9][0-9][0-9]-v*.zip*"):
            issues.append(error("reserved", "the version archive name is reserved", rel))
        size = (bundle_dir / rel).stat().st_size
        if size > LARGE_FILE:
            issues.append(
                warning("size", f"{size / 1024**3:.1f} GB; consider a dataset record instead", rel)
            )
    return files, issues


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def placeholder_values(
    finding_id: str, version: int, published: str, site_url: str
) -> dict[str, str]:
    return {
        "FINDING_ID": finding_id,
        "FINDING_VERSION": str(version),
        "FINDING_DATE": published[:10],
        "FINDING_URL": f"{site_url}/{finding_id}/v{version}/",
    }


def license_text(
    lic: dict[str, str], finding_id: str, version: int, upstream: list[dict[str, Any]]
) -> str:
    lines = [
        f"# Licenses for {finding_id} version {version}",
        "",
        f"- Text and figures: {lic['text']}",
        f"- Data: {lic['data']}",
        f"- Code (scripts, notebooks, source files): {lic['code']}",
        "",
        "License texts: https://spdx.org/licenses/",
    ]
    credited = [u for u in upstream if isinstance(u, dict)]
    if credited:
        lines += ["", "## Sources to credit", ""]
        for u in credited:
            ref = u.get("doi") and f"doi:{u['doi']}" or u.get("url", "")
            lic_note = f", {u['license']}" if u.get("license") else ""
            lines.append(f"- {u['name']}{' (' + ref + lic_note + ')' if ref or lic_note else ''}")
    return "\n".join(lines) + "\n"


@dataclass
class Built:
    """The published bytes for one version, laid out in `root`."""

    root: Path
    finding_id: str
    version: int
    manifest: dict[str, Any]
    files: list[FileEntry]  # everything to upload, finding.json included

    @property
    def archive_name(self) -> str:
        return f"{self.finding_id}-v{self.version}.zip"


def build(
    source: mf.Source,
    files: list[str],
    out: Path,
    *,
    finding_id: str,
    version: int,
    published: str,
    publisher: str | None,
    change: dict[str, str] | None,
    profiles: dict[str, str],
    private_code: list[str],
    affiliation: str | None,
    site_url: str,
    tool_version: str,
) -> Built:
    """Lay out the version in `out` deterministically: same inputs, same bytes."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    values = placeholder_values(finding_id, version, published, site_url)
    for rel in files:
        src = source.bundle_dir / rel
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if PurePosixPath(rel).suffix.lower() in PLACEHOLDER_SUFFIXES:
            raw = src.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                dst.write_bytes(raw)
            else:
                dst.write_bytes(substitute(text, values).encode("utf-8"))
        else:
            shutil.copyfile(src, dst)
    lic = mf.license_for(source.core)
    (out / "LICENSE.md").write_text(
        license_text(lic, finding_id, version, source.core.get("upstream", []) or []),
        encoding="utf-8",
    )
    content = sorted([*files, "LICENSE.md"])
    entries = [
        FileEntry(rel, sha256_file(out / rel), (out / rel).stat().st_size, content_type(rel))
        for rel in content
    ]
    manifest = mf.published_manifest(
        source,
        finding_id=finding_id,
        version=version,
        published=published,
        publisher=publisher,
        change=change,
        profiles=profiles,
        private_code=private_code,
        files=[e.as_dict() for e in entries],
        affiliation=affiliation,
        tool_version=tool_version,
    )
    (out / "finding.json").write_bytes(mf.dumps(manifest))
    entries.append(_entry(out, "finding.json"))
    sums = "".join(f"{e.sha256}  {e.path}\n" for e in sorted(entries, key=lambda e: e.path))
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    entries.append(_entry(out, "SHA256SUMS"))
    archive = f"{finding_id}-v{version}.zip"
    _zip(out, sorted(e.path for e in entries), out / archive, prefix=f"{finding_id}-v{version}")
    entries.append(_entry(out, archive))
    digest = sha256_file(out / archive)
    (out / f"{archive}.sha256").write_text(f"{digest}  {archive}\n", encoding="utf-8")
    entries.append(_entry(out, f"{archive}.sha256"))
    return Built(out, finding_id, version, manifest, sorted(entries, key=lambda e: e.path))


def _entry(root: Path, rel: str) -> FileEntry:
    p = root / rel
    return FileEntry(rel, sha256_file(p), p.stat().st_size, content_type(rel))


def _zip(root: Path, rels: list[str], target: Path, prefix: str) -> None:
    with zipfile.ZipFile(target, "w") as zf:
        for rel in rels:
            info = zipfile.ZipInfo(f"{prefix}/{rel}", date_time=ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            stored = PurePosixPath(rel).suffix.lower() in STORED_SUFFIXES
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            with (root / rel).open("rb") as src, zf.open(info, "w", force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 1 << 20)

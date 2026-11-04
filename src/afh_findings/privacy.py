"""Scan everything that would be published for things that should stay private.

Errors block publishing: home paths, private network addresses, tailnet names, internal
host names, credentials. Warnings (emails, /tmp paths) are shown and allowed. Archives
(.gz, .xz, .bz2, .zip, .tar.*) are scanned inside. `privacy_allow` in finding.yaml lists
exact strings that are fine to publish.
"""

from __future__ import annotations

import bz2
import getpass
import gzip
import io
import lzma
import re
import socket
import tarfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from afh_findings.issues import Issue, error, warning

SCAN_LIMIT = 256 * 1024**2  # uncompressed bytes per file
MAX_REPORTS_PER_FILE = 3


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: re.Pattern[str]
    blocking: bool


def patterns(internal_hosts: list[str]) -> list[Pattern]:
    octet = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    pats = [
        Pattern("home path", re.compile(r"(?:/home|/Users)/(?!runner\b)[a-z_][\w.-]*"), True),
        Pattern(
            "private network address",
            re.compile(
                rf"(?<![\w.=<>~@-])(?:10\.{octet}|192\.168|172\.(?:1[6-9]|2\d|3[01])"
                rf"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.{octet}\.{octet}(?![\d.])"
            ),
            True,
        ),
        Pattern("tailnet name", re.compile(r"\b[\w-]+\.ts\.net\b", re.I), True),
        Pattern(
            "credential",
            re.compile(
                r"(?:ghp_|gho_|github_pat_|sk-ant-|xox[bpas]-|AKIA|ASIA)[A-Za-z0-9_\-]{12,}"
                r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
            ),
            True,
        ),
        Pattern(
            "email address", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", re.I), False
        ),
        Pattern("temporary path", re.compile(r"(?<![\w/])/tmp/[\w.-]+"), False),
    ]
    hosts = [h for h in internal_hosts if h]
    try:
        hosts.append(socket.gethostname().split(".")[0])
    except OSError:
        pass
    user = getpass.getuser()
    if len(user) > 3 and user not in {"user", "root", "admin", "runner"}:
        hosts.append(user)
    hosts = sorted({h for h in hosts if len(h) > 2}, key=len, reverse=True)
    if hosts:
        joined = "|".join(re.escape(h) for h in hosts)
        pats.append(
            Pattern("internal name", re.compile(rf"(?<![\w-])(?:{joined})(?![\w-])", re.I), True)
        )
    return pats


def _texts(name: str, raw: bytes, depth: int = 0) -> Iterator[tuple[str, str]]:
    """Yield (label, text) for a file, looking inside archives and compressed files."""
    lower = name.rsplit("!", 1)[-1].lower()  # decide by this member's own name
    try:
        if depth < 3 and (lower.endswith((".tar", ".tgz", ".tbz2", ".txz")) or ".tar." in lower):
            with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
                for member in tf.getmembers():
                    if member.isfile() and member.size <= SCAN_LIMIT:
                        fh = tf.extractfile(member)
                        if fh:
                            yield from _texts(f"{name}!{member.name}", fh.read(), depth + 1)
            return
        if depth < 3 and lower.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for info in zf.infolist():
                    if not info.is_dir() and info.file_size <= SCAN_LIMIT:
                        yield from _texts(f"{name}!{info.filename}", zf.read(info), depth + 1)
            return
        if lower.endswith(".gz"):
            yield from _texts(name[:-3], gzip.decompress(raw), depth + 1)
            return
        if lower.endswith(".xz"):
            yield from _texts(name[:-3], lzma.decompress(raw), depth + 1)
            return
        if lower.endswith(".bz2"):
            yield from _texts(name[:-4], bz2.decompress(raw), depth + 1)
            return
    except (OSError, EOFError, lzma.LZMAError, tarfile.TarError, zipfile.BadZipFile):
        return
    head = raw[:8192]
    if b"\x00" in head:
        return  # binary
    yield name, raw.decode("utf-8", errors="replace")


def scan(
    bundle_dir: Path, files: list[str], internal_hosts: list[str], allow: list[str]
) -> list[Issue]:
    pats = patterns(internal_hosts)
    allowed = [a for a in allow if a]
    issues: list[Issue] = []
    for rel in files:
        path = bundle_dir / rel
        if path.stat().st_size > SCAN_LIMIT:
            issues.append(warning("privacy", "too large to scan; check it yourself", rel))
            continue
        raw = path.read_bytes()
        reported = 0
        for label, text in _texts(rel, raw):
            for pat in pats:
                for m in pat.regex.finditer(text):
                    hit = m.group(0)
                    if any(a in hit or hit in a for a in allowed):
                        continue
                    line = text.count("\n", 0, m.start()) + 1
                    make = error if pat.blocking else warning
                    issues.append(
                        make(
                            "privacy",
                            f"{pat.name} {hit!r} (add to privacy_allow if it is fine to publish)",
                            f"{label}:{line}",
                        )
                    )
                    reported += 1
                    if reported >= MAX_REPORTS_PER_FILE:
                        break
                if reported >= MAX_REPORTS_PER_FILE:
                    break
            if reported >= MAX_REPORTS_PER_FILE:
                break
    return issues

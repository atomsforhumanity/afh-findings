"""Run the core checks and any profiles on a bundle."""

from __future__ import annotations

import posixpath
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from afh_findings import bundle, links, privacy, profiles
from afh_findings import manifest as mf
from afh_findings.config import Config
from afh_findings.issues import Issue, error, warning

# Text from `afh-findings new` that must be replaced before publishing.
TEMPLATE_MARKERS = ("your claim as a sentence", "Your Name", "Write two or three sentences")
GITHUB_REPO = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/@#].*)?$")
CHECK_TIMEOUT = 30 * 60


@dataclass
class Checked:
    """Result of checking a bundle before it is built."""

    source: mf.Source | None
    files: list[str]
    issues: list[Issue]
    profiles: list[str] = field(default_factory=list)
    private_code: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.source is not None and not any(i.level == "error" for i in self.issues)


def check_bundle(
    bundle_dir: Path,
    cfg: Config,
    *,
    extra_profiles: list[str] | None = None,
    profile_files: list[Path] | None = None,
    network: bool = True,
) -> Checked:
    bundle_dir = bundle_dir.resolve()
    try:
        raw = mf.read(bundle_dir)
    except (FileNotFoundError, ValueError) as exc:
        return Checked(None, [], [error("manifest", str(exc), mf.SOURCE_NAME)])
    except Exception as exc:  # YAML syntax errors
        return Checked(None, [], [error("manifest", f"cannot parse: {exc}", mf.SOURCE_NAME)])

    active, issues = profiles.resolve(raw, extra_profiles or [], profile_files or [])
    source, schema_issues = mf.load(bundle_dir, {p.namespace for p in active if p.namespace})
    issues += schema_issues
    if source is None:
        return Checked(None, [], issues, [p.name for p in active])

    files, collect_issues = bundle.collect(bundle_dir, source.core.get("exclude"))
    issues += collect_issues
    if not files:
        issues.append(error("empty", "the bundle has no files besides finding.yaml"))

    entry = source.core.get("entry", mf.DEFAULT_ENTRY)
    if entry not in files:
        issues.append(error("entry", f"entry page {entry!r} is not in the bundle"))

    for rel in [mf.SOURCE_NAME, *[f for f in files if f.endswith((".html", ".htm", ".md"))]]:
        text = (bundle_dir / rel).read_text(encoding="utf-8", errors="replace")
        left = [m for m in TEMPLATE_MARKERS if m in text]
        if left:
            issues.append(error("template", f"template text left in: {left[0]!r}", rel))

    private_code: list[str] = []
    issues += _materials(source, files, network, private_code)
    issues += links.check(bundle_dir, files)
    issues += privacy.scan(
        bundle_dir, files, cfg.internal_hosts, source.core.get("privacy_allow", []) or []
    )
    for prof in active:
        issues += prof.run(source, files)
    return Checked(source, files, issues, [p.name for p in active], private_code)


def _materials(
    source: mf.Source, files: list[str], network: bool, private_code: list[str]
) -> list[Issue]:
    issues: list[Issue] = []
    present = set(files)
    dirs = {posixpath.dirname(f) for f in files}
    for key in ("data", "code"):
        items, _none = mf.materials(source.core.get(key))
        for item in items:
            ref = item["path"]
            if mf.is_url(ref):
                if key == "code" and network:
                    state = _repo_visibility(ref)
                    if state == "private":
                        private_code.append(ref)
                        issues.append(
                            warning(
                                "private-code",
                                f"{ref} is not public; readers can't rerun this (it will be noted on the page)",
                                mf.SOURCE_NAME,
                            )
                        )
                    elif state == "unknown":
                        issues.append(
                            warning("code", f"could not confirm {ref} is public", mf.SOURCE_NAME)
                        )
                continue
            norm = posixpath.normpath(ref.rstrip("/"))
            if norm.startswith(".."):
                issues.append(error(key, f"{ref} is outside the bundle", mf.SOURCE_NAME))
            elif (
                norm not in present
                and norm not in dirs
                and not any(f.startswith(norm + "/") for f in files)
            ):
                issues.append(
                    error(
                        key, f"{ref} is listed under {key} but is not in the bundle", mf.SOURCE_NAME
                    )
                )
    return issues


def _repo_visibility(url: str) -> str:
    """'public', 'private' or 'unknown' for a code URL (GitHub is checked without a login)."""
    m = GITHUB_REPO.match(url)
    target = f"https://github.com/{m.group(1)}/{m.group(2)}" if m else url.split("#")[0]
    req = urllib.request.Request(target, method="HEAD", headers={"User-Agent": "afh-findings"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return "public" if resp.status < 400 else "unknown"
    except urllib.error.HTTPError as exc:
        return "private" if exc.code == 404 and m else "unknown"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "unknown"


def run_check_command(
    built_root: Path, command: str, timeout: int = CHECK_TIMEOUT
) -> tuple[bool, str]:
    """Run the finding's check from a fresh copy of the published files, as a reader would."""
    with tempfile.TemporaryDirectory(prefix="afh-findings-check-") as tmp:
        work = Path(tmp) / "bundle"
        shutil.copytree(
            built_root, work, ignore=shutil.ignore_patterns("F[0-9][0-9][0-9][0-9]-v*.zip*")
        )
        try:
            proc = subprocess.run(
                command, shell=True, cwd=work, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout} s"
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, out[-4000:]


def summarize(issues: list[Issue]) -> dict[str, Any]:
    return {
        "errors": sum(i.level == "error" for i in issues),
        "warnings": sum(i.level == "warning" for i in issues),
    }

"""Read an author's finding.yaml, validate it, and normalize it for publishing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from afh_findings.issues import Issue, error, warning

SOURCE_NAME = "finding.yaml"
DEFAULT_ENTRY = "index.html"
DEFAULT_LICENSE = {"text": "CC-BY-4.0", "data": "CC0-1.0", "code": "MIT"}
ID_PATTERN = r"F\d{4}"


def schema() -> dict[str, Any]:
    text = resources.files("afh_findings").joinpath("schema/finding.schema.json")
    return json.loads(text.read_text(encoding="utf-8"))


@dataclass
class Source:
    """The author's record, split into core fields and profile namespaces."""

    path: Path
    core: dict[str, Any]
    namespaces: dict[str, Any] = field(default_factory=dict)

    @property
    def bundle_dir(self) -> Path:
        return self.path.parent


def read(bundle_dir: Path) -> dict[str, Any]:
    path = bundle_dir / SOURCE_NAME
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; every finding needs a {SOURCE_NAME}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping")
    return data


def load(bundle_dir: Path, namespaces: set[str]) -> tuple[Source | None, list[Issue]]:
    """Validate finding.yaml against the core schema.

    Keys named after an active profile's namespace are set aside for that profile.
    """
    try:
        data = read(bundle_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        return None, [error("manifest", str(exc), SOURCE_NAME)]
    core = {k: v for k, v in data.items() if k not in namespaces}
    spaces = {k: v for k, v in data.items() if k in namespaces}
    issues: list[Issue] = []
    validator = jsonschema.Draft202012Validator(schema())
    for err in sorted(validator.iter_errors(core), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in err.absolute_path) or "(top level)"
        message = err.message
        if err.validator == "additionalProperties" and not err.absolute_path:
            message += (
                " (profile keys belong under a profile's namespace, and that profile"
                " must be active)"
            )
        issues.append(error("schema", f"{where}: {message}", SOURCE_NAME))
    issues += _soft_checks(core)
    return Source(bundle_dir / SOURCE_NAME, core, spaces), issues


def _soft_checks(core: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    title = core.get("title")
    if isinstance(title, str) and len(title.split()) < 5:
        issues.append(warning("title", "title should state the claim as a sentence", SOURCE_NAME))
    claim = core.get("claim")
    if isinstance(claim, str) and len(claim.split()) > 150:
        issues.append(
            warning("claim", "claim runs over 150 words; keep detail on the page", SOURCE_NAME)
        )
    if core.get("status") == "verified" and not core.get("check"):
        issues.append(
            error(
                "verified",
                "status 'verified' needs a `check` command that recomputes the numbers"
                " from the bundle",
                SOURCE_NAME,
            )
        )
    for text in _all_strings(core):
        if "TODO" in text or "FIXME" in text:
            issues.append(error("todo", f"unfinished text: {text[:60]!r}", SOURCE_NAME))
            break
    lic = license_for(core)
    upstream_cc_by = [
        u["name"]
        for u in core.get("upstream", []) or []
        if isinstance(u, dict) and str(u.get("license", "")).upper().startswith("CC-BY")
    ]
    if upstream_cc_by and lic["data"].upper().startswith("CC0"):
        issues.append(
            warning(
                "license",
                "data is CC0 but builds on CC-BY sources "
                f"({', '.join(upstream_cc_by)}); consider CC-BY-4.0",
                SOURCE_NAME,
            )
        )
    for u in core.get("upstream", []) or []:
        if isinstance(u, dict) and any(
            tag in str(u.get("license", "")).upper() for tag in ("NC", "ND", "PROPRIETARY")
        ):
            issues.append(
                warning(
                    "license",
                    f"upstream {u['name']!r} is {u['license']}; check redistribution",
                    SOURCE_NAME,
                )
            )
    return issues


def _all_strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() if k != "private" for s in _all_strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _all_strings(v)]
    return []


def license_for(core: dict[str, Any]) -> dict[str, str]:
    """Policy defaults, with data falling back to CC-BY-4.0 when a source is CC-BY."""
    lic = dict(DEFAULT_LICENSE)
    if any(
        isinstance(u, dict) and str(u.get("license", "")).upper().startswith("CC-BY")
        for u in core.get("upstream", []) or []
    ):
        lic["data"] = "CC-BY-4.0"
    lic.update(core.get("license") or {})
    return lic


def materials(value: Any) -> tuple[list[dict[str, str]], str | None]:
    """Normalize `data`/`code`: a list of {path, description?}, or a reason for none."""
    if isinstance(value, dict) and "none" in value:
        return [], str(value["none"])
    items: list[dict[str, str]] = []
    for item in value or []:
        if isinstance(item, str):
            items.append({"path": item})
        else:
            items.append({k: str(v) for k, v in item.items()})
    return items, None


def is_url(ref: str) -> bool:
    return ref.startswith(("http://", "https://"))


def published_manifest(
    source: Source,
    *,
    finding_id: str,
    version: int,
    published: str,
    publisher: str | None,
    change: dict[str, str] | None,
    profiles: dict[str, str],
    private_code: list[str],
    files: list[dict[str, Any]],
    affiliation: str | None,
    tool_version: str,
) -> dict[str, Any]:
    """The finding.json written into the published version (never holds `private`)."""
    core = source.core
    data, data_none = materials(core.get("data"))
    code, code_none = materials(core.get("code"))
    authors = []
    for a in core["authors"]:
        a = dict(a)
        if affiliation and "affiliation" not in a:
            a["affiliation"] = affiliation
        authors.append(a)
    manifest: dict[str, Any] = {
        "schema": "afh-findings/1",
        "id": finding_id,
        "version": version,
        "published": published,
        "publisher": publisher,
        "title": core["title"].strip(),
        "claim": core["claim"].strip(),
        "authors": authors,
        "project": core["project"],
        "kind": core["kind"],
        "status": core["status"],
        "keywords": core.get("keywords", []),
        "scope": core["scope"],
        "data": data,
        "data_none": data_none,
        "code": code,
        "code_none": code_none,
        "private_code": private_code,
        "upstream": core.get("upstream", []),
        "builds_on": core.get("builds_on", []),
        "supersedes": core.get("supersedes"),
        "formerly": core.get("formerly", []),
        "entry": core.get("entry", DEFAULT_ENTRY),
        "check": core.get("check"),
        "license": license_for(core),
        "change": change,
        "profiles": profiles,
        "tool": tool_version,
        "files": files,
    }
    for name, block in source.namespaces.items():
        manifest[name] = _strip_private(block)
    return manifest


def _strip_private(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items() if k != "private"}
    if isinstance(obj, list):
        return [_strip_private(v) for v in obj]
    return obj


def dumps(manifest: dict[str, Any]) -> bytes:
    """Deterministic JSON so a rebuild gives the same bytes."""
    return (json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()

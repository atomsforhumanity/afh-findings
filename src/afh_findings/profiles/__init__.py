"""Profiles: extra rules a project adds on top of the core standard.

A profile is a module in this folder with:

    NAME = "mepd"
    NAMESPACE = "mepd"        # optional: its own block in finding.yaml
    SCHEMA = {...}            # optional: JSON Schema for that block
    REQUIRES = ["reproducible"]
    def check(source, files) -> list[Issue]

`projects.toml` lists the profiles every finding in a project must pass. A finding can
add more with `profiles: [...]`, and `--profile path/to/rules.py` tries out a profile
that isn't in this folder yet.
"""

from __future__ import annotations

import importlib
import importlib.util
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema

from afh_findings import manifest as mf
from afh_findings.issues import Issue, error


@dataclass
class Profile:
    name: str
    namespace: str | None
    schema: dict[str, Any] | None
    requires: list[str]
    checker: Callable[[mf.Source, list[str]], list[Issue]]

    def run(self, source: mf.Source, files: list[str]) -> list[Issue]:
        issues: list[Issue] = []
        if self.namespace:
            block = source.namespaces.get(self.namespace)
            if block is None:
                return [
                    error(
                        self.name,
                        f"add a '{self.namespace}:' block to finding.yaml",
                        mf.SOURCE_NAME,
                    )
                ]
            if self.schema:
                validator = jsonschema.Draft202012Validator(self.schema)
                for err in validator.iter_errors(block):
                    where = ".".join([self.namespace, *(str(p) for p in err.absolute_path)])
                    issues.append(error(self.name, f"{where}: {err.message}", mf.SOURCE_NAME))
        return issues + list(self.checker(source, files))


def _from_module(mod: ModuleType) -> Profile:
    return Profile(
        name=mod.NAME,
        namespace=getattr(mod, "NAMESPACE", None),
        schema=getattr(mod, "SCHEMA", None),
        requires=list(getattr(mod, "REQUIRES", [])),
        checker=mod.check,
    )


def builtin(name: str) -> Profile | None:
    if not name.replace("_", "").replace("-", "").isalnum():
        return None
    try:
        mod = importlib.import_module(f"afh_findings.profiles.{name.replace('-', '_')}")
    except ModuleNotFoundError:
        return None
    return _from_module(mod)


def from_file(path: Path) -> Profile:
    spec = importlib.util.spec_from_file_location(f"afh_findings_local_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load profile from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return _from_module(mod)


def projects() -> dict[str, dict[str, Any]]:
    text = resources.files("afh_findings").joinpath("projects.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def available() -> list[str]:
    folder = resources.files("afh_findings.profiles")
    return sorted(
        p.name[:-3]
        for p in folder.iterdir()
        if p.name.endswith(".py") and not p.name.startswith("_")
    )


def resolve(
    raw: dict[str, Any], extra: list[str], files: list[Path]
) -> tuple[list[Profile], list[Issue]]:
    """The profiles a finding must pass: its project's, its own, and any given on the command line."""
    wanted: list[str] = []
    project = projects().get(str(raw.get("project", "")), {})
    wanted += project.get("profiles", [])
    declared = raw.get("profiles") or []
    if isinstance(declared, list):
        wanted += [str(p) for p in declared]
    wanted += extra
    issues: list[Issue] = []
    active: dict[str, Profile] = {}
    queue = list(dict.fromkeys(wanted))
    while queue:
        name = queue.pop(0)
        if name in active:
            continue
        prof = builtin(name)
        if prof is None:
            issues.append(
                error("profile", f"unknown profile {name!r} (available: {', '.join(available())})")
            )
            continue
        active[name] = prof
        queue += [r for r in prof.requires if r not in active]
    for path in files:
        try:
            prof = from_file(path)
        except Exception as exc:  # a broken local profile should say why
            issues.append(error("profile", f"{path}: {exc}"))
            continue
        active[prof.name] = prof
        for req in prof.requires:
            if req not in active and (dep := builtin(req)):
                active[req] = dep
    return list(active.values()), issues

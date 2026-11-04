"""Publish a bundle as a new finding or a new version of one.

1. Check the bundle (core standard + profiles) and run its `check` from a fresh copy.
2. Claim Fnnnn/vN by creating its finding.json with If-None-Match (numbers can't collide).
3. Upload the other files into that prefix. Nothing is overwritten; an interrupted
   publish of the same bundle resumes where it stopped.
4. Add the version to the registry. Until then the site doesn't show it.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from afh_findings import __version__, bundle, checks, registry
from afh_findings.config import Config
from afh_findings.issues import Issue, warning
from afh_findings.store import PreconditionFailed, Store

CHANGE_TYPES = ("corrected", "expanded", "strengthened", "weakened", "revised")
MAX_CLAIM_ATTEMPTS = 25


class PublishError(Exception):
    def __init__(self, message: str, issues: list[Issue] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


@dataclass
class Plan:
    finding_id: str
    version: int
    change: dict[str, str] | None
    published: str


@dataclass
class Result:
    finding_id: str
    version: int
    url: str
    uploaded: int
    skipped: int
    resumed: bool
    warnings: list[Issue]


def _plan(
    checked: checks.Checked,
    index: dict[str, Any],
    revise: str | None,
    change: dict[str, str] | None,
    published_at: str | None,
) -> tuple[Plan, list[Issue]]:
    assert checked.source is not None
    core = checked.source.core
    notes: list[Issue] = []
    if revise:
        f = index["findings"].get(revise)
        if f is None:
            raise PublishError(
                f"{revise} is not published; leave out --revise to publish a new finding"
            )
        if f["state"] == "withdrawn":
            raise PublishError(f"{revise} was withdrawn; publish a new finding instead")
        change = change or core.get("change")
        if not change:
            raise PublishError(
                "a revision needs --change TYPE --summary TEXT (or a `change:` block)"
            )
        if change["type"] not in CHANGE_TYPES:
            raise PublishError(f"--change must be one of {', '.join(CHANGE_TYPES)}")
        finding_id, version = revise, int(f["latest"]) + 1
    else:
        if change or core.get("change"):
            notes.append(warning("change", "ignored: `change` only applies with --revise"))
        change = None
        finding_id, version = registry.next_id(index), 1
    for ref in core.get("builds_on", []) or []:
        ref_id, ref_v = ref.split("/v")
        target = index["findings"].get(ref_id)
        if target is None or int(ref_v) not in {v["version"] for v in target["versions"]}:
            raise PublishError(f"builds_on {ref}: no such published version")
    sup = core.get("supersedes")
    if sup and (sup not in index["findings"] or sup == finding_id):
        raise PublishError(f"supersedes {sup}: no such other finding")
    return Plan(finding_id, version, change, published_at or registry.now()), notes


def _build(
    checked: checks.Checked, plan: Plan, cfg: Config, out: Path, finding_id: str, published: str
) -> bundle.Built:
    assert checked.source is not None
    return bundle.build(
        checked.source,
        checked.files,
        out,
        finding_id=finding_id,
        version=plan.version,
        published=published,
        publisher=cfg.publisher,
        change=plan.change,
        profiles={name: "passed" for name in checked.profiles},
        private_code=checked.private_code,
        affiliation=cfg.affiliation,
        site_url=cfg.site_url,
        tool_version=f"afh-findings {__version__}",
    )


def summary(built: bundle.Built, checked: checks.Checked, store: Store, cfg: Config) -> str:
    m = built.manifest
    size = sum(e.size for e in built.files)
    warnings = [i for i in checked.issues if i.level == "warning"]
    lines = [
        f"  {built.finding_id} version {built.version}"
        + (f" ({m['change']['type']})" if m.get("change") else " (new finding)"),
        f"  {m['title']}",
        f"  by {', '.join(a['name'] for a in m['authors'])} · {m['project']} · {m['kind']} · {m['status']}",
        f"  {len(built.files)} files, {size / 1024**2:.1f} MB · profiles: {', '.join(checked.profiles) or 'core only'}",
        f"  to {store.describe()} → {cfg.site_url}/{built.finding_id}/v{built.version}/",
    ]
    if m.get("change"):
        lines.insert(2, f"  change: {m['change']['summary']}")
    if checked.private_code:
        lines.append(f"  private code noted on the page: {', '.join(checked.private_code)}")
    if warnings:
        lines.append(f"  {len(warnings)} warning(s), shown above")
    return "\n".join(lines)


def publish(
    bundle_dir: Path,
    cfg: Config,
    store: Store,
    *,
    revise: str | None = None,
    change: dict[str, str] | None = None,
    published_at: str | None = None,
    confirm: Callable[[str], bool] = lambda _s: True,
    extra_profiles: list[str] | None = None,
    profile_files: list[Path] | None = None,
    network: bool = True,
    skip_profiles: bool = False,
    log: Callable[[str], None] = print,
) -> Result:
    checked = checks.check_bundle(
        bundle_dir,
        cfg,
        extra_profiles=extra_profiles,
        profile_files=profile_files,
        network=network,
        skip_profiles=skip_profiles,
    )
    if not checked.ok or checked.source is None:
        raise PublishError("the bundle doesn't meet the standard yet", checked.issues)
    index, _etag = registry.load(store)
    plan, notes = _plan(checked, index, revise, change, published_at)
    checked.issues.extend(notes)

    with tempfile.TemporaryDirectory(prefix="afh-findings-publish-") as tmp:
        out = Path(tmp) / "version"
        finding_id = plan.finding_id
        built = _build(checked, plan, cfg, out, finding_id, plan.published)
        command = checked.source.core.get("check")
        if command:
            log(f"running check: {command}")
            ok, output = checks.run_check_command(built.root, command)
            if not ok:
                raise PublishError(f"`{command}` failed from a fresh copy of the bundle:\n{output}")
        if not confirm(summary(built, checked, store, cfg)):
            raise PublishError("not published")

        resumed = False
        for _attempt in range(MAX_CLAIM_ATTEMPTS):
            claim = f"{finding_id}/v{plan.version}/finding.json"
            manifest_bytes = (built.root / "finding.json").read_bytes()
            try:
                store.put_bytes(
                    claim,
                    manifest_bytes,
                    bundle.content_type("finding.json"),
                    if_none_match=True,
                    metadata={"sha256": bundle.sha256_file(built.root / "finding.json")},
                )
                break
            except PreconditionFailed:
                existing = store.get(claim)
                theirs = json.loads(existing[0]) if existing else {}
                # Same bundle, interrupted earlier? Rebuild with its timestamp and compare bytes.
                if existing and theirs.get("published"):
                    again = _build(
                        checked, plan, cfg, Path(tmp) / "resume", finding_id, theirs["published"]
                    )
                    if (again.root / "finding.json").read_bytes() == existing[0]:
                        built, resumed = again, True
                        log(f"resuming the interrupted publish of {finding_id} v{plan.version}")
                        break
                if revise:
                    raise PublishError(
                        f"{finding_id} v{plan.version} was published by someone else meanwhile; check it, then rerun"
                    ) from None
                finding_id = registry.bump(finding_id)
                built = _build(checked, plan, cfg, out, finding_id, plan.published)
        else:
            raise PublishError("could not claim a finding number; try again")

        uploaded = skipped = 0
        prefix = f"{finding_id}/v{plan.version}/"
        for entry in built.files:
            if entry.path == "finding.json":
                continue
            key = prefix + entry.path
            info = store.head(key)
            if info is not None:
                if info.metadata.get("sha256") == entry.sha256:
                    skipped += 1
                    continue
                raise PublishError(
                    f"{key} already exists with different content; nothing was overwritten"
                )
            store.put_file(
                key, built.root / entry.path, entry.content_type, {"sha256": entry.sha256}
            )
            uploaded += 1
            if uploaded % 50 == 0:
                log(f"  uploaded {uploaded} files")
        final = built.manifest
        registry.update(store, lambda idx: registry.apply_version(idx, final))

    url = (
        f"{cfg.site_url}/{finding_id}/"
        if plan.version == 1
        else f"{cfg.site_url}/{finding_id}/v{plan.version}/"
    )
    return Result(
        finding_id,
        plan.version,
        url,
        uploaded,
        skipped,
        resumed,
        [i for i in checked.issues if i.level == "warning"],
    )


def set_status(
    store: Store,
    finding_id: str,
    kind: str,
    *,
    reason: str | None = None,
    superseded_by: str | None = None,
    doi: str | None = None,
    stacks_url: str | None = None,
    by: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    index, _ = registry.load(store)
    f = index["findings"].get(finding_id)
    if f is None:
        raise PublishError(f"{finding_id} is not published")
    if kind in ("retract", "withdraw") and not reason:
        raise PublishError(f"{kind} needs --reason; readers see it")
    if kind == "supersede":
        if (
            not superseded_by
            or superseded_by not in index["findings"]
            or superseded_by == finding_id
        ):
            raise PublishError("supersede needs --by with another published finding")
    if kind == "link" and doi is None and stacks_url is None:
        raise PublishError("link needs --doi and/or --stacks-url")
    event: dict[str, Any] = {"id": finding_id, "type": kind, "at": at or registry.now(), "by": by}
    if reason:
        event["reason"] = reason
    if superseded_by:
        event["superseded_by"] = superseded_by
    if doi is not None:
        event["doi"] = doi
    if stacks_url is not None:
        event["stacks_url"] = stacks_url
    return registry.write_event(store, event)


def verify(store: Store, finding_id: str, version: int | None = None) -> list[str]:
    """Download a published version and check every file against its checksum."""
    index, _ = registry.load(store)
    f = index["findings"].get(finding_id)
    if f is None:
        return [f"{finding_id} is not in the registry"]
    v = version or f["latest"]
    prefix = f"{finding_id}/v{v}/"
    got = store.get(prefix + "SHA256SUMS")
    if got is None:
        return [f"{prefix}SHA256SUMS is missing"]
    problems = []
    for line in got[0].decode().splitlines():
        digest, rel = line.split("  ", 1)
        obj = store.get(prefix + rel)
        if obj is None:
            problems.append(f"missing {rel}")
        elif hashlib.sha256(obj[0]).hexdigest() != digest:
            problems.append(f"checksum mismatch {rel}")
    archive = f"{finding_id}-v{v}.zip"
    zipsum = store.get(prefix + archive + ".sha256")
    zipobj = store.get(prefix + archive)
    if zipsum is None or zipobj is None:
        problems.append("missing archive or its checksum")
    elif hashlib.sha256(zipobj[0]).hexdigest() != zipsum[0].decode().split()[0]:
        problems.append("archive checksum mismatch")
    return problems

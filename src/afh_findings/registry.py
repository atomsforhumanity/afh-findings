"""The list of all findings: one JSON object in the bucket, rebuildable from the rest.

`_registry/index.json` is the only object that ever changes. It is a cache of what the
bucket already holds: each version's finding.json (written once) and each status event
in Fnnnn/_events/ (written once). `rebuild` recreates it from those alone.
"""

from __future__ import annotations

import copy
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from afh_findings.store import PreconditionFailed, Store

INDEX_KEY = "_registry/index.json"
MANIFEST_KEY = re.compile(r"^(F\d{4})/v(\d+)/finding\.json$")
EVENT_KEY = re.compile(r"^(F\d{4})/_events/[^/]+\.json$")
EVENT_TYPES = ("retract", "withdraw", "restore", "supersede", "link")
STATES = {"retract": "retracted", "withdraw": "withdrawn", "restore": "active"}


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty() -> dict[str, Any]:
    return {"schema": "afh-findings-index/1", "updated": None, "findings": {}}


def load(store: Store) -> tuple[dict[str, Any], str | None]:
    got = store.get(INDEX_KEY)
    if got is None:
        return empty(), None
    data, etag = got
    return json.loads(data), etag


def dumps(index: dict[str, Any]) -> bytes:
    return (json.dumps(index, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def update(
    store: Store, change: Callable[[dict[str, Any]], None], attempts: int = 12
) -> dict[str, Any]:
    """Read, change and write the index; start over if someone else wrote in between."""
    for attempt in range(attempts):
        index, etag = load(store)
        new = copy.deepcopy(index)
        change(new)
        new["updated"] = now()
        try:
            store.put_bytes(
                INDEX_KEY,
                dumps(new),
                "application/json; charset=utf-8",
                if_none_match=etag is None,
                if_match=etag,
            )
            return new
        except PreconditionFailed:
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError("the registry kept changing underneath us; try again")


def next_id(index: dict[str, Any]) -> str:
    numbers = [int(k[1:]) for k in index["findings"]]
    return f"F{(max(numbers) if numbers else 0) + 1:04d}"


def bump(finding_id: str) -> str:
    return f"F{int(finding_id[1:]) + 1:04d}"


def _blank(finding_id: str) -> dict[str, Any]:
    return {
        "id": finding_id,
        "state": "active",
        "state_reason": None,
        "state_date": None,
        "superseded_by": None,
        "doi": None,
        "stacks_url": None,
        "versions": [],
        "events": [],
    }


def apply_version(index: dict[str, Any], m: dict[str, Any]) -> None:
    fid, version = m["id"], m["version"]
    f = index["findings"].setdefault(fid, _blank(fid))
    versions = [v for v in f["versions"] if v["version"] != version]
    versions.append(
        {
            "version": version,
            "published": m["published"],
            "change": m.get("change"),
            "entry": m.get("entry", "index.html"),
            "status": m["status"],
            "publisher": m.get("publisher"),
        }
    )
    versions.sort(key=lambda v: v["version"])
    f["versions"] = versions
    f["latest"] = versions[-1]["version"]
    f["first_published"] = versions[0]["published"]
    if version == f["latest"]:
        f.update(
            {
                "title": m["title"],
                "claim": m["claim"],
                "authors": [{k: a[k] for k in ("name", "orcid") if k in a} for a in m["authors"]],
                "project": m["project"],
                "kind": m["kind"],
                "status": m["status"],
                "keywords": m.get("keywords", []),
                "builds_on": m.get("builds_on", []),
                "supersedes": m.get("supersedes"),
                "formerly": m.get("formerly", []),
                "license": m.get("license"),
                "private_code": m.get("private_code", []),
            }
        )
    f["updated"] = max([f.get("updated") or "", m["published"]])
    sup = m.get("supersedes")
    if sup and sup in index["findings"] and sup != fid:
        index["findings"][sup]["superseded_by"] = fid


def apply_event(index: dict[str, Any], e: dict[str, Any]) -> None:
    f = index["findings"].get(e["id"])
    if f is None:
        return
    kind = e["type"]
    if kind in STATES:
        f["state"] = STATES[kind]
        f["state_reason"] = e.get("reason") if kind != "restore" else None
        f["state_date"] = e["at"] if kind != "restore" else None
    elif kind == "supersede":
        f["superseded_by"] = e.get("superseded_by")
    elif kind == "link":
        for key in ("doi", "stacks_url"):
            if key in e:
                f[key] = e[key] or None
    f["events"].append({k: v for k, v in e.items() if k != "id"})
    f["updated"] = max([f.get("updated") or "", e["at"]])


def event_key(finding_id: str, kind: str, at: str) -> str:
    stamp = at.replace("-", "").replace(":", "")
    return f"{finding_id}/_events/{stamp}-{kind}.json"


def write_event(store: Store, event: dict[str, Any]) -> dict[str, Any]:
    """Record a status change once, then fold it into the index."""
    if event["type"] not in EVENT_TYPES:
        raise ValueError(f"unknown event {event['type']!r}")
    key = event_key(event["id"], event["type"], event["at"])
    store.put_bytes(key, dumps(event), "application/json; charset=utf-8", if_none_match=True)
    return update(store, lambda idx: apply_event(idx, event))


def complete_versions(store: Store) -> tuple[list[dict[str, Any]], list[str]]:
    """Every finding.json whose files are all present, plus the keys of incomplete ones."""
    keys = set(store.list(""))
    good: list[dict[str, Any]] = []
    incomplete: list[str] = []
    for key in sorted(keys):
        m = MANIFEST_KEY.match(key)
        if not m:
            continue
        got = store.get(key)
        if got is None:
            continue
        manifest = json.loads(got[0])
        prefix = f"{m.group(1)}/v{m.group(2)}/"
        archive = f"{m.group(1)}-v{m.group(2)}.zip"
        needed = [f["path"] for f in manifest["files"]] + [
            "SHA256SUMS",
            archive,
            archive + ".sha256",
        ]
        if all(prefix + rel in keys for rel in needed):
            good.append(manifest)
        else:
            incomplete.append(key)
    return good, incomplete


def rebuild(store: Store) -> tuple[dict[str, Any], list[str]]:
    """Recreate the index from versions and events alone, in the order they happened."""
    manifests, incomplete = complete_versions(store)
    events = []
    for key in store.list(""):
        if EVENT_KEY.match(key):
            got = store.get(key)
            if got:
                events.append(json.loads(got[0]))
    steps: list[tuple[str, int, dict[str, Any]]] = [(m["published"], 0, m) for m in manifests]
    steps += [(e["at"], 1, e) for e in events]
    steps.sort(key=lambda s: (s[0], s[1], s[2].get("id", ""), s[2].get("version", 0)))
    index = empty()
    for _at, kind, item in steps:
        if kind == 0:
            apply_version(index, item)
        else:
            apply_event(index, item)
    index["updated"] = now()
    return index, incomplete


def write(store: Store, index: dict[str, Any]) -> None:
    _old, etag = load(store)
    store.put_bytes(
        INDEX_KEY,
        dumps(index),
        "application/json; charset=utf-8",
        if_none_match=etag is None,
        if_match=etag,
    )

"""afh-findings: check, preview and publish findings to findings.afh.org."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from importlib import resources
from pathlib import Path

from afh_findings import __version__, checks, config, preview, publish, registry
from afh_findings.issues import Issue
from afh_findings.store import open_store


def _print_issues(issues: list[Issue]) -> None:
    for issue in sorted(issues, key=lambda i: (i.level != "error", i.code)):
        print(f"  {issue}")


def _cfg(args: argparse.Namespace) -> config.Config:
    cfg = config.load(Path(args.config)) if args.config else config.load()
    if args.store:
        cfg.store = args.store
    if getattr(args, "publisher", None):
        cfg.publisher = args.publisher
    return cfg


def cmd_new(args: argparse.Namespace) -> int:
    target = Path(args.dir)
    if target.exists() and any(target.iterdir()):
        print(f"{target} exists and is not empty", file=sys.stderr)
        return 1
    template = resources.files("afh_findings").joinpath("templates/basic")
    target.mkdir(parents=True, exist_ok=True)
    for item in template.iterdir():
        if item.is_file():
            text = item.read_text(encoding="utf-8")
            if args.project:
                text = text.replace("project: my-project", f"project: {args.project}")
            (target / item.name).write_text(text, encoding="utf-8")
    (target / "data").mkdir(exist_ok=True)
    print(f"Started a finding in {target}. Edit finding.yaml and index.html, then:")
    print(f"  afh-findings check {target}\n  afh-findings preview {target}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    checked = checks.check_bundle(
        Path(args.dir),
        cfg,
        extra_profiles=args.profile,
        profile_files=[Path(p) for p in args.profile_file],
        network=not args.offline,
    )
    _print_issues(checked.issues)
    counts = checks.summarize(checked.issues)
    profiles = ", ".join(checked.profiles) or "core only"
    if checked.ok:
        print(f"OK ({profiles}): {counts['warnings']} warning(s), {len(checked.files)} files")
        if checked.source and checked.source.core.get("check") and args.run_check:
            ok, out = checks.run_check_command(
                Path(args.dir).resolve(), checked.source.core["check"]
            )
            print(out)
            return 0 if ok else 1
        return 0
    print(f"Not ready ({profiles}): {counts['errors']} error(s), {counts['warnings']} warning(s)")
    return 1


def cmd_preview(args: argparse.Namespace) -> int:
    preview.serve(
        Path(args.dir), _cfg(args), port=args.port, finding_id=args.id, version=args.version
    )
    return 0


def _confirm(yes: bool):
    def ask(text: str) -> bool:
        print("About to publish:\n" + text)
        if yes:
            return True
        if not sys.stdin.isatty():
            print("Not a terminal: pass --yes to publish without a prompt.", file=sys.stderr)
            return False
        return input("Publish? [y/N] ").strip().lower() in ("y", "yes")

    return ask


def cmd_publish(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    if not cfg.publisher:
        print(
            'Set publisher = "Your Name" in ~/.config/afh-findings/config.toml (or --publisher).',
            file=sys.stderr,
        )
        return 1
    change = {"type": args.change, "summary": args.summary} if args.change else None
    if bool(args.change) != bool(args.summary):
        print("--change and --summary go together", file=sys.stderr)
        return 2
    store = open_store(cfg)
    try:
        result = publish.publish(
            Path(args.dir),
            cfg,
            store,
            revise=args.revise,
            change=change,
            published_at=args.published_at,
            confirm=_confirm(args.yes),
            extra_profiles=args.profile,
            profile_files=[Path(p) for p in args.profile_file],
            network=not args.offline,
        )
    except publish.PublishError as exc:
        _print_issues(exc.issues)
        print(f"Not published: {exc}", file=sys.stderr)
        return 1
    _print_issues(result.warnings)
    how = "resumed and finished" if result.resumed else "published"
    print(f"{result.finding_id} v{result.version} {how}: {result.url}")
    print(f"  {result.uploaded} files uploaded, {result.skipped} already there")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    store = open_store(cfg)
    if args.action in ("retract", "withdraw") and not args.yes:
        if not sys.stdin.isatty() or input(
            f"{args.action} {args.id}? [y/N] "
        ).strip().lower() not in ("y", "yes"):
            print("Nothing changed.")
            return 1
    try:
        publish.set_status(
            store,
            args.id,
            args.action,
            reason=args.reason,
            superseded_by=args.by,
            doi=args.doi,
            stacks_url=args.stacks_url,
            by=cfg.publisher,
            at=args.at,
        )
    except publish.PublishError as exc:
        print(f"Nothing changed: {exc}", file=sys.stderr)
        return 1
    print(f"{args.id}: {args.action} recorded")
    if args.action == "withdraw":
        print(
            "  The site now answers 410 for it. Its files stay in the bucket until an admin deletes them."
        )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    index, _ = registry.load(open_store(_cfg(args)))
    if args.json:
        print(json.dumps(index, indent=1))
        return 0
    width = shutil.get_terminal_size((100, 20)).columns
    for fid, f in sorted(index["findings"].items()):
        flags = "" if f["state"] == "active" else f" [{f['state']}]"
        flags += f" [superseded by {f['superseded_by']}]" if f.get("superseded_by") else ""
        line = f"{fid} v{f['latest']} {f['status'][:4]} {f['project']:<10} {f['title']}{flags}"
        print(line[: width - 1])
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    index, _ = registry.load(open_store(_cfg(args)))
    f = index["findings"].get(args.id)
    if f is None:
        print(f"{args.id} is not published", file=sys.stderr)
        return 1
    print(json.dumps(f, indent=1, ensure_ascii=False))
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    store = open_store(_cfg(args))
    index, incomplete = registry.rebuild(store)
    for key in incomplete:
        print(f"  skipped (files missing, an interrupted publish?): {key}")
    print(f"{len(index['findings'])} findings rebuilt from {store.describe()}")
    if args.dry_run:
        return 0
    registry.write(store, index)
    print("registry written")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    store = open_store(_cfg(args))
    fid, _, v = args.ref.partition("/v")
    problems = publish.verify(store, fid, int(v) if v else None)
    for p in problems:
        print(f"  {p}")
    print("OK: every file matches its checksum" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="afh-findings", description=__doc__)
    p.add_argument("--version", action="version", version=f"afh-findings {__version__}")
    p.add_argument("--config", help="settings file (default ~/.config/afh-findings/config.toml)")
    p.add_argument("--store", help="'r2' (default) or 'file:/path' to publish into a local folder")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("new", help="start a finding from the template")
    s.add_argument("dir")
    s.add_argument("--project")
    s.set_defaults(func=cmd_new)

    def profile_args(s: argparse.ArgumentParser) -> None:
        s.add_argument("--profile", action="append", default=[], help="also apply this profile")
        s.add_argument(
            "--profile-file", action="append", default=[], help="try a profile from a .py file"
        )
        s.add_argument("--offline", action="store_true", help="skip checks that need the network")

    s = sub.add_parser("check", help="check a bundle against the standard and its profiles")
    s.add_argument("dir")
    s.add_argument(
        "--run-check", action="store_true", help="also run the finding's `check` command"
    )
    profile_args(s)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("preview", help="serve a bundle locally as the site will")
    s.add_argument("dir")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--id", default="F0000", help="number to show (default F0000)")
    s.add_argument("--version", type=int, default=1)
    s.set_defaults(func=cmd_preview)

    s = sub.add_parser("publish", help="publish a new finding, or a new version with --revise")
    s.add_argument("dir")
    s.add_argument("--revise", metavar="FNNNN", help="publish as the next version of this finding")
    s.add_argument(
        "--change", choices=publish.CHANGE_TYPES, help="what kind of change (with --revise)"
    )
    s.add_argument("--summary", help="one line on what changed and why (with --revise)")
    s.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    s.add_argument("--publisher", help="your name (default: publisher in the config)")
    s.add_argument("--published-at", help=argparse.SUPPRESS)  # migration: keep original dates
    profile_args(s)
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser(
        "status", help="retract, withdraw, restore, supersede, or link a DOI / Stacks page"
    )
    s.add_argument("id")
    s.add_argument("action", choices=registry.EVENT_TYPES)
    s.add_argument("--reason", help="shown to readers (retract, withdraw)")
    s.add_argument("--by", help="the finding that supersedes this one")
    s.add_argument("--doi")
    s.add_argument("--stacks-url")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--at", help=argparse.SUPPRESS)
    s.add_argument("--publisher", help="your name (default: publisher in the config)")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("list", help="list published findings")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one finding's registry entry")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("verify", help="download a published version and check its checksums")
    s.add_argument("ref", metavar="FNNNN[/vN]")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser(
        "reindex", help="rebuild the registry from the published versions and events"
    )
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_reindex)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

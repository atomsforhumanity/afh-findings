"""Someone else can check the numbers and rerun the work from the download alone."""

from __future__ import annotations

from afh_findings import manifest as mf
from afh_findings.issues import Issue, error

NAME = "reproducible"
README = "reproduce/README.md"


def check(source: mf.Source, files: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    if not source.core.get("check"):
        issues.append(
            error(
                NAME,
                "needs a `check` command that recomputes the numbers from data/",
                mf.SOURCE_NAME,
            )
        )
    if README not in files:
        issues.append(
            error(
                NAME, f"needs {README}: how to check the numbers and how to rerun, for a stranger"
            )
        )
    _items, none = mf.materials(source.core.get("code"))
    if none:
        issues.append(error(NAME, "needs the code that produced the results (`code: none` given)"))
    return issues

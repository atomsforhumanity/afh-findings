"""Problems found while checking a bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    level: Level
    code: str
    message: str
    path: str | None = None

    def __str__(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"{self.level}: {self.code}{where}: {self.message}"


def error(code: str, message: str, path: str | None = None) -> Issue:
    return Issue("error", code, message, path)


def warning(code: str, message: str, path: str | None = None) -> Issue:
    return Issue("warning", code, message, path)


def has_errors(issues: list[Issue]) -> bool:
    return any(i.level == "error" for i in issues)

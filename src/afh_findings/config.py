"""Settings: defaults, then ~/.config/afh-findings/config.toml, then AFH_FINDINGS_* env vars."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "afh-findings"
    / "config.toml"
)


@dataclass
class Config:
    # "r2" publishes to Cloudflare R2; "file:/some/dir" publishes to a local folder (tests, dry runs).
    store: str = "r2"
    account_id: str | None = None
    endpoint: str | None = None
    bucket: str = "afh-findings"
    access_key_id: str | None = None
    secret_access_key: str | None = None
    publisher: str | None = None
    site_url: str = "https://findings.afh.org"
    affiliation: str | None = "Atoms for Humanity, Astera Institute"
    # Host and machine names that must never appear in published files.
    internal_hosts: list[str] = field(
        default_factory=lambda: ["afh-services", "melodi", "afh-c01", "afh-k3s"]
    )

    @property
    def r2_endpoint(self) -> str | None:
        if self.endpoint:
            return self.endpoint
        if self.account_id:
            return f"https://{self.account_id}.r2.cloudflarestorage.com"
        return None


def load(path: Path = CONFIG_PATH, env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ) if env is None else env
    cfg = Config()
    names = {f.name for f in fields(Config)}
    if path.is_file():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        unknown = set(data) - names
        if unknown:
            raise ValueError(f"{path}: unknown settings {sorted(unknown)}")
        for key, value in data.items():
            if key == "internal_hosts":
                value = cfg.internal_hosts + [h for h in value if h not in cfg.internal_hosts]
            setattr(cfg, key, value)
    for name in names:
        value = env.get(f"AFH_FINDINGS_{name.upper()}")
        if value is None:
            continue
        if name == "internal_hosts":
            cfg.internal_hosts = cfg.internal_hosts + [
                h.strip() for h in value.split(",") if h.strip()
            ]
        else:
            setattr(cfg, name, value)
    cfg.site_url = cfg.site_url.rstrip("/")
    return cfg

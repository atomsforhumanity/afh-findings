"""Where findings live: Cloudflare R2, or a local folder with the same rules.

Only two writes are conditional, and they carry the whole consistency story:
- a version is claimed by creating its finding.json with If-None-Match: * (R2 checks this
  atomically, so two publishers can never get the same number), and
- the registry is replaced with If-Match on the ETag that was read.
Everything else is written once into a prefix the claim already owns.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import shutil
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from afh_findings.config import Config

MULTIPART_THRESHOLD = 64 * 1024**2


class PreconditionFailed(Exception):
    """A conditional write lost: the key already exists, or changed since it was read."""


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size: int
    etag: str
    metadata: dict[str, str]


class Store(ABC):
    @abstractmethod
    def get(self, key: str) -> tuple[bytes, str] | None: ...

    @abstractmethod
    def head(self, key: str) -> ObjectInfo | None: ...

    @abstractmethod
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
        *,
        if_none_match: bool = False,
        if_match: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str: ...

    @abstractmethod
    def put_file(
        self, key: str, path: Path, content_type: str, metadata: dict[str, str] | None = None
    ) -> None: ...

    @abstractmethod
    def list(self, prefix: str = "") -> Iterator[str]: ...

    @abstractmethod
    def describe(self) -> str: ...


class FileStore(Store):
    """A folder that behaves like the bucket, for tests and local dry runs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / ".meta").mkdir(exist_ok=True)

    def describe(self) -> str:
        return f"folder {self.root}"

    def _path(self, key: str) -> Path:
        if key.startswith("/") or ".." in key.split("/") or key.startswith(".meta"):
            raise ValueError(f"bad key {key!r}")
        return self.root / key

    def _meta_path(self, key: str) -> Path:
        return self.root / ".meta" / (key + ".json")

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        with (self.root / ".meta" / ".lock").open("a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    @staticmethod
    def _etag(data: bytes) -> str:
        return '"' + hashlib.md5(data).hexdigest() + '"'

    def get(self, key: str) -> tuple[bytes, str] | None:
        p = self._path(key)
        if not p.is_file():
            return None
        data = p.read_bytes()
        return data, self._etag(data)

    def head(self, key: str) -> ObjectInfo | None:
        p = self._path(key)
        if not p.is_file():
            return None
        meta = {}
        mp = self._meta_path(key)
        if mp.is_file():
            meta = json.loads(mp.read_text())
        return ObjectInfo(
            key, p.stat().st_size, self._etag(p.read_bytes()), meta.get("metadata", {})
        )

    def _write_meta(self, key: str, content_type: str, metadata: dict[str, str] | None) -> None:
        mp = self._meta_path(key)
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({"content_type": content_type, "metadata": metadata or {}}))

    def put_bytes(
        self, key, data, content_type, *, if_none_match=False, if_match=None, metadata=None
    ) -> str:
        p = self._path(key)
        with self._lock():
            exists = p.is_file()
            if if_none_match and exists:
                raise PreconditionFailed(key)
            if if_match is not None and (not exists or self._etag(p.read_bytes()) != if_match):
                raise PreconditionFailed(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".partial")
            tmp.write_bytes(data)
            tmp.replace(p)
            self._write_meta(key, content_type, metadata)
        return self._etag(data)

    def put_file(self, key, path, content_type, metadata=None) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".partial")
        shutil.copyfile(path, tmp)
        tmp.replace(p)
        self._write_meta(key, content_type, metadata)

    def list(self, prefix: str = "") -> Iterator[str]:
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and ".meta" not in p.relative_to(self.root).parts:
                key = p.relative_to(self.root).as_posix()
                if key.startswith(prefix) and not key.endswith(".partial"):
                    yield key

    def content_type(self, key: str) -> str | None:
        mp = self._meta_path(key)
        return json.loads(mp.read_text())["content_type"] if mp.is_file() else None


class R2Store(Store):
    """Cloudflare R2 through its S3 API."""

    def __init__(self, endpoint: str, bucket: str, key_id: str, secret: str) -> None:
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket = bucket
        self.endpoint = endpoint
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name="auto",
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
                # R2 doesn't need boto3's newer default checksum headers.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def describe(self) -> str:
        return f"R2 bucket {self.bucket}"

    @staticmethod
    def _code(exc: Exception) -> tuple[str, int]:
        resp: dict[str, Any] = getattr(exc, "response", {}) or {}
        return str(resp.get("Error", {}).get("Code", "")), int(
            resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        )

    def get(self, key: str) -> tuple[bytes, str] | None:
        from botocore.exceptions import ClientError

        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code, status = self._code(exc)
            if code in ("NoSuchKey", "404") or status == 404:
                return None
            raise
        return obj["Body"].read(), obj["ETag"]

    def head(self, key: str) -> ObjectInfo | None:
        from botocore.exceptions import ClientError

        try:
            obj = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code, status = self._code(exc)
            if code in ("NoSuchKey", "404", "NotFound") or status == 404:
                return None
            raise
        return ObjectInfo(key, obj["ContentLength"], obj["ETag"], obj.get("Metadata", {}))

    def put_bytes(
        self, key, data, content_type, *, if_none_match=False, if_match=None, metadata=None
    ) -> str:
        from botocore.exceptions import ClientError

        args: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "Metadata": metadata or {},
        }
        if if_none_match:
            args["IfNoneMatch"] = "*"
        if if_match is not None:
            args["IfMatch"] = if_match
        try:
            resp = self.client.put_object(**args)
        except ClientError as exc:
            code, status = self._code(exc)
            if status in (409, 412) or code in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise PreconditionFailed(key) from exc
            raise
        return str(resp["ETag"])

    def put_file(self, key, path, content_type, metadata=None) -> None:
        from boto3.s3.transfer import TransferConfig

        self.client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "Metadata": metadata or {}},
            Config=TransferConfig(
                multipart_threshold=MULTIPART_THRESHOLD, multipart_chunksize=MULTIPART_THRESHOLD
            ),
        )

    def list(self, prefix: str = "") -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]


def open_store(cfg: Config) -> Store:
    if cfg.store.startswith("file:"):
        return FileStore(Path(cfg.store[len("file:") :]).expanduser())
    if cfg.store != "r2":
        raise ValueError(f"unknown store {cfg.store!r}: use 'r2' or 'file:/path'")
    missing = [
        name
        for name, value in (
            ("account_id or endpoint", cfg.r2_endpoint),
            ("access_key_id", cfg.access_key_id),
            ("secret_access_key", cfg.secret_access_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "R2 settings missing: "
            + ", ".join(missing)
            + " (set them in ~/.config/afh-findings/config.toml or AFH_FINDINGS_* env vars)"
        )
    assert cfg.r2_endpoint and cfg.access_key_id and cfg.secret_access_key
    return R2Store(cfg.r2_endpoint, cfg.bucket, cfg.access_key_id, cfg.secret_access_key)

"""Immutable raw file store keyed by content hash (design doc 9.3).

Key layout: ``kind/yyyy/mm/sha256.ext``. Talks the S3 API through boto3, so MinIO locally and any
managed S3 service when hosted are a configuration change only. A local directory store is used
by tests and single-machine development.

XML (results XBRL) is stored gzipped, about 12 times smaller; ``get`` returns the original bytes,
so the key's hash still matches. PDFs and Excel files are already compressed and stored as-is.
"""

import gzip
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from analekh.config import get_settings


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key(kind: str, digest: str, ext: str, when: datetime | None = None) -> str:
    when = when or datetime.now(UTC)
    return f"{kind}/{when:%Y}/{when:%m}/{digest}.{ext.lstrip('.')}"


GZIP_MAGIC = b"\x1f\x8b"  # XML, PDF (%PDF) and xlsx (PK) never start with these bytes
COMPRESSED_TYPES = {"application/xml"}


def pack(data: bytes, content_type: str) -> bytes:
    """Bytes as stored: gzipped for XML. mtime=0 keeps the output the same for the same input."""
    return gzip.compress(data, mtime=0) if content_type in COMPRESSED_TYPES else data


def unpack(data: bytes) -> bytes:
    """Original bytes from stored ones; files stored before compression come back unchanged."""
    return gzip.decompress(data) if data[:2] == GZIP_MAGIC else data


class ObjectStore(Protocol):
    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(pack(data, content_type))

    def get(self, key: str) -> bytes:
        return unpack((self.root / key).read_bytes())

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()


class StorageUnavailable(RuntimeError):
    """Object storage can't be reached (e.g. MinIO not running). The API answers 503."""


class S3Store:
    def __init__(self, client: Any = None) -> None:
        import boto3
        from botocore.config import Config

        s = get_settings()
        self.bucket = s.minio_bucket
        self.endpoint = s.minio_endpoint
        scheme = "https" if s.minio_secure else "http"
        # Fail in seconds, not minutes, when storage is down: botocore's defaults (60 s connect
        # timeout, several retries) leave API requests hanging.
        config = Config(
            connect_timeout=2,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 1},
        )
        self.client = client or boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{s.minio_endpoint}",
            aws_access_key_id=s.minio_access_key,
            aws_secret_access_key=s.minio_secret_key,
            config=config,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
        except (EndpointConnectionError, ConnectTimeoutError) as exc:
            raise StorageUnavailable(f"object storage is not reachable at {self.endpoint}") from exc

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        if not self.exists(key):
            self.write(key, data, content_type)

    def write(self, key: str, data: bytes, content_type: str) -> None:
        """Write even if the key exists (``put`` never does); used to compress stored files."""
        body = pack(data, content_type)
        if body is data:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        else:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                ContentEncoding="gzip",
            )

    def get(self, key: str) -> bytes:
        body: bytes = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return unpack(body)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


def default_store() -> ObjectStore:
    return S3Store()

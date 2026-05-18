"""S3-compatible storage backend (AWS S3, MinIO)."""

from __future__ import annotations

import structlog
import boto3
from botocore.exceptions import ClientError

from app.infrastructure.storage.base import StorageBackend

logger = structlog.get_logger()

PRESIGNED_URL_EXPIRY = 900  # 15 minutes


class S3Storage(StorageBackend):
    """S3-compatible storage via boto3."""

    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def _safe_path(self, path: str) -> str:
        if ".." in path:
            raise ValueError(f"Path traversal detected: {path}")
        return path.lstrip("/")

    async def save(self, path: str, data: bytes) -> str:
        key = self._safe_path(path)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return f"s3://{self._bucket}/{key}"

    async def load(self, path: str) -> bytes:
        key = self._safe_path(path)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"S3 key not found: {key}")
            raise

    async def delete(self, path: str) -> None:
        key = self._safe_path(path)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def list(self, prefix: str = "") -> list[str]:
        safe_prefix = self._safe_path(prefix) if prefix else ""
        response = self._client.list_objects_v2(Bucket=self._bucket, Prefix=safe_prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]

    async def get_url(self, path: str) -> str:
        key = self._safe_path(path)
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
        logger.info("s3_presigned_url_generated", key=key, expiry_seconds=PRESIGNED_URL_EXPIRY)
        return url

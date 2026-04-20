"""
Async S3 client wrapper for EventSnap.

Wraps aioboto3 so the rest of the application never imports boto3/aioboto3
directly. All public methods are async and raise S3Error on failure.

Usage (from a FastAPI dependency or service):

    from src.s3.client import S3Client, get_s3_client

    async def my_endpoint(s3: S3Client = Depends(get_s3_client)):
        url = await s3.generate_presigned_upload_url("photos/x/y/original.jpg")
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aioboto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from src.config import config

logger = logging.getLogger(__name__)

# Type alias for the raw aioboto3 S3 resource object
_S3ResourceType = object


class S3Error(Exception):
    """Raised when any S3 operation fails. Wraps the underlying boto exception."""


class S3Client:
    """
    Stateless async S3 client.

    One instance is created per application lifetime (see get_s3_client).
    The underlying aioboto3 session is thread-safe and shared; individual
    resource/client contexts are acquired per-call to avoid holding open
    connections longer than necessary.

    All methods convert boto3/botocore exceptions into S3Error so callers
    only need to handle one exception type.
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        base_url: str,
        presign_upload_ttl: int,
        presign_download_ttl: int,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url or None
        self._base_url = base_url.rstrip("/")
        self._presign_upload_ttl = presign_upload_ttl
        self._presign_download_ttl = presign_download_ttl
        self._client_config = BotoConfig(signature_version="s3v4")

        self._session = aioboto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator:
        """
        Yield a raw boto3 S3 client for a single operation.
        Using a context manager per call is recommended by aioboto3.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            config=self._client_config,
        ) as client:
            yield client

    def _wrap(self, exc: Exception, operation: str, key: str) -> S3Error:
        """Convert a boto exception into a domain S3Error and log it."""
        logger.error("S3 %s failed for key=%r: %s", operation, key, exc)
        return S3Error(f"S3 {operation} failed for key {key!r}: {exc}")

    # ------------------------------------------------------------------
    # URL helpers (no I/O)
    # ------------------------------------------------------------------

    def build_public_url(self, key: str) -> str:
        """
        Build the public (CDN or bucket) URL for a stored object.

        The base URL comes from S3_BASE_URL in config. If the bucket
        is private, use generate_presigned_download_url instead.
        """
        return f"{self._base_url}/{key}"

    # ------------------------------------------------------------------
    # Presigned URLs
    # ------------------------------------------------------------------

    async def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        *,
        ttl: int | None = None,
    ) -> str:
        """
        Return a presigned PUT URL that the client can use to upload a file
        directly to S3 without routing through the API server.

        The caller should set the Content-Type header to *content_type* when
        performing the PUT, otherwise S3 rejects the request.

        Args:
            key: S3 object key (e.g. "photos/{event_id}/{photo_id}/original.jpg").
            content_type: MIME type the client must send (e.g. "image/jpeg").
            ttl: Override the default presign TTL (seconds).
        """
        expires_in = ttl if ttl is not None else self._presign_upload_ttl
        try:
            async with self._get_client() as client:
                url: str = await client.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=expires_in,
                )
            logger.debug("Generated presigned upload URL for key=%r (ttl=%ds)", key, expires_in)
            return url
        except (BotoCoreError, ClientError) as exc:
            raise self._wrap(exc, "generate_presigned_upload_url", key)

    async def generate_presigned_download_url(
        self,
        key: str,
        *,
        ttl: int | None = None,
    ) -> str:
        """
        Return a presigned GET URL for a private object.

        Use this when the bucket is not publicly accessible. For CDN-fronted
        buckets, use build_public_url instead.

        Args:
            key: S3 object key.
            ttl: Override the default presign TTL (seconds).
        """
        expires_in = ttl if ttl is not None else self._presign_download_ttl
        try:
            async with self._get_client() as client:
                url: str = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
            logger.debug("Generated presigned download URL for key=%r (ttl=%ds)", key, expires_in)
            return url
        except (BotoCoreError, ClientError) as exc:
            raise self._wrap(exc, "generate_presigned_download_url", key)

    # ------------------------------------------------------------------
    # Object lifecycle
    # ------------------------------------------------------------------

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """
        Upload raw bytes to S3 under *key*.

        Prefer generate_presigned_upload_url for large files so the binary
        data does not pass through the API server. This method is mainly
        useful for small server-generated files (e.g. thumbnails produced
        by a background worker).

        Args:
            key: Destination S3 key.
            data: File content as bytes.
            content_type: MIME type stored as object metadata.
        """
        try:
            async with self._get_client() as client:
                await client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            logger.debug("Uploaded %d bytes to key=%r", len(data), key)
        except (BotoCoreError, ClientError) as exc:
            raise self._wrap(exc, "upload_bytes", key)

    async def delete_object(self, key: str) -> None:
        """
        Delete a single object from S3.

        S3 delete is idempotent — deleting a non-existent key is not an error.

        Args:
            key: S3 object key to remove.
        """
        try:
            async with self._get_client() as client:
                await client.delete_object(Bucket=self._bucket, Key=key)
            logger.debug("Deleted S3 object key=%r", key)
        except (BotoCoreError, ClientError) as exc:
            raise self._wrap(exc, "delete_object", key)

    async def delete_objects(self, keys: list[str]) -> None:
        """
        Batch-delete up to 1000 S3 objects in a single API call.

        Splits larger lists into 1000-item chunks automatically.
        Partial failures (individual keys that could not be deleted) are
        collected and raised together as a single S3Error.

        Args:
            keys: List of S3 object keys to remove.
        """
        if not keys:
            return

        errors: list[str] = []

        # S3 DeleteObjects accepts at most 1000 keys per call
        for chunk_start in range(0, len(keys), 1000):
            chunk = keys[chunk_start : chunk_start + 1000]
            objects = [{"Key": k} for k in chunk]
            try:
                async with self._get_client() as client:
                    response = await client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": objects, "Quiet": False},
                    )
                # Collect per-key errors from the response
                for err in response.get("Errors", []):
                    msg = f"key={err['Key']!r} code={err['Code']} message={err['Message']}"
                    logger.error("S3 batch delete partial failure: %s", msg)
                    errors.append(msg)
            except (BotoCoreError, ClientError) as exc:
                raise self._wrap(exc, "delete_objects", str(chunk))

        if errors:
            raise S3Error(f"S3 delete_objects had {len(errors)} failure(s): {'; '.join(errors)}")

    async def object_exists(self, key: str) -> bool:
        """
        Return True if the object exists in the bucket, False otherwise.

        Uses head_object which is cheaper than get_object for existence checks.

        Args:
            key: S3 object key.
        """
        try:
            async with self._get_client() as client:
                await client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            error = exc.response.get("Error", {})
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status_code == 404 or error.get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
                "Not Found",
            }:
                return False
            raise self._wrap(exc, "object_exists", key)
        except BotoCoreError as exc:
            raise self._wrap(exc, "object_exists", key)

    async def copy_object(self, source_key: str, dest_key: str) -> None:
        """
        Server-side copy an object within the same bucket.

        Useful for creating thumbnails from originals without re-uploading,
        or for moving objects between key prefixes.

        Args:
            source_key: Key of the source object.
            dest_key: Key of the destination object.
        """
        copy_source = {"Bucket": self._bucket, "Key": source_key}
        try:
            async with self._get_client() as client:
                await client.copy_object(
                    CopySource=copy_source,
                    Bucket=self._bucket,
                    Key=dest_key,
                )
            logger.debug("Copied S3 object %r -> %r", source_key, dest_key)
        except (BotoCoreError, ClientError) as exc:
            raise self._wrap(exc, "copy_object", f"{source_key} -> {dest_key}")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

# Module-level singleton — created once at import time using config.
# Config raises at startup if required env vars are missing,
# so this will never silently use empty credentials.
_s3_client: S3Client = S3Client(
    bucket=config.S3_BUCKET_NAME,
    region=config.S3_REGION,
    endpoint_url=config.S3_ENDPOINT_URL,
    access_key_id=config.S3_ACCESS_KEY_ID,
    secret_access_key=config.S3_SECRET_ACCESS_KEY,
    base_url=config.S3_BASE_URL,
    presign_upload_ttl=config.S3_PRESIGN_UPLOAD_TTL,
    presign_download_ttl=config.S3_PRESIGN_DOWNLOAD_TTL,
)


def get_s3_client() -> S3Client:
    """
    FastAPI dependency that returns the shared S3Client singleton.

    Usage in a router:

        from fastapi import Depends
        from src.s3.client import S3Client, get_s3_client

        @router.post("/photos/upload-url")
        async def request_upload_url(s3: S3Client = Depends(get_s3_client)):
            ...
    """
    return _s3_client

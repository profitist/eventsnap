"""
src.s3 — S3 / object-storage integration for EventSnap.

Public surface:
    S3Client       — the async client class
    S3Error        — exception raised on any S3 failure
    get_s3_client  — FastAPI Depends()-compatible factory
    keys           — sub-module with S3 key construction helpers
"""

from src.s3.client import S3Client, S3Error, get_s3_client

__all__ = [
    "S3Client",
    "S3Error",
    "get_s3_client",
]
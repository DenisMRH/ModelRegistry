from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from api.core.config import settings


class S3Client:
    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url or settings.minio_url
        self._access_key = access_key or settings.minio_access_key
        self._secret_key = secret_key or settings.minio_secret_key
        self._bucket_name = bucket_name or settings.minio_bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )
        presign_endpoint = settings.minio_public_url or self._endpoint_url
        self._presign_client = (
            boto3.client(
                "s3",
                endpoint_url=presign_endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                config=BotoConfig(signature_version="s3v4"),
                region_name="us-east-1",
            )
            if presign_endpoint != self._endpoint_url
            else self._client
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket_name)
            else:
                raise

    def generate_presigned_upload_url(
        self,
        object_name: str,
        expiry: int = 3600,
        **kwargs: Any,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": object_name,
                **kwargs,
            },
            ExpiresIn=expiry,
        )

    def generate_presigned_download_url(
        self,
        object_name: str,
        expiry: int = 3600,
        **kwargs: Any,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": object_name,
                **kwargs,
            },
            ExpiresIn=expiry,
        )


s3_client = S3Client()

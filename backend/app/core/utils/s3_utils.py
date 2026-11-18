import logging
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

SERVER_ROLE_NOT_ALLOWED = (
    "Enter the access key and secret key: this server does not allow S3 data sources to use its own AWS access."
)


class ServerRoleNotAllowedError(ValueError):
    """An S3 data source has no keys and the server does not allow its own AWS access."""


def s3_data_source_keys(connection_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """The data source's access key and secret key; both None means the server's own AWS access."""
    access_key = connection_data.get("access_key") or None
    secret_key = connection_data.get("secret_key") or None
    has_no_keys = access_key is None and secret_key is None
    if has_no_keys and not settings.S3_DATA_SOURCES_USE_SERVER_ROLE:
        raise ServerRoleNotAllowedError(SERVER_ROLE_NOT_ALLOWED)
    return access_key, secret_key


def is_s3_not_found_error(error: ClientError) -> bool:
    """Return whether an S3 ``ClientError`` represents a missing object."""
    response = error.response or {}
    code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404


def build_s3_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    region_name: Optional[str] = None,
    aws_session_token: Optional[str] = None,
):
    """A boto3 S3 client; empty settings are left out, so empty keys use the server's AWS role."""
    settings = {
        "region_name": region_name,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "aws_session_token": aws_session_token,
    }
    client_options: Dict[str, Any] = {name: value for name, value in settings.items() if value}
    return boto3.client("s3", **client_options)


class S3Client:
    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """
        Initialize S3 client with credentials and bucket name.
        If credentials are not provided, boto3 will use the default credential chain.
        """
        self.bucket_name = bucket_name
        self.s3_client = build_s3_client(aws_access_key_id, aws_secret_access_key, region_name, aws_session_token)

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List files in the S3 bucket with pagination support.

        Args:
            prefix: Filter files by prefix (folder path)
            max_keys: Maximum number of keys to return in one request
            continuation_token: Token for pagination
            file_extensions: List of file extensions to filter (e.g., ['.pdf', '.txt'])

        Returns:
            Dictionary containing:
            - files: List of file information (name, size, last_modified)
            - next_token: Token for the next page of results
            - is_truncated: Boolean indicating if more results are available
        """
        try:
            # Prepare list_objects_v2 parameters
            cleaned_prefix = (prefix or "").lstrip("/").strip()
            params = {"Bucket": self.bucket_name, "MaxKeys": max_keys}
            if cleaned_prefix:
                params["Prefix"] = cleaned_prefix

            if continuation_token:
                params["ContinuationToken"] = continuation_token

            logger.info(f"Listing files from S3: {params}")

            # Make the API call
            response = self.s3_client.list_objects_v2(**params)

            # Process the results
            files = []
            for obj in response.get("Contents", []):
                file_name = obj["Key"]

                # Apply file extension filter if specified
                if file_extensions:
                    if not any(file_name.lower().endswith(ext.lower()) for ext in file_extensions):
                        continue

                files.append(
                    {
                        "key": file_name,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"],
                    }
                )

            return {
                "files": files,
                "next_token": response.get("NextContinuationToken"),
                "is_truncated": response.get("IsTruncated", False),
            }

        except ClientError as e:
            logger.error(f"Error listing files from S3: {str(e)}")
            raise

    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file.

        Args:
            file_key: The key (path) of the file in the bucket

        Returns:
            Dictionary containing file metadata
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)

            return {
                "key": file_key,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"].isoformat(),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
                "etag": response["ETag"],
            }
        except ClientError as e:
            logger.error(f"Error getting file metadata from S3: {str(e)}")
            raise

    def download_file(self, file_key: str, local_path: str) -> bool:
        """
        Download a file from S3 to a local path.

        Args:
            file_key: The key (path) of the file in the bucket
            local_path: Local path where the file should be saved

        Returns:
            Boolean indicating success
        """
        try:
            self.s3_client.download_file(self.bucket_name, file_key, local_path)
            return True
        except ClientError as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            return False

    def get_file_content(self, file_key: str) -> bytes:
        """
        Get the content of a file as bytes.

        Args:
            file_key: The key (path) of the file in the bucket

        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Error reading file content from S3: {str(e)}")
            raise

    def upload_file(self, file_name: str, bucket: str, key: str) -> bool:
        """
        Upload file to S3.

        Args:
            content: Content to upload
            bucket: Bucket name
            key: Key (path) in the bucket

        Returns:
            Boolean indicating success
        """
        try:
            self.s3_client.upload_file(file_name, bucket, key)

            return True
        except ClientError as e:
            logger.error(f"Error uploading content to S3: {str(e)}")
            return False

    def upload_content(self, content: bytes | str, bucket: str, key: str) -> bool:
        """
        Upload content to S3.

        Args:
            content: Content to upload (bytes or str)
            bucket: Bucket name
            key: Key (path) in the bucket

        Returns:
            Boolean indicating success
        """
        try:
            self.s3_client.put_object(Bucket=bucket, Key=key, Body=content)
            return True
        except ClientError as e:
            logger.error(f"Error uploading content to S3: {str(e)}")
            return False

    def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            file_key: The key (path) of the file in the bucket

        Returns:
            Boolean indicating success
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False

    _COPIED_HEADERS = (
        "ContentType",
        "ContentEncoding",
        "ContentDisposition",
        "ContentLanguage",
        "CacheControl",
        "ServerSideEncryption",
        "SSEKMSKeyId",
        "StorageClass",
    )

    def copy_file(self, source_key: str, destination_key: str) -> bool:
        """Copy an object within the configured bucket, keeping its headers and metadata.

        The managed ``copy`` switches to a multipart copy for large objects, which does
        not carry over the source headers, so they are passed explicitly, including the
        encryption settings and storage class.
        """
        try:
            source = self.s3_client.head_object(Bucket=self.bucket_name, Key=source_key)
            extra_args: Dict[str, Any] = {
                "MetadataDirective": "REPLACE",
                "Metadata": source.get("Metadata", {}),
            }
            for header in self._COPIED_HEADERS:
                if source.get(header) is not None:
                    extra_args[header] = source[header]
            self.s3_client.copy(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source_key},
                Key=destination_key,
                ExtraArgs=extra_args,
            )
            return True
        except ClientError as e:
            logger.error(
                "Error copying S3 object %s to %s: %s",
                source_key,
                destination_key,
                str(e),
            )
            return False

    @staticmethod
    def test_connection(cd: dict) -> dict:
        access_key, secret_key = s3_data_source_keys(cd)
        client = S3Client(
            bucket_name=cd["bucket_name"],
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=cd.get("region"),
        )
        client.list_files(prefix=cd.get("prefix", ""), max_keys=1)
        return {"success": True, "message": "Successfully connected to S3 bucket."}

    def generate_presigned_url(self, operation: str, params: Dict[str, Any], expires_in: int) -> str:
        """
        Generate a presigned URL for an S3 operation.

        Args:
            operation: The S3 operation to generate a presigned URL for
            params: Parameters for the S3 operation
            expires_in: The number of seconds the presigned URL should be valid for

        Returns:
            A presigned URL for the S3 operation
        """
        return self.s3_client.generate_presigned_url(operation, Params=params, ExpiresIn=expires_in)

    def generate_presigned_put_url(
        self,
        file_key: str,
        content_type: Optional[str],
        expires_in: int,
        bucket: Optional[str] = None,
    ) -> str:
        """Generate a presigned PUT URL for direct browser uploads.

        The signed ``Content-Type`` becomes a hard requirement for the PUT request:
        the client MUST send the same value or S3 will return a SignatureDoesNotMatch
        error. Pass ``None`` to leave it unsigned (any content-type accepted).
        """
        params: Dict[str, Any] = {
            "Bucket": bucket or self.bucket_name,
            "Key": file_key,
        }
        if content_type:
            params["ContentType"] = content_type
        return self.s3_client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in)

    def head_object(self, file_key: str) -> Dict[str, Any]:
        """Return basic object metadata or raise ``ClientError`` if missing."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return {
                "key": file_key,
                "size": int(response.get("ContentLength", 0) or 0),
                "etag": (response.get("ETag") or "").strip('"'),
                "content_type": response.get("ContentType"),
                "last_modified": (response["LastModified"].isoformat() if response.get("LastModified") else None),
            }
        except ClientError as e:
            if is_s3_not_found_error(e):
                logger.debug("S3 key does not exist: %s", file_key)
            else:
                logger.error("Error head_object on S3 key %s: %s", file_key, e)
            raise

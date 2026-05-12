from typing import List, Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        """
        Initialize S3 client with credentials and bucket name.
        If credentials are not provided, boto3 will use the default credential chain.
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: Optional[str] = None,
        file_extensions: Optional[List[str]] = None
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
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            if cleaned_prefix:
                params['Prefix'] = cleaned_prefix

            if continuation_token:
                params['ContinuationToken'] = continuation_token

            logger.info(f"Listing files from S3: {params}")

            # Make the API call
            response = self.s3_client.list_objects_v2(**params)

            # Process the results
            files = []
            for obj in response.get('Contents', []):
                file_name = obj['Key']

                # Apply file extension filter if specified
                if file_extensions:
                    if not any(file_name.lower().endswith(ext.lower()) for ext in file_extensions):
                        continue

                files.append({
                    'key': file_name,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'],
                })

            return {
                'files': files,
                'next_token': response.get('NextContinuationToken'),
                'is_truncated': response.get('IsTruncated', False)
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
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )

            return {
                'key': file_key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType'),
                'metadata': response.get('Metadata', {}),
                'etag': response['ETag']
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
            self.s3_client.download_file(
                self.bucket_name,
                file_key,
                local_path
            )
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
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return response['Body'].read()
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
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content
            )
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
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False

    @staticmethod
    def test_connection(cd: dict) -> dict:
        client = S3Client(
            bucket_name=cd["bucket_name"],
            aws_access_key_id=cd.get("access_key"),
            aws_secret_access_key=cd.get("secret_key"),
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
        return self.s3_client.generate_presigned_url(
            "put_object", Params=params, ExpiresIn=expires_in
        )

    def head_object(self, file_key: str) -> Dict[str, Any]:
        """Return basic object metadata or raise ``ClientError`` if missing."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return {
                "key": file_key,
                "size": int(response.get("ContentLength", 0) or 0),
                "etag": (response.get("ETag") or "").strip('"'),
                "content_type": response.get("ContentType"),
                "last_modified": (
                    response["LastModified"].isoformat()
                    if response.get("LastModified")
                    else None
                ),
            }
        except ClientError as e:
            logger.error(f"Error head_object on S3 key {file_key}: {e}")
            raise
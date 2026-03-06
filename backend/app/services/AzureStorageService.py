# AzureStorageService.py
# !pip install azure-storage-blob
###############################################

import os
from typing import Optional, List
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


class AzureStorageService:
    """
    Service wrapper for Azure Blob Storage operations.

    Initialization fallback order:
      1. If connection_string is provided → use it directly.
      2. Else if account_name & account_key are provided → build connection string.
      3. Else → try AZURE_STORAGE_CONNECTION_STRING env variable.

    If container_name is not given, it must be specified at call time.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        container_name: Optional[str] = None,
    ):
        self._container_name = container_name

        # Determine connection string
        if connection_string:
            self._conn_str = connection_string
        elif account_name and account_key:
            self._conn_str = (
                f"DefaultEndpointsProtocol=https;AccountName={account_name};"
                f"AccountKey={account_key};EndpointSuffix=core.windows.net"
            )
        else:
            self._conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

        if not self._conn_str:
            raise ValueError("No Azure Storage credentials provided.")

        # Initialize the service client
        self._service = BlobServiceClient.from_connection_string(self._conn_str)

    # ────────────────────────────────────────────────────────────────
    # Helper to get container
    def _get_container(self, container_name: Optional[str] = None) -> ContainerClient:
        name = container_name or self._container_name
        if not name:
            raise ValueError("No container name provided.")
        self._container_name = name
        return self._service.get_container_client(name)

    # ────────────────────────────────────────────────────────────────
    # 1. Check if container exists
    def bucket_exists(self, container_name: Optional[str] = None) -> bool:
        try:
            container = self._get_container(container_name)
            return container.exists()
        except Exception as e:
            print(f"XX - Error checking container existence: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # 2. Check if file exists
    def file_exists(self, filename: str, prefix: Optional[str] = None, container_name: Optional[str] = None) -> bool:
        try:
            container = self._get_container(container_name)
            blob_name = f"{prefix}/{filename}" if prefix else filename
            blob = container.get_blob_client(blob_name)
            return blob.exists()
        except Exception as e:
            print(f"XX - Error checking file existence: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # 3. Upload file
    def file_upload(
        self,
        local_file_path: str,
        destination_name: str,
        prefix: Optional[str] = None,
        container_name: Optional[str] = None,
    ) -> str:
        try:
            container = self._get_container(container_name)
            blob_name = f"{prefix}/{destination_name}" if prefix else destination_name
            with open(local_file_path, "rb") as f:
                container.upload_blob(name=blob_name, data=f, overwrite=True)

            url = f"{container.url}/{blob_name}"
            print(f"OK - Uploaded {local_file_path} → {url}")
            return url
        except Exception as e:
            print(f"XX - Upload failed: {e}")
            raise

    def file_upload_content(
        self,
        local_file_content: bytes,
        local_file_name: str,
        destination_name: str,
        prefix: Optional[str] = None,
        container_name: Optional[str] = None,
    ) -> str:
        try:
            container = self._get_container(container_name)
            blob_name = f"{prefix}/{destination_name}" if prefix else destination_name
            container.upload_blob(name=blob_name, data=local_file_content, overwrite=True)

            url = f"{container.url}/{blob_name}"
            print(f"OK - Uploaded {local_file_name} → {url}")
            return url
        except Exception as e:
            print(f"XX - Upload failed: {e}")
            raise

    # ────────────────────────────────────────────────────────────────
    # 4. Delete file
    def file_delete(self, filename: str, prefix: Optional[str] = None, container_name: Optional[str] = None) -> bool:
        try:
            container = self._get_container(container_name)
            blob_name = f"{prefix}/{filename}" if prefix else filename
            container.delete_blob(blob_name)
            print(f"OK - Deleted {container.url}/{blob_name}")
            return True
        except Exception as e:
            print(f"XX - Delete failed: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # 5. Move file (copy + delete)
    def file_move(
        self,
        source_name: str,
        destination_name: str,
        source_prefix: Optional[str] = None,
        destination_prefix: Optional[str] = None,
        container_name: Optional[str] = None,
    ) -> str:
        container = self._get_container(container_name)

        src_blob_name = f"{source_prefix}/{source_name}" if source_prefix else source_name
        dst_blob_name = f"{destination_prefix}/{destination_name}" if destination_prefix else destination_name

        src_blob = container.get_blob_client(src_blob_name)

        if not src_blob.exists():
            raise FileNotFoundError(f"Source blob {src_blob_name} does not exist.")

        dst_blob = container.get_blob_client(dst_blob_name)

        dst_blob.start_copy_from_url(src_blob.url)  # copy
        container.delete_blob(src_blob_name)        # delete original

        print(f"OK - Moved {src_blob.url} → {dst_blob.url}")
        return dst_blob.url

    # ────────────────────────────────────────────────────────────────
    # 6. List files
    def file_list(self, prefix: Optional[str] = None, container_name: Optional[str] = None) -> List[str]:
        try:
            container = self._get_container(container_name)
            files = [blob.name for blob in container.list_blobs(name_starts_with=prefix)]
            print(f"OK - Found {len(files)} file(s) in {container.container_name} with prefix='{prefix or ''}'")
            return files
        except Exception as e:
            print(f"XX - Error listing files: {e}")
            return []

#############################################
## Usage
#############################################

# service = AzureStorageService(
#     connection_string="DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=yyy;EndpointSuffix=core.windows.net",
#     container_name="my-audio-bucket"
# )

# service.file_upload(
#     local_file_path="./audio/test.wav",
#     destination_name="uploads/test.wav"
# )

# files = service.file_list(prefix="uploads/")
# print(files)

# print(service.file_exists("test.wav", prefix="uploads"))

# service.file_delete("test.wav", prefix="uploads")

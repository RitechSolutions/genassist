import os
import json
from google.cloud import storage
from google.oauth2 import service_account
from typing import Optional, List


class GoogleStorageService:
    """
    Service wrapper for Google Cloud Storage operations.

    Initialization fallback order:
      1. If config_json (string) is provided → load credentials from string.
      2. Else if config_json_file (path) is provided → load credentials from file.
      3. Else → load credentials from GOOGLE_APPLICATION_CREDENTIALS env var.

    If storage_bucket is not given, it can be set later or inferred dynamically.
    """

    def __init__(
        self,
        config_json: Optional[str] = None,
        config_json_file: Optional[str] = None,
        storage_bucket: Optional[str] = None,
    ):
        self._bucket_name = storage_bucket
        self._client = None

        # --- Load credentials ---
        credentials = None
        project_id = None

        if config_json:
            info = json.loads(config_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            project_id = info.get("project_id")
        elif config_json_file:
            credentials = service_account.Credentials.from_service_account_file(config_json_file)
            with open(config_json_file, "r") as f:
                project_id = json.load(f).get("project_id")
        else:
            # default credentials from GOOGLE_APPLICATION_CREDENTIALS or environment
            credentials = None
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

        # Initialize the storage client
        self._client = storage.Client(credentials=credentials, project=project_id)

    # ────────────────────────────────────────────────────────────────
    # Helper to get bucket (lazy initialization)
    def _get_bucket(self, bucket_name: Optional[str] = None):
        name = bucket_name or self._bucket_name
        if not name:
            raise ValueError("No storage bucket specified. Provide one during init or call.")
        bucket = self._client.bucket(name)
        self._bucket_name = name  # remember for reuse
        return bucket

    # ────────────────────────────────────────────────────────────────
    # 1. Check if bucket exists
    def bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        try:
            name = bucket_name or self._bucket_name
            if not name:
                raise ValueError("Bucket name not specified.")
            bucket = self._client.lookup_bucket(name)
            return bucket is not None
        except Exception as e:
            print(f"XX -  Error checking bucket existence: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # 2. Check if file exists
    def file_exists(self, filename: str, prefix: Optional[str] = None, bucket_name: Optional[str] = None) -> bool:
        try:
            bucket = self._get_bucket(bucket_name)
            blob_name = f"{prefix}/{filename}" if prefix else filename
            return bucket.blob(blob_name).exists()
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
        bucket_name: Optional[str] = None,
    ) -> str:
        try:
            bucket = self._get_bucket(bucket_name)
            blob_name = f"{prefix}/{destination_name}" if prefix else destination_name
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_file_path)
            print(f"OK - Uploaded {local_file_path} → gs://{bucket.name}/{blob_name}")
            return f"gs://{bucket.name}/{blob_name}"
        except Exception as e:
            print(f"XX - Upload failed: {e} LocalPath: {local_file_path} Bucker: {bucket_name}")
            raise
    
    def file_upload_content(
        self,
        local_file_content: bytes,
        local_file_name: str,
        destination_name: str,
        prefix: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> str:
        try:
            bucket = self._get_bucket(bucket_name)
            blob_name = f"{prefix}/{destination_name}" if prefix else destination_name
            blob = bucket.blob(blob_name)
            blob.upload_from_string(local_file_content)
            print(f"OK - Uploaded {local_file_name} → gs://{bucket.name}/{blob_name}")
            return f"gs://{bucket.name}/{blob_name}"
        except Exception as e:
            print(f"XX - Upload failed: {e}")
            raise

    # ────────────────────────────────────────────────────────────────
    # 4. Delete file
    def file_delete(self, filename: str, prefix: Optional[str] = None, bucket_name: Optional[str] = None) -> bool:
        try:
            bucket = self._get_bucket(bucket_name)
            blob_name = f"{prefix}/{filename}" if prefix else filename
            blob = bucket.blob(blob_name)
            blob.delete()
            print(f"OK - Deleted gs://{bucket.name}/{blob_name}")
            return True
        except Exception as e:
            print(f"XX - Delete failed: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    # 5. Move file
    def file_move(
        self,
        source_name: str,
        destination_name: str,
        source_prefix: Optional[str] = None,
        destination_prefix: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> str:
        """
        Moves (renames) a file by copying it to a new name/prefix and deleting the original.
        """
        bucket = self._get_bucket(bucket_name)

        src_blob_name = f"{source_prefix}/{source_name}" if source_prefix else source_name
        dst_blob_name = f"{destination_prefix}/{destination_name}" if destination_prefix else destination_name

        src_blob = bucket.blob(src_blob_name)
        if not src_blob.exists():
            raise FileNotFoundError(f"Source blob {src_blob_name} does not exist.")

        # Copy the blob to the new destination
        new_blob = bucket.copy_blob(src_blob, bucket, dst_blob_name)

        # Delete the old blob
        src_blob.delete()

        print(f"OK - Moved gs://{bucket.name}/{src_blob_name} -> gs://{bucket.name}/{dst_blob_name}")
        return f"gs://{bucket.name}/{dst_blob_name}"

    # ────────────────────────────────────────────────────────────────
    # 6. List files
    def file_list(self, prefix: Optional[str] = None, bucket_name: Optional[str] = None) -> List[str]:
        try:
            bucket = self._get_bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            file_list = [b.name for b in blobs]
            print(f"OK -  Found {len(file_list)} file(s) in {bucket.name} with prefix='{prefix or ''}'")
            return file_list
        except Exception as e:
            print(f"XX - Error listing files: {e}")
            return []


##############################################
# usage
##############################################
# #Initialize Service
# service = GoogleStorageService(
#     config_json=json.dumps({
#         "type": "service_account",
#         "project_id": "genassist-stt",
#         ....
#         "client_email": "stt-service@genassist-stt.iam.gserviceaccount.com",
#         "token_uri": "https://oauth2.googleapis.com/token"
#     }),
#     storage_bucket="genassist-stt-audio-bucket"
# )

# # Upload File
# service.file_upload(
#     local_file_path="./audio/test.wav",
#     destination_name="uploads/test.wav"
# )

# # List Files
# files = service.file_list(prefix="uploads/")
# print(files)

# # Check if file exists
# exists = service.file_exists("uploads/test.wav")
# print("Exists:", exists)

# # Delete File
# service.file_delete("uploads/test.wav")

# # Move file
# service.file_move(
#     source_name="test.wav",
#     source_prefix="uploads",
#     destination_prefix="processed"
# )

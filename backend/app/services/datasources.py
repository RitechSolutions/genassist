import base64
import logging
import os
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from injector import inject

from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.db.models import DataSourceModel
from app.repositories.datasources import DataSourcesRepository
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate

logger = logging.getLogger(__name__)


@inject
class DataSourceService:
    encrypted_fields = [
        "database_password",
        "ssh_tunnel_private_key",
        "secret_key",
        "access_key",
        "access_token",
        "refresh_token",
        "password",
        "api_token",
    ]

    def __init__(self, repository: DataSourcesRepository):
        self.repository = repository

    async def create(self, datasource: DataSourceCreate):
        datasource.connection_data = await self.extract_private_key(
            datasource.connection_data
        )
        datasource.connection_data = await self.encrypt_connection_data_fields(
            datasource.connection_data
        )

        db_datasource = await self.repository.create(datasource)
        return db_datasource

    async def get_by_id(
        self, datasource_id: UUID, decrypt_sensitive: Optional[bool] = False
    ) -> Optional[DataSourceModel]:
        db_datasource = await self.repository.get_by_id(datasource_id)
        if decrypt_sensitive:
            db_datasource.connection_data = await self.decrypt_connection_data_fields(
                db_datasource.connection_data
            )

        return db_datasource

    async def get_all(self):
        db_datasources = await self.repository.get_all()
        return db_datasources

    async def update(self, datasource_id: UUID, datasource_update: DataSourceUpdate):
        update_data = datasource_update.model_dump(exclude_unset=True)

        if "connection_data" in update_data:
            update_data["connection_data"] = await self.extract_private_key(
                update_data["connection_data"]
            )

        # get  current datasource from DB
        db_datasource = await self.repository.get_by_id(datasource_id)
        if not db_datasource:
            raise ValueError(f"Datasource with ID {datasource_id} not found")

        # Ensure connection_data exists in both
        update_conn_data = update_data.get("connection_data", {})
        existing_conn_data = db_datasource.connection_data or {}

        for field_name in self.encrypted_fields:
            if field_name in update_conn_data:
                if (
                    update_conn_data[field_name] == ""
                    or update_conn_data[field_name] == None
                ):
                    del update_conn_data[field_name]
                elif (
                    field_name not in existing_conn_data
                    or update_conn_data[field_name] != existing_conn_data[field_name]
                ):
                    # encrypt field in connection_data if is different or doesn't exist in DB
                    update_conn_data[field_name] = encrypt_key(
                        update_conn_data[field_name]
                    )

        db_datasource = await self.repository.update(datasource_id, update_data)
        return db_datasource

    async def delete(self, datasource_id: UUID):
        await self.repository.delete(datasource_id)

    async def get_active(self):
        db_datasources = await self.repository.get_active()
        return db_datasources

    async def get_by_type(
        self, source_type: str, decrypt_sensitive: Optional[bool] = False
    ):
        db_datasources = await self.repository.get_by_type(source_type)
        if decrypt_sensitive:
            for datasource in db_datasources:
                if datasource.connection_data:
                    datasource.connection_data = (
                        await self.decrypt_connection_data_fields(
                            datasource.connection_data, datasource.id
                        )
                    )
        return db_datasources

    async def encrypt_connection_data_fields(
        self, connection_data: Dict[str, Any], datasource_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        for field_name in self.encrypted_fields:
            if field_name in connection_data and connection_data[field_name]:
                try:
                    connection_data[field_name] = encrypt_key(
                        connection_data[field_name]
                    )
                except Exception as e:
                    logger.error(
                        f"Error decrypting datasource field '{field_name}' for datasource ID '{datasource_id}': {e}"
                    )
        return connection_data

    async def decrypt_connection_data_fields(
        self, connection_data: Dict[str, Any], datasource_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        for field_name in self.encrypted_fields:
            if field_name in connection_data and connection_data[field_name]:
                try:
                    connection_data[field_name] = decrypt_key(
                        connection_data[field_name]
                    )
                except Exception as e:
                    logger.error(
                        f"Error decrypting datasource field '{field_name}' for datasource ID '{datasource_id}': {e}"
                    )
        return connection_data

    async def test_connection(
        self,
        source_type: Optional[str],
        connection_data: Optional[Dict[str, Any]],
        datasource_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        cd = dict(connection_data or {})

        if datasource_id:
            stored = await self.get_by_id(datasource_id, decrypt_sensitive=True)
            base = dict(stored.connection_data or {})
            for k, v in cd.items():
                if v is not None and v != "":
                    base[k] = v
            cd = base

        if "private_key_file" in cd:
            cd = await self.extract_private_key(cd)

        try:
            if source_type == "S3":
                from app.core.utils.s3_utils import S3Client

                client = S3Client(
                    bucket_name=cd["bucket_name"],
                    aws_access_key_id=cd.get("access_key"),
                    aws_secret_access_key=cd.get("secret_key"),
                    region_name=cd.get("region"),
                )
                client.list_files(prefix=cd.get("prefix", ""), max_keys=1)
                return {
                    "success": True,
                    "message": "Successfully connected to S3 bucket.",
                }

            elif source_type == "Database":
                from app.modules.integration.database.database_manager import (
                    DatabaseManager,
                )

                db_cd = dict(cd)
                for field in ["database_password", "ssh_tunnel_private_key"]:
                    if db_cd.get(field):
                        db_cd[field] = encrypt_key(db_cd[field])
                manager = DatabaseManager(db_cd)
                await manager.connect()
                await manager.disconnect()
                return {
                    "success": True,
                    "message": "Successfully connected to database.",
                }

            elif source_type == "Snowflake":
                from app.modules.integration.snowflake.snowflake_manager import (
                    SnowflakeManager,
                )

                sf_cd = dict(cd)
                if sf_cd.get("password"):
                    sf_cd["password"] = encrypt_key(sf_cd["password"])
                manager = SnowflakeManager(sf_cd)
                await manager.connect()
                await manager.disconnect()
                return {
                    "success": True,
                    "message": "Successfully connected to Snowflake.",
                }

            elif source_type == "Zendesk":
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://{cd['subdomain']}.zendesk.com/api/v2/users/me.json",
                        auth=(f"{cd['email']}/token", cd["api_token"]),
                        timeout=10.0,
                    )
                    response.raise_for_status()
                return {
                    "success": True,
                    "message": "Successfully connected to Zendesk.",
                }

            elif source_type == "smb_share_folder":
                from app.services.smb_share_service import SMBShareFSService

                async with SMBShareFSService(
                    smb_host=cd.get("smb_host"),
                    smb_share=cd.get("smb_share"),
                    smb_user=cd.get("smb_user"),
                    smb_pass=cd.get("smb_password"),
                    smb_port=cd.get("smb_port"),
                    use_local_fs=cd.get("use_local_fs", False),
                    local_root=cd.get("local_root"),
                ):
                    pass
                return {
                    "success": True,
                    "message": "Successfully connected to network share.",
                }

            elif source_type == "azure_blob":
                from app.services.AzureStorageService import AzureStorageService

                service = AzureStorageService(
                    connection_string=cd["connectionstring"],
                    container_name=cd.get("container"),
                )
                service.bucket_exists(cd.get("container"))
                return {
                    "success": True,
                    "message": "Successfully connected to Azure Blob Storage.",
                }

            elif source_type == "URL":
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        cd["url"], timeout=10.0, follow_redirects=True
                    )
                    response.raise_for_status()
                return {"success": True, "message": "URL is accessible."}

            else:
                return {
                    "success": False,
                    "message": f"Test connection is not supported for {source_type}.",
                }

        except Exception as e:
            logger.error(f"Test connection failed for {source_type}: {e}")
            return {"success": False, "message": str(e)}

    async def extract_private_key(self, connection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reads content from 'private_key_file', stores it in 'private_key',
        and removes the source file and file path property.
        """
        file_path = connection_data.get("private_key_file")

        if not file_path:
            return connection_data

        try:
            # if file path is a URL, download the file to a temporary file
            if file_path.startswith("http://") or file_path.startswith("https://"):
                from app.dependencies.injector import injector
                from app.services.file_manager import FileManagerService
                file_manager_service = injector.get(FileManagerService)

                # store the file to a temporary folder
                temp_file_path = f"/tmp/{uuid.uuid4()}.p8"
                await file_manager_service.download_file_from_url_to_path(file_path, temp_file_path)
                # set the file path to the temporary file path
                file_path = temp_file_path

            # Read file content
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    content = f.read()

                encrypted_content = encrypt_key(content)
                private_key = base64.b64encode(
                    encrypted_content.encode("utf-8")
                ).decode("utf-8")
                connection_data["private_key"] = private_key

                # Delete file from memory
                os.remove(file_path)
                logger.info(f"Private key extracted and file deleted: {file_path}")
            else:
                logger.warning(
                    f"Private key file path provided but file not found: {file_path}"
                )

        except Exception as e:
            logger.error(f"Error processing private key file {file_path}: {str(e)}")
            raise e

        return connection_data

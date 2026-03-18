import base64
import logging
import os
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
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

        if datasource.connection_status:
            datasource.connection_status = datasource.connection_status.model_dump(mode="json")
        else:
            datasource.connection_status = {"status": "Untested", "last_tested_at": None, "message": None}

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
        update_data = datasource_update.model_dump(exclude_unset=True, mode="json")

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

        if "connection_data" in update_data:
            # Check if any connection field actually changed (after encryption processing)
            connection_data_changed = any(
                update_data["connection_data"].get(k) != existing_conn_data.get(k)
                for k in update_data["connection_data"]
            )

            if connection_data_changed:
                incoming_cs = update_data.get("connection_status")
                stored_cs = db_datasource.connection_status or {}
                stored_last_tested = stored_cs.get("last_tested_at")

                incoming_last_tested = None
                if isinstance(incoming_cs, dict):
                    incoming_last_tested = incoming_cs.get("last_tested_at")
                elif hasattr(incoming_cs, "last_tested_at"):
                    incoming_last_tested = getattr(incoming_cs, "last_tested_at", None)

                # Fresh test = timestamps differ (new test was run in this session)
                fresh_test = bool(incoming_cs) and incoming_last_tested != stored_last_tested

                if fresh_test:
                    update_data["connection_status"] = incoming_cs
                else:
                    update_data["connection_status"] = {"status": "Untested", "last_tested_at": None, "message": None}
            else:
                # connection_data unchanged — preserve provided connection_status (e.g., test result)
                if not update_data.get("connection_status"):
                    update_data.pop("connection_status", None)
        else:
            update_data.pop("connection_status", None)

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
            stored_raw = await self.repository.get_by_id(datasource_id)
            raw_conn = dict((stored_raw.connection_data if stored_raw else None) or {})
            decrypted_conn = await self.decrypt_connection_data_fields(dict(raw_conn))

            base = dict(decrypted_conn)
            for k, v in cd.items():
                if v is None or v == "":
                    continue
                if k in self.encrypted_fields and v == raw_conn.get(k):
                    pass  # unchanged encrypted field — keep stored decrypted value
                else:
                    base[k] = v  # new plaintext value from user
            cd = base

        if "private_key_file" in cd:
            cd = await self.extract_private_key(cd, delete_file=False)

        source_type_lower = (source_type or "").lower()
        try:
            if source_type_lower == "s3":
                from app.core.utils.s3_utils import S3Client
                return S3Client.test_connection(cd)
            elif source_type_lower == "database":
                from app.modules.integration.database.database_manager import (
                    DatabaseManager,
                )
                return await DatabaseManager.test_connection(cd)
            elif source_type_lower == "snowflake":
                from app.modules.integration.snowflake.snowflake_manager import (
                    SnowflakeManager,
                )
                return await SnowflakeManager.test_connection(cd)
            elif source_type_lower == "zendesk":
                from app.modules.integration.zendesk import ZendeskConnector
                return await ZendeskConnector.test_connection(cd)
            elif source_type_lower == "smb_share_folder":
                from app.services.smb_share_service import SMBShareFSService
                return await SMBShareFSService.test_connection(cd)
            elif source_type_lower == "azure_blob":
                from app.services.AzureStorageService import AzureStorageService
                return AzureStorageService.test_connection(cd)
            elif source_type_lower == "url":
                async with httpx.AsyncClient() as client:
                    response = await client.get(cd["url"], timeout=10.0, follow_redirects=True)
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

    async def extract_private_key(self, connection_data: Dict[str, Any], delete_file: bool = True) -> Dict[str, Any]:
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

                if delete_file:
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

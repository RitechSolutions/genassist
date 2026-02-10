import os
import base64
from uuid import UUID
from injector import inject

from app.db.models import DataSourceModel
from app.repositories.datasources import DataSourcesRepository

from app.schemas.datasource import DataSourceCreate, DataSourceUpdate

import logging
from typing import Any, Dict, Optional
from app.core.utils.encryption_utils import decrypt_key, encrypt_key

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
        datasource.connection_data = self.extract_private_key(
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
            update_data["connection_data"] = self.extract_private_key(
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
                    not field_name in existing_conn_data
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

    def extract_private_key(self, connection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reads content from 'private_key_file', stores it in 'private_key',
        and removes the source file and file path property.
        """
        file_path = connection_data.get("private_key_file")

        if not file_path:
            return connection_data

        try:
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

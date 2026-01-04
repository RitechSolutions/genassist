from typing import List, Optional, Dict, Any
from uuid import UUID
from injector import inject
import logging

from app.repositories.app_settings import AppSettingsRepository
from app.schemas.app_settings import (
    AppSettingsCreate,
    AppSettingsUpdate,
    AppSettingsRead,
)
from app.schemas.dynamic_form_schemas import (
    get_schema_for_type,
    get_encrypted_fields_for_type,
    APP_SETTINGS_SCHEMAS_DICT,
)
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey
from app.core.utils.encryption_utils import encrypt_key, decrypt_key

logger = logging.getLogger(__name__)


@inject
class AppSettingsService:
    def __init__(self, repo: AppSettingsRepository):
        self.repo = repo

    async def get_all(self) -> List[AppSettingsRead]:
        rows = await self.repo.get_all()
        return [AppSettingsRead.model_validate(r, from_attributes=True) for r in rows]

    async def get_by_id(self, id: UUID) -> AppSettingsRead:
        row = await self.repo.get_by_id(id)
        if not row:
            raise AppException(
                status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND
            )
        return AppSettingsRead.model_validate(row, from_attributes=True)

    async def get_by_type_and_name(
        self, setting_type: str, name: str
    ) -> Optional[AppSettingsRead]:
        """Get app setting by type and name."""
        row = await self.repo.get_by_type_and_name(setting_type, name)
        if not row:
            return None
        return AppSettingsRead.model_validate(row, from_attributes=True)

    async def get_value_by_type_and_field(
        self, setting_type: str, field_name: str, decrypt: bool = False
    ) -> Optional[str]:
        """Get a specific field value from an app setting by type and field name.

        This is a helper method for backward compatibility with get_by_key usage.
        Returns the first setting of the given type that has the field.
        """
        rows = await self.repo.get_by_type(setting_type)
        if not rows:
            return None

        # Get the first active setting of this type
        active_rows = [r for r in rows if r.is_active == 1]
        if not active_rows:
            return None

        setting = active_rows[0]
        values = setting.values if isinstance(setting.values, dict) else {}

        if field_name not in values:
            return None

        value = values[field_name]

        # Decrypt if needed
        if decrypt and field_name in get_encrypted_fields_for_type(setting_type):
            try:
                value = decrypt_key(value)
            except Exception as e:
                logger.error(
                    f"Error decrypting field '{field_name}' for type '{setting_type}': {e}"
                )

        return value

    async def validate_and_encrypt_values(
        self, setting_type: str, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate values against schema and encrypt sensitive fields."""
        # For "Other" type, no validation needed
        if setting_type == "Other":
            return values

        schema = get_schema_for_type(setting_type)
        if not schema:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"Unknown type: {setting_type}",
            )

        # Validate required fields
        required_fields = [field.name for field in schema.fields if field.required]
        missing_fields = [
            field
            for field in required_fields
            if field not in values or values[field] is None
        ]
        if missing_fields:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"Missing required fields: {', '.join(missing_fields)}",
            )

        # Validate that only schema fields are present
        schema_field_names = {field.name for field in schema.fields}
        extra_fields = set(values.keys()) - schema_field_names
        if extra_fields:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"Unknown fields for type '{setting_type}': {', '.join(extra_fields)}",
            )

        # Encrypt sensitive fields
        encrypted_values = values.copy()
        encrypted_fields = get_encrypted_fields_for_type(setting_type)

        for field_name in encrypted_fields:
            if field_name in encrypted_values and encrypted_values[field_name]:
                try:
                    # Only encrypt if not already encrypted (check if it's a valid encrypted string)
                    value = encrypted_values[field_name]
                    if isinstance(value, str) and not value.startswith(
                        "gAAAAA"
                    ):  # Fernet encrypted strings start with this
                        encrypted_values[field_name] = encrypt_key(value)
                except Exception as e:
                    logger.error(f"Error encrypting field '{field_name}': {e}")
                    raise AppException(
                        status_code=500,
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Failed to encrypt field '{field_name}'",
                    )

        return encrypted_values

    async def create(self, dto: AppSettingsCreate) -> AppSettingsRead:
        # Check if a setting with the same name and type already exists
        existing = await self.repo.get_by_type_and_name(dto.type, dto.name)
        if existing:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"App setting with name '{dto.name}' and type '{dto.type}' already exists",
            )

        # Validate and encrypt values
        encrypted_values = await self.validate_and_encrypt_values(dto.type, dto.values)

        # Create a new DTO with encrypted values
        create_dto = AppSettingsCreate(
            name=dto.name,
            type=dto.type,
            values=encrypted_values,
            description=dto.description,
            is_active=dto.is_active,
        )

        row = await self.repo.create(create_dto)
        return AppSettingsRead.model_validate(row, from_attributes=True)

    async def update(self, id: UUID, dto: AppSettingsUpdate) -> AppSettingsRead:
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(
                status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND
            )

        # If values are being updated, validate and encrypt them
        update_dict = dto.model_dump(exclude_unset=True)

        if "values" in update_dict:
            # Get the type (either from update or existing)
            setting_type = update_dict.get("type", existing.type)
            encrypted_values = await self.validate_and_encrypt_values(
                setting_type, update_dict["values"]
            )
            update_dict["values"] = encrypted_values

        # Create update DTO
        update_dto = AppSettingsUpdate(**update_dict)
        updated = await self.repo.update(id, update_dto)
        return AppSettingsRead.model_validate(updated, from_attributes=True)

    async def delete(self, id: UUID):
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(
                status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND
            )
        await self.repo.delete(id)

    async def get_schemas(self) -> Dict[str, Any]:
        """Get all field schemas for frontend."""
        return APP_SETTINGS_SCHEMAS_DICT

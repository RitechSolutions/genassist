import asyncio
import logging
import os
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional
from uuid import UUID

import pandas as pd
import sqlglot
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi_injector import Injected
from pydantic import BaseModel
from sqlglot import exp

from app.auth.dependencies import auth, permissions
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.project_path import DATA_VOLUME
from app.modules.integration.database.provider_manager import DBProviderManager
from app.modules.integration.database.read_only_sql import (
    SQLGLOT_DIALECTS,
    read_only_sql_blocked_message,
    validate_read_only_sql,
)
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.utils import has_volatile_template_vars
from app.schemas.file import FileBase, FileUploadResponse
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate
from app.services.app_settings import AppSettingsService
from app.services.file_manager import FileManagerService
from app.services.ml_model_manager import get_ml_model_manager
from app.services.ml_models import MLModelsService

logger = logging.getLogger(__name__)

router = APIRouter()

# Directory for storing ML model .pkl files
ML_MODELS_UPLOAD_DIR = str(DATA_VOLUME / "ml_models")
os.makedirs(ML_MODELS_UPLOAD_DIR, exist_ok=True)

# Maximum file size for .pkl files (500MB)
MAX_PKL_FILE_SIZE = 500 * 1024 * 1024


class ProfileDataRequest(BaseModel):
    """Input for profiling an uploaded CSV or a database query result."""

    source_type: Literal["csv", "datasource"] = "csv"
    file_url: Optional[str] = None
    file_id: Optional[UUID] = None
    file_name: Optional[str] = None
    data_source_id: Optional[UUID] = None
    query: Optional[str] = None


_require_data_source_read = permissions(P.DataSource.READ)


@router.post("", response_model=MLModelRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.CREATE))
])
async def create_ml_model(
    ml_model: MLModelCreate,
    service: MLModelsService = Injected(MLModelsService),
):
    """Create a new ML model."""
    return await service.create(ml_model)


@router.get("/{ml_model_id}", response_model=MLModelRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def get_ml_model(
    ml_model_id: UUID,
    service: MLModelsService = Injected(MLModelsService)
):
    """Get a single ML model by ID."""
    return await service.get_by_id(ml_model_id)


@router.get("", response_model=list[MLModelRead], dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def get_all_ml_models(
    service: MLModelsService = Injected(MLModelsService)
):
    """Get all ML models."""
    return await service.get_all()


@router.put("/{ml_model_id}", response_model=MLModelRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.UPDATE))
])
async def update_ml_model(
    ml_model_id: UUID,
    ml_model_update: MLModelUpdate,
    service: MLModelsService = Injected(MLModelsService)
):
    """Update an existing ML model."""
    return await service.update(ml_model_id, ml_model_update)


@router.delete("/{ml_model_id}", status_code=204, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.DELETE))
])
async def delete_ml_model(
    ml_model_id: UUID,
    service: MLModelsService = Injected(MLModelsService)
):
    """Delete an ML model and its associated .pkl file."""
    await service.delete(ml_model_id)

    # Invalidate the model from cache
    model_manager = get_ml_model_manager()
    model_manager.invalidate_model(ml_model_id)

    return None


@router.post("/upload", response_model=FileUploadResponse, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.CREATE))
])
async def upload_pkl_file(
    request: Request,
    file: UploadFile = File(...),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    """
    Upload a .pkl model file.

    - Validates file type (.pkl only)
    - Validates file size (max 500MB)
    - Saves file with unique filename
    - Returns file path and original filename
    """
    try:
        logger.info(f"Received file upload: {file.filename}, content_type: {file.content_type}")

        # file extension
        file_extension = "pkl"

        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # subdir
        sub_folder = "ml_models"

        # initialize the file manager service
        app_settings_config = await app_settings_svc.get_by_type_and_name("FileManagerSettings", "File Manager Settings")
        storage_provider = await file_manager_service.initialize(base_url=str(request.base_url).rstrip('/'), base_path=str(DATA_VOLUME), app_settings = app_settings_config)

        # create file base
        file_base = FileBase(
            name=unique_filename,
            original_filename=file.filename,
            path=sub_folder,
            storage_provider=storage_provider.name,
            storage_path=storage_provider.get_base_path(),
            file_extension=file_extension
        )

        # create file in file manager service
        created_file = await file_manager_service.create_file(file, file_base=file_base, allowed_extensions=["pkl"], max_file_size=MAX_PKL_FILE_SIZE)

        # get file info
        file_url = await file_manager_service.get_file_source_url(created_file.id)
        file_path = None

        if created_file.storage_provider == "local":
            file_path = f"{storage_provider.get_base_path()}/{created_file.path}"
            # file_path = await file_manager_service.get_file_url(created_file)

        file_id = str(created_file.id)

        return FileUploadResponse(
            filename=file.filename,
            file_path=file_path,
            original_filename=file.filename,
            file_id=file_id,
            file_url=file_url,
        )

    except AppException:
        # Re-raise AppException as is
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        ) from e


@router.get("/cache/stats", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def get_cache_stats():
    """Get ML model cache statistics."""
    model_manager = get_ml_model_manager()
    return model_manager.get_cache_stats()


@router.post("/cache/clear", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.UPDATE))
])
async def clear_model_cache():
    """Clear all cached ML models."""
    model_manager = get_ml_model_manager()
    model_manager.clear_cache()
    return {"message": "Model cache cleared successfully"}


@router.post("/cache/invalidate/{ml_model_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.UPDATE))
])
async def invalidate_model_cache(ml_model_id: UUID):
    """Invalidate a specific ML model from cache."""
    model_manager = get_ml_model_manager()
    model_manager.invalidate_model(ml_model_id)
    return {"message": f"Model {ml_model_id} invalidated from cache"}


@router.post("/validate/{ml_model_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ)),
])
async def validate_model_file(
    ml_model_id: UUID,
    service: MLModelsService = Injected(MLModelsService)
):
    """
    Validate a model's PKL file to check if it can be loaded safely.
    This runs validation in a subprocess to prevent segfaults from crashing the API.
    """
    from app.core.utils.model_validator import get_model_info

    # Get model from database
    ml_model = await service.get_by_id(ml_model_id)

    if not ml_model.pkl_file and not ml_model.pkl_file_id:
        raise HTTPException(
            status_code=400,
            detail="Model has no PKL file configured"
        )

    # if ml_model.pkl_file is none and we have a pkl_file_id, get the file from the file manager service
    if not ml_model.pkl_file and ml_model.pkl_file_id:
        # get the file from the file manager service
        from app.dependencies.injector import injector
        from app.services.file_manager import FileManagerService
        file_manager_service = injector.get(FileManagerService)
        file = await file_manager_service.get_file_by_id(ml_model.pkl_file_id)
        if not file:
            raise HTTPException(
                status_code=404,
                detail="PKL file not found"
            )

    # Get model info
    info = get_model_info(ml_model.pkl_file)

    return {
        "model_id": str(ml_model_id),
        "model_name": ml_model.name,
        "validation": {
            "is_valid": info["is_valid"],
            "error": info["error"],
            "file_path": info["file_path"],
            "file_size_bytes": info["file_size"],
            "file_size_mb": round(info["file_size"] / 1024 / 1024, 2)
        },
        "recommendation": (
            "Model is safe to use" if info["is_valid"]
            else "Model validation failed. Please re-save the model with the current library versions."
        )
    }

@router.post("/analyze-csv", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def analyze_csv(
    file_url: str = Body(..., embed=True, description="Path or URL to CSV file"),
    python_code: Optional[str] = Body(None, embed=True, description="Optional Python code to preprocess data before analysis"),
    file_manager_service: FileManagerService = Injected(FileManagerService)
):
    """
    Analyze a CSV file and return a comprehensive report.

    The file_url can be:
    - An absolute path (starting with /)
    - A relative path (will be checked in DATA_VOLUME/train directories)
    - A path within DATA_VOLUME

    If python_code is provided, the data will be preprocessed using the Python code
    before analysis. The code should accept params with 'data' (list of dicts), 'df' (DataFrame),
    and 'fileUrl' (string), and return a result that can be converted to a DataFrame.

    Returns:
        - row_count: Number of rows
        - column_count: Number of columns
        - column_names: List of column names
        - sample_data: First 3 and last 3 records
        - columns_info: Detailed info per column including:
            - name: Column name
            - type: "numeric", "categorical", or "other"
            - dtype: Pandas data type
            - missing_count: Number of missing/null/empty values
            - unique_count: Number of unique values
            - category_count: Number of categories (for non-numeric)
            - min: Minimum value (for numeric)
            - max: Maximum value (for numeric)
    """
    try:
        # Resolve and validate file path using shared utility
        try:
            # check if the file_url includes a valid file id
            if file_url.startswith("http://") or file_url.startswith("https://"):
                dest_path = os.path.join(ML_MODELS_UPLOAD_DIR, f"csv_file_{uuid.uuid4()}.csv")
                await file_manager_service.download_file_from_url_to_path(file_url, dest_path)
                file_path = dest_path
            else:
                file_path = ml_utils.resolve_csv_file_path(file_url)

        except AppException as e:
            # Convert AppException to HTTPException for API endpoint
            if e.error_key == ErrorKey.FILE_NOT_FOUND:
                raise HTTPException(
                    status_code=404,
                    detail=e.error_detail
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=e.error_detail
                )

        logger.info(f"Analyzing CSV file: {file_path}")

        # If python_code is provided, preprocess the data first
        if python_code:
            logger.info("Preprocessing data with Python code before analysis")

            try:
                # Load the CSV file using shared utility
                data, df = ml_utils.load_csv_file(file_url)

                # Execute preprocessing code using shared utility
                # Use raise_on_error=True to raise exceptions for API endpoint
                processed_df, _, _ = await ml_utils.execute_and_process_preprocessing_code(
                    python_code, data, df, str(file_path), raise_on_error=True
                )

                # Save processed data to a temporary CSV file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
                    processed_df.to_csv(tmp_file.name, index=False, encoding='utf-8')
                    temp_file_path = tmp_file.name

                try:
                    # Analyze the processed CSV file
                    analysis = ml_utils.analyze_csv_data(temp_file_path)
                    return analysis
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {temp_file_path}: {str(e)}")

            except AppException as e:
                # Convert AppException to HTTPException for API endpoint
                raise HTTPException(
                    status_code=400,
                    detail=e.error_detail
                )
            except Exception as e:
                logger.error(f"Error executing preprocessing code: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error executing preprocessing code: {str(e)}"
                ) from e

        # If no python_code, analyze the original CSV file directly
        analysis = ml_utils.analyze_csv_data(str(file_path))
        return analysis

    except HTTPException:
        raise
    except AppException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing CSV file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing CSV file: {str(e)}"
        ) from e


def _build_profile_report_html(
    file_path: str,
    display_name: Optional[str] = None,
) -> str:
    """Run ydata-profiling on a CSV file and return the report as an HTML string."""
    path = Path(file_path)
    try:
        df = pd.read_csv(
            path,
            encoding="utf-8",
            on_bad_lines="skip",
            nrows=settings.ML_PROFILE_MAX_ROWS,
        )
    except pd.errors.EmptyDataError as exc:
        raise HTTPException(status_code=400, detail="The file has no rows.") from exc

    return _build_dataframe_profile_report_html(
        df,
        title=(
            f"Data Profile: {Path(display_name).name if display_name else path.name} "
            f"(up to {settings.ML_PROFILE_MAX_ROWS:,} rows)"
        ),
        empty_detail="The file has no rows.",
    )


def _normalize_profile_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert common driver objects into types understood by ydata-profiling."""
    normalized = df.copy()
    for column in normalized.columns:
        non_null = normalized[column].dropna()
        if non_null.empty:
            continue
        if non_null.map(lambda value: isinstance(value, Decimal)).all():
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        elif non_null.map(lambda value: isinstance(value, UUID)).all():
            normalized[column] = normalized[column].map(
                lambda value: str(value) if isinstance(value, UUID) else value
            )
    return normalized


def _build_dataframe_profile_report_html(
    df: pd.DataFrame,
    *,
    title: str,
    empty_detail: str = "The query returned no rows.",
) -> str:
    """Run ydata-profiling on an already-loaded dataframe."""
    if df.empty:
        raise HTTPException(status_code=400, detail=empty_detail)

    from ydata_profiling import ProfileReport

    profile = ProfileReport(_normalize_profile_dataframe(df), title=title)
    return profile.to_html()


def _temporary_csv_path() -> Path:
    """Create a closed temporary CSV path suitable for async downloads."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        return Path(temp_file.name)


async def _resolve_profile_csv(
    request: ProfileDataRequest,
    file_manager_service: FileManagerService,
) -> tuple[Path, Optional[Path]]:
    """Resolve a local CSV or download a non-local one.

    The second tuple item identifies a temporary file owned by this request and
    therefore requiring cleanup.
    """
    file_id = request.file_id
    if file_id is None and request.file_url:
        file_id = await file_manager_service.extract_file_id_from_url(request.file_url)

    if file_id is not None:
        temp_path = _temporary_csv_path()
        try:
            await file_manager_service.download_file_to_path(
                file_id,
                str(temp_path),
            )
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Could not fetch the CSV file from File Manager.",
            ) from exc
        return temp_path, temp_path

    if request.file_url and not request.file_url.startswith(("http://", "https://")):
        return ml_utils.resolve_csv_file_path(request.file_url), None

    if request.file_url and request.file_url.startswith(("http://", "https://")):
        temp_path = _temporary_csv_path()
        try:
            downloaded = await file_manager_service.download_file_from_url_to_path(
                request.file_url,
                str(temp_path),
            )
            if not downloaded:
                raise HTTPException(
                    status_code=400,
                    detail="Could not fetch the CSV file.",
                )
        except HTTPException:
            temp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Could not fetch the CSV file.",
            ) from exc
        return temp_path, temp_path

    raise HTTPException(
        status_code=400,
        detail="A CSV file path, URL, or File Manager ID is required.",
    )


async def _load_query_profile_dataframe(
    request: ProfileDataRequest,
) -> pd.DataFrame:
    """Execute a validated read-only query and return its rows as a dataframe."""
    if request.data_source_id is None or not (request.query or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A data source and query are required for SQL profiling.",
        )

    provider = DBProviderManager.get_instance()
    manager = await provider.get_database_manager(str(request.data_source_id))
    if manager is None:
        raise HTTPException(status_code=404, detail="Data source not found.")

    query = request.query.strip()
    if has_volatile_template_vars(query):
        raise HTTPException(
            status_code=400,
            detail=(
                "Profiling cannot resolve workflow variables. Replace {{...}} "
                "with sample values before profiling."
            ),
        )

    db_type = manager.get_db_type()
    validation = validate_read_only_sql(query, db_type)
    if not validation.is_valid:
        raise HTTPException(
            status_code=400,
            detail=read_only_sql_blocked_message(validation),
        )

    dialect = SQLGLOT_DIALECTS[db_type.strip().lower()]
    statement = sqlglot.parse_one(query, read=dialect)
    existing_limit = statement.args.get("limit")
    row_limit = settings.ML_PROFILE_MAX_ROWS
    existing_count = None
    if isinstance(existing_limit, exp.Limit):
        existing_count = existing_limit.expression
    elif isinstance(existing_limit, exp.Fetch):
        existing_count = existing_limit.args.get("count")
    if isinstance(existing_count, exp.Literal):
        try:
            row_limit = min(row_limit, int(existing_count.this))
        except (TypeError, ValueError):
            pass
    profile_query = statement.limit(row_limit, copy=True).sql(dialect=dialect)

    limited_validation = validate_read_only_sql(profile_query, db_type)
    if not limited_validation.is_valid:
        raise HTTPException(
            status_code=400,
            detail=read_only_sql_blocked_message(limited_validation),
        )

    try:
        rows, error = await asyncio.wait_for(
            manager.execute_read_query(profile_query),
            timeout=settings.ML_EXTRACT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail="The profiling query timed out.",
        ) from exc

    if error:
        logger.error("Data profiling query failed: %s", error)
        raise HTTPException(
            status_code=400,
            detail=(
                "The profiling query failed. Check the selected columns and data source."
            ),
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        raise HTTPException(status_code=400, detail="The query returned no rows.")
    return dataframe


@router.post("/profile-data", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
@router.post("/profile-csv", include_in_schema=False, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def profile_data(
    profile_request: ProfileDataRequest,
    request: Request,
    file_manager_service: FileManagerService = Injected(FileManagerService)
):
    """
    Profile a local/non-local CSV file or the result of a read-only SQL query.
    """
    if profile_request.source_type == "datasource":
        await _require_data_source_read(request)

    temporary_path: Optional[Path] = None
    try:
        if profile_request.source_type == "datasource":
            logger.info(
                "Profiling SQL results for datasource %s",
                profile_request.data_source_id,
            )
            dataframe = await _load_query_profile_dataframe(profile_request)
            html = await asyncio.to_thread(
                _build_dataframe_profile_report_html,
                dataframe,
                title=(
                    "Data Profile: SQL Query Results "
                    f"(up to {settings.ML_PROFILE_MAX_ROWS:,} rows)"
                ),
            )
            download_name = "query_profile.html"
        else:
            file_path, temporary_path = await _resolve_profile_csv(
                profile_request,
                file_manager_service,
            )
            logger.info("Profiling CSV file: %s", file_path)
            display_name = profile_request.file_name
            if display_name is None and temporary_path is not None:
                display_name = "data.csv"
            html = await asyncio.to_thread(
                _build_profile_report_html,
                str(file_path),
                display_name,
            )
            report_stem = Path(display_name or str(file_path)).stem
            download_name = f"{report_stem}_profile.html"

        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    except HTTPException:
        raise
    except AppException as exc:
        status_code = 404 if exc.error_key == ErrorKey.FILE_NOT_FOUND else 400
        raise HTTPException(status_code=status_code, detail=exc.error_detail) from exc
    except Exception as e:
        logger.error("Error profiling data: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error profiling data."
        ) from e
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Failed to delete temporary profile file %s",
                    temporary_path,
                    exc_info=True,
                )

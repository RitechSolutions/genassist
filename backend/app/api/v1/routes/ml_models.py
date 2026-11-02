import asyncio
import logging
import os
import shutil
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
from app.core.utils.training_upload import format_bytes, training_upload_max_bytes
from app.modules.integration.database.provider_manager import DBProviderManager
from app.modules.integration.database.read_only_sql import (
    SQLGLOT_DIALECTS,
    read_only_sql_blocked_message,
    validate_read_only_sql,
)
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.training_file_readers import (
    CSV_SUFFIXES,
    EXCEL_SUFFIXES,
    SUPPORTED_TRAINING_FILE_LABEL,
    SUPPORTED_TRAINING_FILE_SUFFIXES,
    ensure_supported_training_file,
    list_excel_sheets,
    read_training_file_preview,
    training_file_suffix,
)
from app.modules.workflow.engine.utils import has_volatile_template_vars
from app.schemas.file import FileBase, FileUploadResponse
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate, is_in_ml_models_dir
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
    sheet_name: Optional[str] = None


class AnalyzeFileRequest(BaseModel):
    """Input for previewing an uploaded training file of any supported type."""

    file_id: Optional[UUID] = None
    # A File Manager URL (its file id is used) or a path under the data volume.
    file_url: Optional[str] = None
    # The original upload name - its extension picks the reader.
    file_name: Optional[str] = None
    sheet_name: Optional[str] = None


_require_data_source_read = permissions(P.DataSource.READ)
_require_file_manager_read = permissions(P.FileManager.READ)


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
            # A custom file manager folder puts the file outside the ML models folder, where
            # pkl_file is not accepted, so the model gets a copy inside it.
            if not is_in_ml_models_dir(file_path):
                copy_path = os.path.join(ML_MODELS_UPLOAD_DIR, f"{created_file.id}.{file_extension}")
                await asyncio.to_thread(shutil.copyfile, file_path, copy_path)
                file_path = copy_path
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

    # Fetch the uploaded file into the ML models folder when the saved path is not usable
    from app.services.ml_model_manager import local_model_file
    try:
        await local_model_file(ml_model, service)
    except Exception as e:
        logger.warning(f"Could not fetch the model file for {ml_model_id}: {e}")

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
    request: Request,
    file_url: Optional[str] = Body(None, embed=True, description="Path or URL to CSV file"),
    file_id: Optional[UUID] = Body(None, embed=True, description="File Manager ID"),
    file_name: Optional[str] = Body(None, embed=True, description="Original CSV file name"),
    python_code: Optional[str] = Body(None, embed=True, description="Optional Python code to preprocess data before analysis"),
    file_manager_service: FileManagerService = Injected(FileManagerService)
):
    """
    Analyze a CSV file and return a comprehensive report.

    The file_url can be:
    - An absolute path (starting with /)
    - A relative path (will be checked in DATA_VOLUME/train directories)
    - A path within DATA_VOLUME
    - A File Manager URL (resolved by ID, including S3-backed files)

    A file_id can be supplied directly so non-local files do not need to be
    fetched through their HTTP source URL.

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
    temporary_path: Optional[Path] = None
    try:
        file_path, temporary_path = await _resolve_csv_input(
            file_url=file_url,
            file_id=file_id,
            file_name=file_name,
            request=request,
            file_manager_service=file_manager_service,
        )

        logger.info(f"Analyzing CSV file: {file_path}")

        # If python_code is provided, preprocess the data first
        if python_code:
            logger.info("Preprocessing data with Python code before analysis")

            try:
                # Load the CSV file using shared utility
                df = ml_utils.load_csv_file(str(file_path))

                # Execute preprocessing code using shared utility
                # Use raise_on_error=True to raise exceptions for API endpoint
                processed_df, _, _ = await ml_utils.execute_and_process_preprocessing_code(
                    python_code, df, str(file_path), raise_on_error=True
                )

                # Save processed data to a temporary CSV file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
                    processed_df.to_csv(tmp_file.name, index=False, encoding='utf-8')
                    temp_file_path = tmp_file.name
                # Keep the column types the preprocessing code produced, so the
                # analysis reports them the way the next node will see them.
                dtypes_path = ml_utils.write_dtypes_sidecar(temp_file_path, processed_df)

                try:
                    # Analyze the processed CSV file
                    analysis = ml_utils.analyze_csv_data(temp_file_path)
                    return analysis
                finally:
                    # Clean up temporary files
                    for path in (temp_file_path, dtypes_path):
                        try:
                            os.unlink(path)
                        except Exception as e:
                            logger.warning(f"Failed to delete temporary file {path}: {str(e)}")

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
    except AppException as exc:
        if exc.status_code == 403:
            raise
        status_code = 404 if exc.error_key == ErrorKey.FILE_NOT_FOUND else 400
        raise HTTPException(
            status_code=status_code,
            detail=exc.error_detail,
        ) from exc
    except Exception as e:
        logger.error(f"Error analyzing CSV file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing CSV file: {str(e)}"
        ) from e
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Failed to delete temporary CSV preview file",
                    exc_info=True,
                )


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


def _temporary_csv_path(suffix: str = ".csv") -> Path:
    """Create a closed temporary file path (default .csv) suitable for async downloads."""
    with tempfile.NamedTemporaryFile(suffix=suffix or ".csv", delete=False) as temp_file:
        return Path(temp_file.name)


def _training_file_http_error(exc: AppException) -> HTTPException:
    status_code = 404 if exc.error_key in (ErrorKey.FILE_NOT_FOUND, ErrorKey.ML_EXTRACT_FILE_UNAVAILABLE) else 400
    return HTTPException(status_code=status_code, detail=exc.error_detail)


class TrainingDataLimits(BaseModel):
    """Effective Train Data Source limits, shown in the upload UI."""

    max_upload_bytes: int
    max_upload_label: str
    json_max_bytes: int
    max_rows: int
    supported_extensions: list[str]


@router.get("/training-data/limits", response_model=TrainingDataLimits, dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def get_training_data_limits() -> TrainingDataLimits:
    """The largest training file a user can upload, and the extraction limits."""
    max_upload = training_upload_max_bytes()
    return TrainingDataLimits(
        max_upload_bytes=max_upload,
        max_upload_label=format_bytes(max_upload),
        json_max_bytes=min(settings.ML_EXTRACT_JSON_MAX_BYTES, max_upload),
        max_rows=settings.ML_EXTRACT_MAX_ROWS,
        supported_extensions=sorted(SUPPORTED_TRAINING_FILE_SUFFIXES),
    )


@router.post("/analyze-file", dependencies=[
    Depends(auth),
    Depends(permissions(P.MlModel.READ))
])
async def analyze_training_file(
    analyze_request: AnalyzeFileRequest,
    request: Request,
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    """Preview an uploaded training file: CSV, Parquet, Excel or JSON.

    Reads at most ML_PROFILE_MAX_ROWS rows through the same streaming readers
    the Train Data Source node uses, so a large file is never loaded whole.
    Returns the analyze-csv report plus:
        - rows_analyzed / rows_truncated: how much of the file the stats cover
        - row_count: the file's total rows when known (Parquet metadata, or the
          whole file was read), otherwise rows_analyzed
        - sheet_names / sheet_name: for Excel workbooks
    """
    temporary_path: Optional[Path] = None
    try:
        path, temporary_path = await _resolve_csv_input(
            file_url=analyze_request.file_url,
            file_id=analyze_request.file_id,
            file_name=analyze_request.file_name,
            request=request,
            file_manager_service=file_manager_service,
            allowed_suffixes=SUPPORTED_TRAINING_FILE_SUFFIXES,
        )
        suffix = training_file_suffix(path)
        sheet_names = None
        sheet_name = (analyze_request.sheet_name or "").strip() or None
        if suffix in EXCEL_SUFFIXES:
            sheet_names = await asyncio.to_thread(list_excel_sheets, path)
            sheet_name = sheet_name or (sheet_names[0] if sheet_names else None)

        frame, total_rows, truncated = await read_training_file_preview(
            path,
            settings.ML_PROFILE_MAX_ROWS,
            sheet_name=sheet_name,
            json_max_bytes=settings.ML_EXTRACT_JSON_MAX_BYTES,
        )
        analysis = await asyncio.to_thread(ml_utils.analyze_dataframe, frame)
        analysis["rows_analyzed"] = len(frame)
        analysis["rows_truncated"] = truncated
        analysis["row_count"] = total_rows if total_rows is not None else len(frame)
        if sheet_names is not None:
            analysis["sheet_names"] = sheet_names
            analysis["sheet_name"] = sheet_name
        return analysis
    except HTTPException:
        raise
    except AppException as exc:
        raise _training_file_http_error(exc) from exc
    except Exception as exc:
        logger.error("Error analyzing training file: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not analyze the file.") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


async def _resolve_profile_csv(
    profile_request: ProfileDataRequest,
    request: Request,
    file_manager_service: FileManagerService,
) -> tuple[Path, Optional[Path]]:
    """Resolve the CSV input used by data profiling."""
    return await _resolve_csv_input(
        file_url=profile_request.file_url,
        file_id=profile_request.file_id,
        file_name=profile_request.file_name,
        request=request,
        file_manager_service=file_manager_service,
        allowed_suffixes=SUPPORTED_TRAINING_FILE_SUFFIXES,
    )


async def _resolve_csv_input(
    *,
    file_url: Optional[str],
    file_id: Optional[UUID],
    file_name: Optional[str],
    request: Request,
    file_manager_service: FileManagerService,
    allowed_suffixes: frozenset[str] | set[str] = CSV_SUFFIXES,
) -> tuple[Path, Optional[Path]]:
    """Resolve a local file or download a File Manager/non-local file.

    Only files whose extension is in allowed_suffixes are accepted (CSV by
    default). The second tuple item identifies a temporary file owned by this
    request and therefore requiring cleanup. Reading a File Manager record
    also requires File Manager read permission; local paths do not.
    """
    if file_id is None and file_url:
        file_id = await file_manager_service.extract_file_id_from_url(file_url)

    if file_id is not None:
        await _require_file_manager_read(request)
        try:
            stored_file = await file_manager_service.get_file_by_id(file_id)
            if stored_file is None:
                raise LookupError("File Manager record not found")
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not access the selected file. Check that it still "
                    "exists and that the storage configuration is valid."
                ),
            ) from exc
        suffix = _validate_file_manager_file(stored_file, allowed_suffixes)
        # Reject from stored metadata before downloading the object.
        stored_size = getattr(stored_file, "size", None)
        if isinstance(stored_size, int):
            _raise_if_csv_input_too_large(stored_size)

        # Keep the upload's extension so a Parquet/Excel/JSON file is read
        # with the right reader.
        temp_path = _temporary_csv_path(suffix)
        try:
            await file_manager_service.download_file_to_path(
                file_id,
                str(temp_path),
            )
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not access the selected file. Check that it still "
                    "exists and that the storage configuration is valid."
                ),
            ) from exc
        try:
            _enforce_csv_input_byte_limit(temp_path)
        except HTTPException:
            temp_path.unlink(missing_ok=True)
            raise
        return temp_path, temp_path

    candidate_name = file_url or file_name
    candidate_suffix = ""
    if candidate_name:
        candidate_suffix = Path(candidate_name.split("?", maxsplit=1)[0]).suffix.lower()
        if candidate_suffix and candidate_suffix not in allowed_suffixes:
            raise _unsupported_file_type_error(candidate_suffix, allowed_suffixes)

    if file_url and not file_url.startswith(("http://", "https://")):
        # Only files inside the data volume, or the configured storage folder, can be read
        extra_directories = await ml_utils.extra_csv_directories()
        if candidate_suffix in ("", ".csv"):
            local_path = ml_utils.resolve_csv_file_path(
                file_url, allowed_directories=extra_directories
            )
        else:
            local_path = _training_file_path_inside(file_url, extra_directories)
        _enforce_csv_input_byte_limit(local_path)
        return local_path, None

    if file_url and file_url.startswith(("http://", "https://")):
        temp_path = _temporary_csv_path(candidate_suffix or ".csv")
        try:
            downloaded = await file_manager_service.download_file_from_url_to_path(
                file_url,
                str(temp_path),
            )
            if not downloaded:
                raise HTTPException(
                    status_code=400,
                    detail="Could not fetch the file.",
                )
        except HTTPException:
            temp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Could not fetch the file.",
            ) from exc
        try:
            _enforce_csv_input_byte_limit(temp_path)
        except HTTPException:
            temp_path.unlink(missing_ok=True)
            raise
        return temp_path, temp_path

    raise HTTPException(
        status_code=400,
        detail="A file path, URL, or File Manager ID is required.",
    )


def _training_file_path_inside(file_url: str, extra_directories: list[Path]) -> Path:
    """A non-CSV training file path, only from inside the data volume or storage folder."""
    candidates = [file_url] if os.path.isabs(file_url) else [
        DATA_VOLUME / "train" / file_url,
        DATA_VOLUME / file_url,
    ]
    directories = [DATA_VOLUME, *extra_directories]
    for candidate in candidates:
        path = ml_utils._csv_path_inside(candidate, directories)
        if path is not None:
            return path
    raise HTTPException(
        status_code=404,
        detail="The uploaded file is no longer available. Upload it again.",
    )


def _unsupported_file_type_error(
    suffix: str, allowed_suffixes: frozenset[str] | set[str]
) -> HTTPException:
    if set(allowed_suffixes) == set(CSV_SUFFIXES):
        return HTTPException(
            status_code=400,
            detail="Only CSV files can be previewed or profiled.",
        )
    try:
        ensure_supported_training_file(f"file{suffix}")
    except AppException as exc:
        return HTTPException(status_code=400, detail=exc.error_detail)
    return HTTPException(
        status_code=400,
        detail=f"This file type can't be previewed. Use one of: {SUPPORTED_TRAINING_FILE_LABEL}.",
    )


def _enforce_csv_input_byte_limit(file_path: Path) -> None:
    """Apply the Train Data Source byte ceiling to preview/profile inputs."""
    _raise_if_csv_input_too_large(file_path.stat().st_size)


def _raise_if_csv_input_too_large(file_size: int) -> None:
    if file_size <= settings.ML_EXTRACT_MAX_BYTES:
        return

    raise HTTPException(
        status_code=413,
        detail=(
            f"The CSV file is {file_size:,} bytes, which exceeds the "
            f"{settings.ML_EXTRACT_MAX_BYTES:,}-byte training-data limit."
        ),
    )


def _validate_file_manager_file(
    stored_file: object,
    allowed_suffixes: frozenset[str] | set[str] = CSV_SUFFIXES,
) -> str:
    """Validate a File Manager record using server-controlled metadata; return its suffix."""
    extension = str(getattr(stored_file, "file_extension", "") or "").strip()
    if extension:
        suffix = f".{extension.lstrip('.').lower()}"
    else:
        suffix = ""
        for candidate in (
            getattr(stored_file, "name", None),
            getattr(stored_file, "path", None),
        ):
            if candidate:
                suffix = Path(str(candidate)).suffix.lower()
                if suffix:
                    break

    if suffix not in allowed_suffixes:
        raise _unsupported_file_type_error(suffix, allowed_suffixes)
    return suffix


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
                request,
                file_manager_service,
            )
            logger.info("Profiling training file: %s", file_path)
            display_name = profile_request.file_name
            if display_name is None and temporary_path is not None:
                display_name = "data.csv"
            if training_file_suffix(file_path) in CSV_SUFFIXES:
                html = await asyncio.to_thread(
                    _build_profile_report_html,
                    str(file_path),
                    display_name,
                )
            else:
                # Parquet / Excel / JSON: the first rows through the streaming
                # readers, so profiling never loads a large file whole.
                frame, _, _ = await read_training_file_preview(
                    file_path,
                    settings.ML_PROFILE_MAX_ROWS,
                    sheet_name=profile_request.sheet_name,
                    json_max_bytes=settings.ML_EXTRACT_JSON_MAX_BYTES,
                )
                html = await asyncio.to_thread(
                    _build_dataframe_profile_report_html,
                    frame,
                    title=(
                        f"Data Profile: {Path(display_name or str(file_path)).name} "
                        f"(up to {settings.ML_PROFILE_MAX_ROWS:,} rows)"
                    ),
                    empty_detail="The file has no rows.",
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
        if exc.status_code == 403:
            raise
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

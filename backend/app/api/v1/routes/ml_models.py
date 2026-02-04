from uuid import UUID
import os
import uuid
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Body
from fastapi_injector import Injected
from typing import Optional

from app.auth.dependencies import auth, permissions
from app.schemas.ml_model import MLModelRead, MLModelCreate, MLModelUpdate, FileUploadResponse
from app.services.ml_models import MLModelsService
from app.services.ml_model_manager import get_ml_model_manager
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.core.permissions.constants import Permissions as P
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Directory for storing ML model .pkl files
ML_MODELS_UPLOAD_DIR = str(DATA_VOLUME / "ml_models")
os.makedirs(ML_MODELS_UPLOAD_DIR, exist_ok=True)

# Maximum file size for .pkl files (500MB)
MAX_PKL_FILE_SIZE = 500 * 1024 * 1024


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
    file: UploadFile = File(...),
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

        # Validate file extension
        if not file.filename or not file.filename.lower().endswith('.pkl'):
            raise AppException(
                error_key=ErrorKey.INVALID_PKL_FILE
            )

        # Read file content to validate size
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_PKL_FILE_SIZE:
            raise AppException(
                error_key=ErrorKey.PKL_FILE_TOO_LARGE
            )

        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}.pkl"
        file_path = os.path.join(ML_MODELS_UPLOAD_DIR, unique_filename)

        logger.info(f"Saving file to: {file_path}")

        # Save the file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        result = {
            "file_path": file_path,
            "original_filename": file.filename,
        }
        logger.info(f"Upload successful: {result}")
        return result

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
    Depends(permissions(P.MlModel.READ))
])
async def validate_model_file(
    ml_model_id: UUID,
    service: MLModelsService = Injected(MLModelsService)
):
    """
    Validate a model's PKL file to check if it can be loaded safely.
    This runs validation in a subprocess to prevent segfaults from crashing the API.
    """
    from app.core.utils.model_validator import validate_pickle_file_safe, get_model_info
    
    # Get model from database
    ml_model = await service.get_by_id(ml_model_id)
    
    if not ml_model.pkl_file:
        raise HTTPException(
            status_code=400,
            detail="Model has no PKL file configured"
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
    python_code: Optional[str] = Body(None, embed=True, description="Optional Python code to preprocess data before analysis")
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

"""
Utility functions for ML workflow nodes.

This module contains shared functionality used across ML-related nodes.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import csv
import math
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize data to make it JSON-compliant.
    Converts inf, -inf, and nan float values to None or string representations.

    Args:
        obj: Any object to sanitize

    Returns:
        JSON-compliant version of the object
    """
    # Handle numpy types (pandas uses numpy internally)
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            obj = float(obj) if isinstance(obj, np.floating) else int(obj)
        elif isinstance(obj, np.ndarray):
            return sanitize_for_json(obj.tolist())
    except ImportError:
        pass  # numpy not available, skip

    # Handle float types (including numpy floats converted above)
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, pd.DataFrame):
        # Convert DataFrame to dict and sanitize
        return sanitize_for_json(obj.to_dict("records"))
    elif pd.isna(obj):
        return None
    else:
        return obj


def get_sample_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get first 3 and last 3 records from data.

    Args:
        data: List of dictionaries representing the data rows

    Returns:
        List containing first 3 and last 3 records
    """
    if not data:
        return []

    if len(data) <= 6:
        # If 6 or fewer records, return all
        return data

    # Get first 3 and last 3
    first_three = data[:3]
    last_three = data[-3:]

    # Sanitize data to ensure JSON compliance
    result = first_three + last_three
    return sanitize_for_json(result)


async def save_data_to_csv(
    data: List[Dict[str, Any]],
    columns: List[str],
    thread_id: str,
    suffix: Optional[str] = None,
    file_description: str = "CSV",
) -> str:
    """
    Save data to CSV file using thread_id and timestamp as filename.

    Args:
        data: List of dictionaries representing the data rows
        columns: List of column names
        thread_id: Thread ID for filename generation
        suffix: Optional suffix to add to filename (e.g., "_preprocess")
        file_description: Description for logging (e.g., "CSV", "preprocessed CSV")

    Returns:
        Path to the saved CSV file
    """
    try:
        # Create uploads directory within the project's data volume
        uploads_dir = DATA_VOLUME / "train" / thread_id
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Get timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate filename using thread_id and timestamp with optional suffix
        if suffix:
            filename = f"{thread_id}_{timestamp}{suffix}.csv"
        else:
            filename = f"{thread_id}_{timestamp}.csv"
        file_path = uploads_dir / filename

        # Write CSV file
        if data and columns:
            # Use pandas for better CSV handling
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False, encoding="utf-8")
        else:
            # Create empty CSV with headers if no data
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if columns:
                    writer.writerow(columns)

        logger.info(f"Saved {file_description} file: {file_path}")
        return str(file_path)

    except OSError as e:
        logger.error(
            f"OS error saving {file_description} file (permissions/filesystem issue): {str(e)}",
            exc_info=True,
        )
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Failed to save {file_description} file due to filesystem error: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Error saving {file_description} file: {str(e)}", exc_info=True)
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Failed to save {file_description} file: {str(e)}",
        ) from e


def parse_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse CSV file with proper encoding detection and delimiter handling.

    Args:
        file_path: Path to CSV file

    Returns:
        List of dictionaries representing CSV rows
    """
    # Common encodings to try
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

    # Read a sample to detect delimiter
    sample_size = 1024
    delimiter = ","

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                sample = f.read(sample_size)
                f.seek(0)

                # Try to detect delimiter
                try:
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(sample)
                    delimiter = dialect.delimiter
                    logger.debug(
                        f"Detected delimiter: '{delimiter}' for encoding: {encoding}"
                    )
                except Exception:
                    # Fall back to comma if detection fails
                    delimiter = ","
                    logger.debug(
                        f"Using default delimiter ',' for encoding: {encoding}"
                    )

                # Parse the CSV
                reader = csv.DictReader(f, delimiter=delimiter)
                results = []

                for row in reader:
                    # Convert empty strings to None for consistency
                    cleaned_row = {
                        k: (v if v != "" else None) for k, v in row.items()
                    }
                    results.append(cleaned_row)

                logger.info(f"Successfully parsed CSV with encoding: {encoding}")
                return results

        except Exception as e:
            logger.debug(f"Failed to parse CSV with encoding {encoding}: {str(e)}")
            continue

    # If all encodings fail, try with pandas as fallback
    try:
        logger.info("Trying pandas fallback for CSV parsing")
        df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Pandas fallback also failed: {str(e)}")
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Could not parse CSV file: {str(e)}",
        ) from e


def resolve_csv_file_path(
    file_url: str, thread_id: Optional[str] = None
) -> Path:
    """
    Resolve a CSV file path from a file URL/path.

    Args:
        file_url: URL or path to the file (CSV expected)
        thread_id: Optional thread ID for relative path resolution

    Returns:
        Resolved Path object

    Raises:
        AppException: If file is not found or is not a CSV file
    """
    try:
        # Handle both absolute paths and relative paths
        if file_url.startswith("/"):
            # Absolute path
            file_path = Path(file_url)
        elif file_url.startswith("http://") or file_url.startswith("https://"):
            # For HTTP URLs, we'd need to download first
            # For now, raise an error
            raise AppException(
                error_key=ErrorKey.FILE_NOT_FOUND,
                error_detail=f"HTTP/HTTPS URLs are not yet supported: {file_url}",
            )
        else:
            # Try relative to DATA_VOLUME/train/thread_id if thread_id provided
            if thread_id:
                file_path = DATA_VOLUME / "train" / thread_id / file_url
                # If not found, try as absolute path
                if not file_path.exists():
                    file_path = Path(file_url)
            else:
                # Try relative to DATA_VOLUME/train (common location for CSV files)
                file_path = DATA_VOLUME / "train" / file_url
                # If not found, try as absolute path
                if not file_path.exists():
                    file_path = Path(file_url)
                # If still not found, try directly in DATA_VOLUME
                if not file_path.exists():
                    file_path = DATA_VOLUME / file_url

        # Validate file exists
        if not file_path.exists():
            raise AppException(
                error_key=ErrorKey.FILE_NOT_FOUND,
                error_detail=f"File not found: {file_url}",
            )

        # Check if it's a CSV file
        if file_path.suffix.lower() != ".csv":
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Unsupported file type: {file_path.suffix}. Only CSV files are supported.",
            )

        # Check file is readable
        if not os.access(file_path, os.R_OK):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"CSV file is not readable: {file_path}",
            )

        return file_path

    except AppException:
        raise
    except Exception as e:
        logger.error(f"Error resolving file path {file_url}: {str(e)}", exc_info=True)
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Failed to resolve file path: {str(e)}",
        ) from e


def load_csv_file(
    file_url: str, thread_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
    """
    Load data from a CSV file URL/path.

    Args:
        file_url: URL or path to the file (CSV expected)
        thread_id: Optional thread ID for relative path resolution

    Returns:
        Tuple of (data as list of dicts, DataFrame)

    Raises:
        AppException: If file cannot be loaded
    """
    try:
        file_path = resolve_csv_file_path(file_url, thread_id)

        # Load CSV file using pandas
        df = pd.read_csv(file_path, encoding="utf-8")
        data = df.to_dict("records")

        logger.info(f"Loaded {len(data)} rows from {file_path}")

        return data, df

    except AppException:
        raise
    except Exception as e:
        logger.error(f"Error loading file {file_url}: {str(e)}", exc_info=True)
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Failed to load file: {str(e)}",
        ) from e


async def execute_and_process_preprocessing_code(
    python_code: str,
    data: Optional[List[Dict[str, Any]]],
    df: Optional[pd.DataFrame],
    file_url: str,
    raise_on_error: bool = True,
) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict[str, Any]]]:
    """
    Execute preprocessing Python code and return processed DataFrame.

    Args:
        python_code: Python code for data preprocessing
        data: Optional list of dictionaries representing the data rows
        df: Optional pandas DataFrame
        file_url: URL or path to the file
        raise_on_error: If True, raise AppException on errors. If False, return error info.

    Returns:
        Tuple of (processed DataFrame or None, error string or None, full response dict or None)
        If raise_on_error is True and there's an error, raises AppException instead.

    Raises:
        AppException: If code execution fails or result cannot be processed (only if raise_on_error=True)
    """
    from app.modules.workflow.utils import execute_python_code

    # Prepare parameters for Python code execution
    params = {
        "data": data,
        "df": df,
        "fileUrl": file_url,
    }

    # Execute the preprocessing Python code
    response = await execute_python_code(python_code, params, wrap_code=True)

    # Check for errors in response
    errors = response.get("errors", None)
    if errors and errors != "":
        if raise_on_error:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Error executing preprocessing code: {errors}",
            )
        else:
            return None, errors, response

    # Extract result from response
    result = response.get("result")

    # Process the result similar to train_preprocess_node
    if isinstance(result, pd.DataFrame):
        processed_df = result
    elif isinstance(result, dict) and "data" in result:
        # If result is a dict with 'data' key, assume it's already processed
        processed_data = result.get("data", [])
        processed_df = pd.DataFrame(processed_data)
    elif isinstance(result, list):
        # If result is a list, use it directly
        processed_df = pd.DataFrame(result)
    else:
        error_msg = f"Preprocessing code must return a DataFrame, list of dicts, or dict with 'data' key. Got: {type(result).__name__}"
        if raise_on_error:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=error_msg,
            )
        else:
            return None, error_msg, response

    return processed_df, None, response


def analyze_csv_data(file_path: str) -> Dict[str, Any]:
    """
    Analyze CSV file and return comprehensive report.

    Args:
        file_path: Path to CSV file

    Returns:
        Dictionary with analysis report including:
        - row_count: Number of rows
        - column_count: Number of columns
        - column_names: List of column names
        - sample_data: First 3 and last 3 records
        - columns_info: Detailed info per column
    """
    try:
        # Load CSV using pandas for better analysis
        df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")

        # Convert to list of dicts for sample data
        data = df.to_dict("records")

        # Get basic info
        row_count = len(df)
        column_names = list(df.columns)
        column_count = len(column_names)

        # Get sample data (first 3 and last 3)
        sample_data = get_sample_data(data)

        # Analyze each column
        columns_info = []
        for col in column_names:
            col_info = {
                "name": col,
                "dtype": str(df[col].dtype),
                "missing_count": int(df[col].isna().sum() + (df[col] == "").sum()),
            }

            # Determine if numeric
            is_numeric = pd.api.types.is_numeric_dtype(df[col])

            if is_numeric:
                # Numeric column stats
                col_info["type"] = "numeric"
                numeric_values = pd.to_numeric(df[col], errors="coerce")
                col_info["min"] = float(numeric_values.min()) if not numeric_values.isna().all() else None
                col_info["max"] = float(numeric_values.max()) if not numeric_values.isna().all() else None
                col_info["unique_count"] = int(df[col].nunique())
            else:
                # Non-numeric column stats
                col_info["type"] = "categorical" if df[col].dtype == "object" else "other"
                col_info["unique_count"] = int(df[col].nunique())
                col_info["category_count"] = int(df[col].nunique())

            # Sanitize the column info
            col_info = sanitize_for_json(col_info)
            columns_info.append(col_info)

        response = {
            "row_count": row_count,
            "column_count": column_count,
            "column_names": column_names,
            "sample_data": sample_data,
            "columns_info": columns_info,
        }
        return sanitize_for_json(response)

    except Exception as e:
        logger.error(f"Error analyzing CSV file: {str(e)}", exc_info=True)
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Failed to analyze CSV file: {str(e)}",
        ) from e

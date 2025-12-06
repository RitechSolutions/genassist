"""
Train Preprocess node implementation using the BaseNode class.

This node performs data preprocessing using Python code on training data.
"""

from typing import Dict, Any
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)


class TrainPreprocessNode(BaseNode):
    """
    Train Preprocess node that performs data preprocessing using Python code.

    Supports:
    - Python code execution for data preprocessing
    - Optional file URL to load data from previous nodes
    - Pandas DataFrame operations
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a train preprocess node.

        Args:
            config: The resolved configuration for the node containing:
                - pythonCode: Python code for data preprocessing (required)
                - fileUrl: Optional URL/path to the file for preprocessing

        Returns:
            Dictionary with preprocessing results and metadata
        """
        try:
            # Extract configuration
            python_code = config.get("pythonCode", "")
            file_url = config.get("fileUrl")

            # Validate pythonCode is provided
            if not python_code:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="pythonCode is required for train preprocess node",
                )

            logger.info("Processing train preprocess node")

            # Load data from file if fileUrl is provided
            data = None
            df = None
            if file_url:
                data, df = ml_utils.load_csv_file(file_url, self.state.thread_id)
                logger.info(
                    f"Loaded data from file: {file_url} ({len(df) if df is not None else 0} rows)"
                )

            # Execute the preprocessing Python code
            self.set_node_input(python_code)

            try:
                # Execute and process preprocessing code using shared utility
                # Use raise_on_error=False to handle errors in the node's expected format
                processed_df, errors, response = await ml_utils.execute_and_process_preprocessing_code(
                    python_code, data, df, file_url or "", raise_on_error=False
                )

                # Check for errors and return in expected format
                if errors:
                    return {
                        "success": False,
                        "errors": errors,
                        "result": response,
                    }

                # Convert DataFrame to dict format for saving
                processed_data = processed_df.to_dict("records")
                columns = list(processed_df.columns)
                row_count = len(processed_df)

                logger.info(
                    f"Preprocessing completed: {row_count} rows, {len(columns)} columns"
                )

                # Save processed data to CSV using thread_id and timestamp with _preprocess suffix
                csv_file_path = await ml_utils.save_data_to_csv(
                    processed_data,
                    columns,
                    self.state.thread_id,
                    suffix="_preprocess",
                    file_description="preprocessed CSV",
                )

                # Get first 3 and last 3 records for response
                sample_data = ml_utils.get_sample_data(processed_data)

                return {
                    "success": True,
                    "data": sample_data,
                    "data_path": csv_file_path,
                    "metadata": {
                        "rowCount": row_count,
                        "columns": columns,
                    },
                }

            except AppException:
                raise
            except Exception as e:
                logger.error(
                    f"Error executing preprocessing code: {str(e)}", exc_info=True
                )
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Preprocessing code execution failed: {str(e)}",
                ) from e

        except AppException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in train preprocess node: {str(e)}", exc_info=True
            )
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Train preprocess processing failed: {str(e)}",
            ) from e

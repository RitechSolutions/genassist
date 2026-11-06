"""
Train Preprocess node implementation using the BaseNode class.

This node performs data preprocessing using Python code on training data.
"""

from typing import Dict, Any, Optional
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)

# What a File URL like {{source.data_path}} resolves to when the upstream node
# has no such output (none connected, several connected, or not run yet)
# A blank File URL is not one of these: code may load its own data
_UNRESOLVED_FILE_URLS = {"null", "none", "undefined"}


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

            # Check the input before reading, so a missing or extra source is
            # named instead of surfacing as "File not found: null"
            missing_input = self._missing_input_reason(file_url)
            if missing_input:
                return node_failure(missing_input, output={"success": False, "errors": missing_input})

            # Load data from file if fileUrl is provided
            df = None
            if file_url:
                df = ml_utils.load_csv_file(file_url, self.state.thread_id, await ml_utils.extra_csv_directories())
                logger.info(
                    f"Loaded data from file: {file_url} ({len(df) if df is not None else 0} rows)"
                )

            # Execute the preprocessing Python code
            self.set_node_input(python_code)

            try:
                # Execute and process preprocessing code using shared utility
                # Use raise_on_error=False to handle errors in the node's expected format
                processed_df, errors, response = await ml_utils.execute_and_process_preprocessing_code(
                    python_code, df, file_url or "", raise_on_error=False
                )

                # The run failed: fail the node with the short message (the
                # full traceback is only in the server log)
                if errors:
                    # Keep what the code printed: users debug with print()
                    output = {"success": False, "errors": errors, "output": (response or {}).get("output", "")}
                    return node_failure(errors, output=output)

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
                    # Keep the column types the preprocessing code produced
                    # (e.g. a Change Column Data Type step) for the next node.
                    dtypes={str(c): str(t) for c, t in processed_df.dtypes.items()},
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

    def _missing_input_reason(self, file_url: Optional[str]) -> Optional[str]:
        """Why there is no file to preprocess, or None when the File URL names one."""
        value = str(file_url or "").strip()
        if not value or (value.lower() not in _UNRESOLVED_FILE_URLS and "{{" not in value):
            return None
        target_edges = self.get_state().target_edges.get(self.node_id, [])
        sources = [
            edge["source"]
            for edge in target_edges
            if edge.get("targetHandle", "") == "input" and not self._is_unused_entry_source(edge["source"])
        ]
        if not sources and not self.get_state().workflow.get("edges"):
            # Run on its own (Test Node sends just this node): nothing is wired,
            # so the path has to be typed in
            return (
                "No input file: enter the data file path (e.g. source.data_path) "
                "to test this node on its own."
            )
        if not sources:
            return (
                "No data source is connected to this node. Connect a Train Data Source "
                "(or another node that outputs a data file) to its input."
            )
        if len(sources) > 1:
            names = ", ".join(self._node_name(source) for source in sources)
            return (
                f"{len(sources)} nodes are connected to this node's input ({names}). "
                "Connect only the one data source to preprocess."
            )
        return (
            f"{self._node_name(sources[0])} has no data file for this node yet. "
            "Run it first, or check that it outputs a data file (data_path)."
        )

    def _node_name(self, node_id: str) -> str:
        try:
            node_config, _ = self.get_node_config(node_id)
        except StopIteration:
            return node_id
        data = node_config.get("data") or {}
        return str(data.get("name") or data.get("label") or node_id)

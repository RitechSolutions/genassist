"""
Train Data Source node implementation using the BaseNode class.

This node fetches training data from databases or CSV files for ML model training.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, TypeVar
from uuid import UUID

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.integration.database.provider_manager import DBProviderManager
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)

NumericLimit = TypeVar("NumericLimit", int, float)


@dataclass(frozen=True)
class ExtractionLimits:
    """Effective limits for one Train Data Source execution."""

    max_rows: int
    max_bytes: int
    query_timeout_seconds: float


class TrainDataSourceNode(BaseNode):
    """
    Train Data Source node that fetches training data from databases or CSV files.

    Supports:
    - Database queries with variable substitution
    - CSV file parsing with encoding detection
    - Multiple database types (TimeDB, Snowflake, PostgreSQL, MySQL, TimescaleDB)
    - Snowflake-specific query execution via SnowflakeManager
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a train data source node.

        Args:
            config: The resolved configuration for the node containing:
                - name: Node name
                - sourceType: "datasource" or "csv"
                - dataSourceId: UUID of datasource (for database mode)
                - query: SQL query string (for database mode)
                - csvFileName: Name of CSV file (for CSV mode)
                - csvFilePath: Server path to CSV file (for CSV mode)

        Returns:
            Dictionary with training data and metadata
        """
        try:
            # Extract configuration
            name = config.get("name", "Training Data")
            source_type = config.get("sourceType")

            if not source_type:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="sourceType is required (must be 'datasource' or 'csv')",
                )

            if source_type not in ["datasource", "csv"]:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="sourceType must be 'datasource' or 'csv'",
                )

            limits = self._resolve_extraction_limits(config)

            logger.info(
                "Processing train data source node %s (type=%s, max_rows=%s, "
                "max_bytes=%s, timeout=%ss)",
                name,
                source_type,
                limits.max_rows,
                limits.max_bytes,
                self._format_number(limits.query_timeout_seconds),
            )

            if source_type == "datasource":
                return await self._process_database_source(config, limits)
            elif source_type == "csv":
                return await self._process_csv_source(config, limits)
            else:
                # This should never happen due to validation above, but for completeness
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail=f"Unsupported sourceType: {source_type}",
                )

        except AppException:
            # Re-raise AppException as is
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in train data source node: {str(e)}", exc_info=True
            )
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Train data source processing failed: {str(e)}",
            ) from e

    async def _process_database_source(
        self, config: Dict[str, Any], limits: ExtractionLimits
    ) -> Dict[str, Any]:
        """
        Process database data source.

        Args:
            config: Node configuration

        Returns:
            Dictionary with database query results and metadata
        """
        data_source_id = config.get("dataSourceId")
        query = config.get("query", "")

        if not data_source_id:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="dataSourceId is required for database source type",
            )

        if not query:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="query is required for database source type",
            )

        # Convert data_source_id to string if it's a UUID
        if isinstance(data_source_id, UUID):
            data_source_id = str(data_source_id)

        logger.info(f"Executing database query for datasource: {data_source_id}")

        try:
            # Get database manager
            db_manager = await self._get_database_manager(data_source_id)
            if not db_manager:
                raise AppException(
                    error_key=ErrorKey.DATASOURCE_NOT_FOUND,
                    error_detail=f"Database connection not available for datasource {data_source_id}",
                )

            # Log database type for debugging (supports TimeDB, Snowflake, PostgreSQL, MySQL, TimescaleDB)
            db_type = getattr(db_manager, "db_type", "unknown")
            logger.debug(f"Using database manager for {db_type} database")

            substituted_query = query
            logger.debug(f"Substituted query: {substituted_query}")

            # Execute query with timeout
            # Note: For Snowflake, this automatically routes to SnowflakeManager.execute_query()
            try:
                results, error_msg = await asyncio.wait_for(
                    db_manager.execute_query(substituted_query),
                    timeout=limits.query_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=(
                        "Database query timed out after "
                        f"{self._format_number(limits.query_timeout_seconds)} seconds"
                    ),
                ) from exc

            if error_msg:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Database query failed: {error_msg}",
                )

            self._enforce_row_limit(results, limits.max_rows, "query")

            # Extract column names from first row
            columns = list(results[0].keys()) if results else []

            if not results:
                logger.warning("Database query returned no results")
            else:
                logger.info(
                    f"Database query successful: {len(results)} rows, {len(columns)} columns"
                )

            # Save all results to CSV using thread_id and timestamp
            csv_file_path = await ml_utils.save_data_to_csv(
                results, columns, self.state.thread_id
            )

            # Get first 3 and last 3 records for response
            sample_data = ml_utils.get_sample_data(results)

            return {
                "success": True,
                "data": sample_data,
                "data_path": csv_file_path,
                "metadata": {
                    "rowCount": len(results),
                    "columns": columns,
                },
            }

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error processing database source: {str(e)}", exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Database source processing failed: {str(e)}",
            ) from e

    async def _process_csv_source(
        self, config: Dict[str, Any], limits: ExtractionLimits
    ) -> Dict[str, Any]:
        """
        Process CSV data source.

        Args:
            config: Node configuration

        Returns:
            Dictionary with CSV data and metadata
        """
        csv_file_path = config.get("csvFilePath")
        csv_file_id = config.get("csvFileId")

        if not csv_file_path and not csv_file_id:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="csvFilePath is required for CSV source type",
            )

        logger.info(f"Processing CSV file: {csv_file_path or csv_file_id}")

        try:
            # Prefer re-downloading by ID over trusting a stored csvFilePath.
            # csvFilePath is an absolute path captured wherever the file was
            # originally uploaded from (e.g. DATA_VOLUME on the API server at
            # upload time) - it can point somewhere that doesn't exist in
            # whatever process/container actually executes this node (a
            # scheduled pipeline run, a different host, etc.), while the file
            # manager download always resolves correctly relative to this
            # process's own DATA_VOLUME. Only fall back to the raw
            # csvFilePath when there's no ID to re-download by.
            if csv_file_id:
                from app.dependencies.injector import injector
                from app.services.file_manager import FileManagerService

                file_manager_service = injector.get(FileManagerService)
                dest_file_path = f"{DATA_VOLUME}/train/{csv_file_id}.csv"

                logger.info(f"Downloading CSV file to: {dest_file_path}")

                # download the file to the destination path
                await file_manager_service.download_file_to_path(
                    csv_file_id, dest_file_path
                )

                # set the csv file path to the destination path
                csv_file_path = dest_file_path

            # Validate file exists and is accessible
            csv_path = Path(csv_file_path)
            if not csv_path.exists():
                raise AppException(
                    error_key=ErrorKey.FILE_NOT_FOUND,
                    error_detail=f"CSV file not found: {csv_file_path}",
                )

            if not os.access(csv_file_path, os.R_OK):
                raise AppException(
                    error_key=ErrorKey.FILE_NOT_FOUND,
                    error_detail=f"CSV file not readable: {csv_file_path}",
                )

            self._enforce_csv_byte_limit(csv_path, limits.max_bytes)

            # Parse CSV file
            results = ml_utils.parse_csv_file(csv_file_path)

            self._enforce_row_limit(results, limits.max_rows, "CSV file")

            # Extract column names from first row
            columns = list(results[0].keys()) if results else []

            logger.info(
                f"CSV parsing successful: {len(results)} rows, {len(columns)} columns"
            )

            # Save parsed data to CSV using thread_id and timestamp
            # This ensures consistent naming regardless of source type
            saved_csv_path = await ml_utils.save_data_to_csv(
                results, columns, self.state.thread_id
            )

            # Get first 3 and last 3 records for response
            sample_data = ml_utils.get_sample_data(results)

            return {
                "success": True,
                "data": sample_data,
                "data_path": saved_csv_path,
                "metadata": {
                    "rowCount": len(results),
                    "columns": columns,
                },
            }

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error processing CSV source: {str(e)}", exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"CSV source processing failed: {str(e)}",
            ) from e

    @classmethod
    def _resolve_extraction_limits(cls, config: Dict[str, Any]) -> ExtractionLimits:
        """Resolve node overrides without allowing platform ceilings to rise."""
        return ExtractionLimits(
            max_rows=cls._resolve_limit(
                config,
                "maxRows",
                settings.ML_EXTRACT_MAX_ROWS,
                int,
            ),
            max_bytes=cls._resolve_limit(
                config,
                "maxBytes",
                settings.ML_EXTRACT_MAX_BYTES,
                int,
            ),
            query_timeout_seconds=cls._resolve_limit(
                config,
                "timeoutSeconds",
                float(settings.ML_EXTRACT_QUERY_TIMEOUT_SECONDS),
                float,
            ),
        )

    @staticmethod
    def _resolve_limit(
        config: Dict[str, Any],
        config_key: str,
        platform_limit: NumericLimit,
        converter: Callable[[Any], NumericLimit],
    ) -> NumericLimit:
        raw_value = config.get(config_key)
        if raw_value in (None, ""):
            return platform_limit

        try:
            requested_limit = converter(raw_value)
        except (TypeError, ValueError) as exc:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"{config_key} must be a positive number",
            ) from exc

        if isinstance(raw_value, bool) or requested_limit <= 0:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"{config_key} must be a positive number",
            )

        return min(requested_limit, platform_limit)

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:g}"

    @staticmethod
    def _enforce_row_limit(
        results: list[Dict[str, Any]], max_rows: int, source_label: str
    ) -> None:
        row_count = len(results)
        if row_count <= max_rows:
            return

        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=(
                f"The {source_label} returned {row_count:,} rows, which exceeds "
                f"the limit of {max_rows:,}. Add a filter or LIMIT, or raise "
                "ML_EXTRACT_MAX_ROWS."
            ),
        )

    @staticmethod
    def _enforce_csv_byte_limit(csv_path: Path, max_bytes: int) -> None:
        csv_size = csv_path.stat().st_size
        if csv_size <= max_bytes:
            return

        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=(
                f"CSV file is {csv_size:,} bytes, which exceeds the limit "
                f"of {max_bytes:,} bytes for training extracts. "
                "Use a smaller file or raise ML_EXTRACT_MAX_BYTES."
            ),
        )

    async def _get_database_manager(self, data_source_id: str):
        """
        Get database manager for the given data source ID.

        Args:
            data_source_id: Data source identifier

        Returns:
            DatabaseManager instance or None if datasource not found
        """
        db_provider_manager = DBProviderManager.get_instance()
        return await db_provider_manager.get_database_manager(data_source_id)

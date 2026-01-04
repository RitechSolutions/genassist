"""
Train Data Source node implementation using the BaseNode class.

This node fetches training data from databases or CSV files for ML model training.
"""

from typing import Dict, Any
import logging
import os
import asyncio
from pathlib import Path
from uuid import UUID

from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.integration.database.provider_manager import DBProviderManager
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)


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

            logger.info(
                f"Processing train data source node: {name} (type: {source_type})"
            )

            if source_type == "datasource":
                return await self._process_database_source(config)
            elif source_type == "csv":
                return await self._process_csv_source(config)
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

    async def _process_database_source(self, config: Dict[str, Any]) -> Dict[str, Any]:
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
                    timeout=30.0,  # 30 second timeout
                )
            except asyncio.TimeoutError as exc:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="Database query timed out after 30 seconds",
                ) from exc

            if error_msg:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Database query failed: {error_msg}",
                )

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

    async def _process_csv_source(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process CSV data source.

        Args:
            config: Node configuration

        Returns:
            Dictionary with CSV data and metadata
        """
        csv_file_path = config.get("csvFilePath")

        if not csv_file_path:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="csvFilePath is required for CSV source type",
            )

        logger.info(f"Processing CSV file: {csv_file_path}")

        try:
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

            # Parse CSV file
            results = ml_utils.parse_csv_file(csv_file_path)

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

    async def _get_database_manager(self, data_source_id: str):
        """
        Get database manager for the given data source ID.

        Args:
            data_source_id: Data source identifier

        Returns:
            DatabaseManager instance or None if not found
        """
        try:
            db_provider_manager = DBProviderManager.get_instance()
            return await db_provider_manager.get_database_manager(data_source_id)
        except Exception as e:
            logger.error(
                f"Error getting database manager for {data_source_id}: {str(e)}"
            )
            return None

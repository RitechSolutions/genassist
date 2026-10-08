"""
Train Data Source node implementation using the BaseNode class.

This node fetches training data from databases or uploaded files for ML model training.
"""

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, TypeVar

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.core.utils.sensitive_data_utils import redact_bound_values
from app.modules.integration.database.bound_parameters import BoundValueError
from app.modules.integration.database.provider_manager import DBProviderManager
from app.modules.integration.database.query_validator import AdvancedQueryValidator
from app.modules.integration.database.read_only_sql import (
    read_only_sql_blocked_message,
    validate_read_only_sql,
)
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.utils import (
    PARAM_STYLE_NAMED,
    PARAM_STYLE_PYFORMAT,
    BoundParameters,
    QueryVariableError,
    bind_config_vars,
)

logger = logging.getLogger(__name__)

NumericLimit = TypeVar("NumericLimit", int, float)

@dataclass(frozen=True)
class ExtractionLimits:
    """Effective limits for one Train Data Source execution."""

    max_rows: int
    max_bytes: int
    extraction_timeout_seconds: float


class TrainDataSourceNode(BaseNode):
    """
    Train Data Source node that fetches training data from databases or uploaded files.

    Supports:
    - Database queries with bound workflow variables
    - File parsing for CSV, Excel (.xlsx), JSON, and Parquet uploads
    - The SQL database providers supported by DatabaseManager
    """

    client_safe_failure_messages = True

    def _unresolved_config_fields(self) -> set[str]:
        """Keep SQL templates intact until they can be bound for the driver."""
        return {"query"}

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a train data source node.

        Args:
            config: The resolved configuration for the node containing:
                - name: Node name
                - sourceType: "datasource" or "csv"
                - dataSourceId: Data source identifier (for database mode)
                - query: SQL query string (for database mode)
                - csvFileName: Name of the uploaded file (for file mode)
                - csvFilePath: Server path to the uploaded file (for file mode)
                - csvFileId: File Manager ID of the uploaded file (for file mode)

        Returns:
            Dictionary with training data and metadata
        """
        try:
            name = config.get("name", "Training Data")
            source_type = config.get("sourceType")

            if source_type not in ("datasource", "csv"):
                raise AppException(
                    error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                    error_detail="Choose a database or uploaded file for Train Data Source.",
                )

            limits = self._resolve_extraction_limits(config)
            chunk_rows = settings.ML_EXTRACT_CHUNK_ROWS

            logger.info(
                "Processing train data source node %s (type=%s, max_rows=%s, "
                "max_bytes=%s, timeout=%ss)",
                name,
                source_type,
                limits.max_rows,
                limits.max_bytes,
                self._format_number(limits.extraction_timeout_seconds),
            )

            if source_type == "datasource":
                return await self._process_database_source(config, limits, chunk_rows)
            return await self._process_csv_source(config, limits, chunk_rows)

        except AppException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error in train data source node: %s",
                self._sanitized_diagnostic(e),
            )
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_FAILED,
                error_detail=f"Train data source processing failed: {str(e)}",
            ) from e

    async def _process_database_source(
        self,
        config: Dict[str, Any],
        limits: ExtractionLimits,
        chunk_rows: int,
    ) -> Dict[str, Any]:
        """
        Process database data source.

        Args:
            config: Node configuration

        Returns:
            Dictionary with database query results and metadata
        """
        data_source_id = config.get("dataSourceId")
        query_template = config.get("query", "")

        if not data_source_id:
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                error_detail="Select a data source.",
            )

        if not query_template:
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                error_detail="Enter a SQL query.",
            )

        logger.info(f"Executing database query for datasource: {data_source_id}")

        try:
            db_manager = await self._get_database_manager(data_source_id)
            if not db_manager:
                raise AppException(
                    error_key=ErrorKey.DATASOURCE_NOT_FOUND,
                    error_detail=f"Database connection not available for datasource {data_source_id}",
                )

            # Datasource DB types are mapped to SQLGlot dialects by
            # read_only_sql.SQLGLOT_DIALECTS; keep supported types aligned there.
            db_type = db_manager.get_db_type()
            logger.debug("Using database manager for %s database", db_type)

            try:
                validation_query, statement, parameters = self._bind_database_query(
                    query_template,
                    db_type,
                )
            except QueryVariableError as exc:
                raise AppException(
                    error_key=ErrorKey.READ_ONLY_SQL_BLOCKED,
                    status_code=400,
                    error_detail=str(exc),
                ) from None

            logger.info(
                "Executing training query with %d bound parameter(s)",
                len(parameters),
            )

            # Fail closed before execution. The rejection reason is generated by the
            # read-only policy and is safe to expose; stream_query adds DB-level
            # read-only defense in depth for statements that pass this gate.
            validation = validate_read_only_sql(validation_query, db_type)
            if not validation.is_valid:
                error = read_only_sql_blocked_message(validation)
                logger.warning(error)
                raise AppException(
                    error_key=ErrorKey.READ_ONLY_SQL_BLOCKED,
                    status_code=400,
                    error_detail=error,
                )

            self._log_query_advisories(validation_query, db_manager)

            # Stream query rows directly to CSV under one timeout. The writer
            # closes the database iterator and removes its partial file on any
            # failure, including cancellation by wait_for.
            try:
                chunks = self._stream_bound_query(
                    db_manager,
                    statement,
                    parameters,
                    chunk_rows,
                )
                csv_file_path, columns, row_count, sample_data = await asyncio.wait_for(
                    ml_utils.stream_rows_to_csv(
                        chunks,
                        self.state.thread_id,
                        max_rows=limits.max_rows,
                        max_bytes=limits.max_bytes,
                    ),
                    timeout=limits.extraction_timeout_seconds,
                )
            except BoundValueError as exc:
                raise AppException(
                    error_key=ErrorKey.READ_ONLY_SQL_BLOCKED,
                    status_code=400,
                    error_detail=str(exc),
                ) from None
            except asyncio.TimeoutError as exc:
                raise self._extraction_timeout_error(limits) from exc
            except AppException:
                raise
            except OSError as exc:
                raise self._storage_error(exc) from None
            except Exception as exc:
                safe_error = self._sanitized_diagnostic(
                    redact_bound_values(exc, parameters)
                )
                logger.error(
                    "Training database query failed with %d bound parameter(s): %s",
                    len(parameters),
                    safe_error,
                )
                raise AppException(
                    error_key=ErrorKey.ML_EXTRACT_QUERY_FAILED,
                    error_detail=self._client_safe_database_error(
                        exc,
                        has_bound_parameters=bool(parameters),
                    ),
                ) from None

            if not row_count:
                logger.warning("Database query returned no results")
            else:
                logger.info(
                    "Database query successful: %s rows, %s columns",
                    row_count,
                    len(columns),
                )

            return self._build_success_response(
                csv_file_path,
                columns,
                row_count,
                sample_data,
            )

        except AppException:
            raise
        except Exception as e:
            logger.error(
                "Error processing database source: %s",
                self._sanitized_diagnostic(e),
            )
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_FAILED,
                error_detail=f"Database source processing failed: {str(e)}",
            ) from e

    async def _process_csv_source(
        self,
        config: Dict[str, Any],
        limits: ExtractionLimits,
        chunk_rows: int,
    ) -> Dict[str, Any]:
        """
        Process an uploaded training-file source.

        Args:
            config: Node configuration

        Returns:
            Dictionary with uploaded-file data and metadata
        """
        csv_file_path = config.get("csvFilePath")
        csv_file_id = config.get("csvFileId")
        csv_file_name = config.get("csvFileName")

        if not csv_file_path and not csv_file_id:
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                error_detail="Upload a training file.",
            )

        logger.info("Processing uploaded training file")

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
                # Keep the extension so parser dispatch selects the right format.
                original_suffix = Path(csv_file_name).suffix if csv_file_name else Path(csv_file_path or "").suffix
                dest_file_path = f"{DATA_VOLUME}/train/{csv_file_id}{original_suffix or '.csv'}"

                logger.info("Downloading uploaded training file for processing")

                try:
                    await file_manager_service.download_file_to_path(csv_file_id, dest_file_path)
                except Exception as exc:
                    logger.error(
                        "Could not download training file: %s",
                        self._sanitized_diagnostic(exc),
                    )
                    raise self._file_unavailable_error() from None

                csv_file_path = dest_file_path

            csv_path = Path(csv_file_path)
            if not csv_path.exists():
                raise self._file_unavailable_error()

            if not os.access(csv_file_path, os.R_OK):
                raise AppException(
                    error_key=ErrorKey.ML_EXTRACT_FILE_UNAVAILABLE,
                    error_detail=(
                        "The uploaded training file cannot be read. Upload it again."
                    ),
                )

            self._enforce_csv_byte_limit(csv_path, limits.max_bytes)

            suffix = csv_path.suffix.lower()

            async def stream_training_file():
                if suffix == ".csv":
                    chunks = ml_utils.iter_csv_chunks(str(csv_path), chunk_rows)
                    source_kind = "csv"
                else:
                    records = await asyncio.to_thread(
                        ml_utils.parse_training_file,
                        str(csv_path),
                    )
                    chunks = ml_utils.iter_record_chunks(records, chunk_rows)
                    source_kind = "file"

                return await ml_utils.stream_rows_to_csv(
                    chunks,
                    self.state.thread_id,
                    max_rows=limits.max_rows,
                    max_bytes=limits.max_bytes,
                    source_kind=source_kind,
                )

            try:
                saved_csv_path, columns, row_count, sample_data = await asyncio.wait_for(
                    stream_training_file(),
                    timeout=limits.extraction_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise self._extraction_timeout_error(limits) from exc

            logger.info(
                "Training file parsing successful: %s rows, %s columns",
                row_count,
                len(columns),
            )
            return self._build_success_response(
                saved_csv_path,
                columns,
                row_count,
                sample_data,
            )

        except AppException:
            raise
        except OSError as exc:
            raise self._storage_error(exc) from None
        except Exception as e:
            logger.error(
                "Error processing uploaded training file: %s",
                self._sanitized_diagnostic(e),
            )
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_FAILED,
                error_detail=f"CSV source processing failed: {str(e)}",
            ) from e

    @staticmethod
    def _log_query_advisories(query: str, db_manager: Any) -> None:
        """Log existing validator warnings without making advice blocking."""
        try:
            # This advisory-only path does not perform schema validation, so
            # avoid a live schema fetch here.
            advisory = AdvancedQueryValidator(
                db_manager,
                schema={"tables": []},
            ).validate_query(query)
            for warning in advisory.warnings or []:
                logger.warning("Training query advisory: %s", warning)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Advisory validation must never block extraction.
            logger.debug("Advisory validation skipped: %s", exc)

    def _bind_database_query(
        self,
        query_template: str,
        db_type: str,
    ) -> tuple[str, str, BoundParameters]:
        """Create the validation and driver-specific forms of a query."""
        source_output = self.get_input_from_source()
        direct_input = self.direct_input if isinstance(self.direct_input, dict) else {}
        validation_query, parameters = bind_config_vars(
            query_template,
            self.state,
            source_output,
            direct_input=direct_input,
            param_style=PARAM_STYLE_NAMED,
            db_type=db_type,
        )

        statement = validation_query
        if str(db_type).strip().lower() == "snowflake":
            statement, parameters = bind_config_vars(
                query_template,
                self.state,
                source_output,
                direct_input=direct_input,
                param_style=PARAM_STYLE_PYFORMAT,
                db_type=db_type,
            )
        return validation_query, statement, parameters

    @staticmethod
    def _stream_bound_query(
        db_manager: Any,
        statement: str,
        parameters: Mapping[str, Any],
        chunk_size: int,
    ):
        """Create a stream without changing the no-parameter call path."""
        if parameters:
            return db_manager.stream_query(
                statement,
                parameters,
                chunk_size=chunk_size,
            )
        return db_manager.stream_query(statement, chunk_size=chunk_size)

    @staticmethod
    def _build_success_response(
        data_path: str,
        columns: list[str],
        row_count: int,
        sample_data: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the shared output contract for database and file extracts."""
        return {
            "success": True,
            "data": sample_data,
            "data_path": data_path,
            "metadata": {
                "rowCount": row_count,
                "columns": columns,
            },
        }

    @classmethod
    def _extraction_timeout_error(cls, limits: ExtractionLimits) -> AppException:
        """Build the shared timeout error for database and file extracts."""
        return AppException(
            error_key=ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED,
            error_detail=(
                "Training data extraction timed out after "
                f"{cls._format_duration(limits.extraction_timeout_seconds)}"
            ),
        )

    @staticmethod
    def _file_unavailable_error() -> AppException:
        """Build the shared missing-upload error."""
        return AppException(
            error_key=ErrorKey.ML_EXTRACT_FILE_UNAVAILABLE,
            error_detail=(
                "The uploaded training file is no longer available. Upload it again."
            ),
        )

    @staticmethod
    def _storage_error(error: OSError) -> AppException:
        """Log and build the shared training-output storage error."""
        logger.error("Training data storage failure: %s", error)
        return AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Training data storage failed: {str(error)}",
        )

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
            extraction_timeout_seconds=cls._resolve_limit(
                config,
                "timeoutSeconds",
                float(settings.ML_EXTRACT_TIMEOUT_SECONDS),
                float,
            ),
        )

    @classmethod
    def _resolve_limit(
        cls,
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
                error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                error_detail=f"{cls._limit_label(config_key)} must be a positive number.",
            ) from exc

        if isinstance(raw_value, bool) or requested_limit <= 0:
            raise AppException(
                error_key=ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
                error_detail=f"{cls._limit_label(config_key)} must be a positive number.",
            )

        return min(requested_limit, platform_limit)

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:g}"

    @classmethod
    def _format_duration(cls, seconds: float) -> str:
        unit = "second" if seconds == 1 else "seconds"
        return f"{cls._format_number(seconds)} {unit}"

    @staticmethod
    def _limit_label(config_key: str) -> str:
        return {
            "maxRows": "The row limit",
            "maxBytes": "The file-size limit",
            "timeoutSeconds": "The extraction timeout",
        }.get(config_key, "This limit")

    @staticmethod
    def _sanitized_diagnostic(error: Any) -> str:
        return ml_utils.sanitized_database_diagnostic(error)

    @staticmethod
    def _client_safe_database_error(
        error: Exception,
        *,
        has_bound_parameters: bool,
    ) -> str:
        return ml_utils.client_safe_database_error(
            error,
            has_bound_parameters=has_bound_parameters,
        )

    @staticmethod
    def _enforce_csv_byte_limit(csv_path: Path, max_bytes: int) -> None:
        csv_size = csv_path.stat().st_size
        if csv_size <= max_bytes:
            return

        raise AppException(
            error_key=ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED,
            error_detail=(
                f"CSV file is {csv_size:,} bytes, which exceeds the limit "
                f"of {max_bytes:,} bytes for training extracts. "
                "Use a smaller file or ask an administrator to raise the file-size limit."
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

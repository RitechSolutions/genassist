# Standard library imports
import asyncio
import logging
import os
from typing import Dict, List, Any, Tuple, Optional

# Third-party imports
import snowflake.connector
from cryptography.hazmat.primitives import serialization

# Local application imports
from app.core.utils.encryption_utils import decrypt_key

logger = logging.getLogger(__name__)


class SnowflakeManager:
    """
    Snowflake datasource manager supporting private key and password authentication.
    Automatically handles token expiry and converts PEM keys to DER format.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Dictionary containing:
                - account: Snowflake account identifier
                - username: Snowflake username
                - warehouse: Snowflake warehouse name
                - database: Snowflake database name
                - schema: Schema name (default: "PUBLIC")
                - role: Snowflake role (optional)
                - auth_method: "private_key" or "password" (default: "password")
                - private_key: Encrypted PEM private key string (for private_key auth)
                - private_key_passphrase: Encrypted passphrase (optional)
                - password: Encrypted password (for password auth)
                - allowed_tables: List of allowed table names (optional)
        """
        self.config = config
        self.connection = None
        self.schema = None

        # Parse allowed tables
        allowed_tables = self.config.get("allowed_tables", None)
        if isinstance(allowed_tables, list):
            self.allowed_tables = allowed_tables
        elif allowed_tables and isinstance(allowed_tables, str):
            self.allowed_tables = [t.strip() for t in allowed_tables.split(",")]
        else:
            self.allowed_tables = []

    # ---------------------------
    # Private helpers
    # ---------------------------

    def _private_key_der_from_pem(self, pem_str: str, passphrase: Optional[str]) -> bytes:
        """
        Convert a PEM (encrypted or not) private key string to *unencrypted* PKCS#8 DER bytes.
        Exactly what the Snowflake connector expects under 'private_key'.
        """
        # cryptography is now directly imported, no need to check
        if not pem_str or not pem_str.strip():
            raise ValueError("Private key PEM is empty.")

        key = serialization.load_pem_private_key(
            pem_str.encode("utf-8"),
            password=None if passphrase is None else passphrase.encode("utf-8")
        )
        return key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )


    def _build_conn_params(self) -> Dict[str, Any]:
        """
        Build the connection parameters for the Snowflake connector based on config.
        """
        # Snowflake connector is now directly imported, no need to check

        auth_method = self.config.get("auth_method", "password")
        client_session_keep_alive = self.config.get("client_session_keep_alive", True)

        params: Dict[str, Any] = {
            "user": self.config.get("username"),
            "account": self.config.get("account"),
            "warehouse": self.config.get("warehouse"),
            "database": self.config.get("database"),
            "schema": self.config.get("schema", "PUBLIC"),
        }
        role = self.config.get("role")
        if role:
            params["role"] = role
        if client_session_keep_alive:
            params["client_session_keep_alive"] = True

        # --- Key-pair auth ---
        if auth_method == "private_key":
            private_key = self.config.get("private_key")
            if not private_key:
                raise ValueError("auth_method='private_key' requires 'private_key' in config.")
            
            pem_str = decrypt_key(private_key)
            passphrase = decrypt_key(self.config["private_key_passphrase"]) if self.config.get("private_key_passphrase") else None
            der_bytes = self._private_key_der_from_pem(pem_str, passphrase)
            params["private_key"] = der_bytes
            logger.info("Using key-pair authentication.")
            return params

        # --- Password auth (fallback) ---
        if auth_method == "password":
            pwd = self.config.get("password")
            if not pwd:
                raise ValueError("auth_method='password' requires 'password' in config.")
            params["password"] = decrypt_key(pwd)
            logger.info("Using password authentication.")
            return params

        # Back-compat safety
        raise ValueError(f"Unsupported auth_method: {auth_method}")

    # ---------------------------
    # Public API
    # ---------------------------

    async def connect(self):
        """
        Establish a connection to Snowflake. If you're inside an async app,
        consider running this in a thread to avoid blocking the event loop.
        """
        params = self._build_conn_params()

        def _do_connect():
            return snowflake.connector.connect(**params)

        # If your stack is **purely async**, uncomment the next line to avoid blocking:
        # self.connection = await asyncio.to_thread(_do_connect)
        # For simplicity, we'll block here (still fine for many apps):
        self.connection = _do_connect()
        logger.info("Connected to Snowflake data warehouse.")

    async def disconnect(self):
        """Close the connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Snowflake connection closed.")
            except Exception as e:
                logger.error(f"Error closing Snowflake connection: {e}")
            finally:
                self.connection = None

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Execute a SQL query with a one-time reconnect on token-expiry (390114).
        Returns (rows_as_dicts, error_message_or_None).
        """
        if not self.connection:
            await self.connect()

        def _run_once() -> List[Dict[str, Any]]:
            cur = self.connection.cursor()
            try:
                if parameters:
                    cur.execute(query, parameters)
                else:
                    cur.execute(query)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                return [dict(zip(cols, r)) for r in rows]
            finally:
                cur.close()

        try:
            # rows = await asyncio.to_thread(_run_once)  # optional in async contexts
            rows = _run_once()
            return rows, None
        except Exception as e:
            msg = str(e)
            if "390114" in msg or "Authentication token has expired" in msg:
                logger.warning("Auth token expired; reconnecting and retrying once.")
                try:
                    await self.disconnect()
                    await self.connect()
                    # rows = await asyncio.to_thread(_run_once)
                    rows = _run_once()
                    return rows, None
                except Exception as e2:
                    logger.error(f"Retry after token expiry failed: {e2}")
                    return [], str(e2)
            logger.error(f"Error executing Snowflake query: {e}")
            return [], str(e)

    async def _get_schema(
        self,
        include_samples: bool = True,
        sample_size: int = 1,
        include_categorical_values: bool = True,
        max_categorical_values: int = 10
    ) -> Dict[str, Any]:
        """Retrieve schema info for current database+schema; respects allowed_tables."""
        if not self.connection:
            await self.connect()

        cur = self.connection.cursor()
        try:
            current_database = self.config.get('database', 'SNOWFLAKE')
            current_schema = self.config.get('schema', 'PUBLIC')

            tables_query = """
            SELECT 
                table_name,
                table_schema,
                table_type
            FROM information_schema.tables 
            WHERE table_catalog = %s 
              AND table_schema = %s
            ORDER BY table_name
            LIMIT 50
            """
            logger.info(f"Executing tables query for {current_database}.{current_schema}")
            cur.execute(tables_query, [current_database, current_schema])
            tables_data = cur.fetchall()
            logger.info(f"Found {len(tables_data)} tables in {current_database}.{current_schema}")

            tables: List[Dict[str, Any]] = []
            allowed_upper = [t.upper() for t in self.allowed_tables] if self.allowed_tables else None

            for table_name, table_schema, table_type in tables_data:
                if allowed_upper and table_name.upper() not in allowed_upper:
                    continue

                columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_catalog = %s 
                  AND table_name = %s 
                  AND table_schema = %s
                ORDER BY ordinal_position
                LIMIT 20
                """
                cur.execute(columns_query, [current_database, table_name, table_schema])
                columns_data = cur.fetchall()

                columns: List[Dict[str, Any]] = []
                for col_name, data_type, is_nullable, column_default in columns_data:
                    col_info: Dict[str, Any] = {
                        "name": col_name,
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                        "default": column_default
                    }

                    # Categorical sampler for text-like columns
                    if include_categorical_values and data_type in ('TEXT', 'VARCHAR', 'CHAR'):
                        try:
                            # Validate identifiers to prevent SQL injection
                            safe_col = self._validate_identifier(col_name)
                            safe_schema = self._validate_identifier(table_schema)
                            safe_table = self._validate_identifier(table_name)

                            if not all([safe_col, safe_schema, safe_table]):
                                logger.warning(f"Invalid identifier detected, skipping categorical probe for {table_schema}.{table_name}.{col_name}")
                                continue

                            # Use quoted identifiers for safety
                            count_query = f"""
                            SELECT COUNT(DISTINCT "{safe_col}")
                            FROM "{safe_schema}"."{safe_table}"
                            WHERE "{safe_col}" IS NOT NULL
                            """
                            cur.execute(count_query)
                            total_distinct = cur.fetchone()[0]
                            col_info["total_distinct_count"] = total_distinct

                            if total_distinct <= 50:
                                # max_categorical_values is an int from function parameter, safe to use
                                categorical_query = f"""
                                SELECT DISTINCT "{safe_col}"
                                FROM "{safe_schema}"."{safe_table}"
                                WHERE "{safe_col}" IS NOT NULL
                                LIMIT {int(max_categorical_values)}
                                """
                                cur.execute(categorical_query)
                                sample_vals = cur.fetchall()
                                if sample_vals:
                                    col_info["categorical_values"] = [r[0] for r in sample_vals]
                        except Exception as e:
                            logger.warning(f"Categorical probe failed for {table_schema}.{table_name}.{col_name}: {e}")

                    columns.append(col_info)

                tables.append({
                    "name": f"{table_schema}.{table_name}",
                    "schema": table_schema,
                    "table": table_name,
                    "type": table_type,
                    "columns": columns
                })

            schema_result = {
                "tables": tables,
                "database": self.config.get('database', 'unknown'),
                "schema_count": len(set(t["schema"] for t in tables))
            }
            logger.info(f"Schema retrieval complete. Found {len(tables)} tables.")
            return schema_result

        finally:
            cur.close()

    def _validate_identifier(self, identifier: str) -> Optional[str]:
        """
        Validate and sanitize a SQL identifier to prevent SQL injection.
        Returns the sanitized identifier or None if invalid.
        Snowflake identifiers must start with a letter or underscore and contain only
        alphanumeric characters, underscores, and dollar signs.
        """
        import re
        if not identifier:
            return None
        # Remove any double quotes that might be present
        identifier = identifier.strip('"')
        # Snowflake identifier pattern: starts with letter/underscore, followed by alphanumeric/underscore/dollar
        if re.match(r'^[A-Za-z_][A-Za-z0-9_$]*$', identifier):
            return identifier
        return None

    def _is_categorical_column(self, data_type: str, column_name: str) -> bool:
        categorical_types = {'VARCHAR', 'CHAR', 'STRING', 'TEXT'}
        if data_type.upper() in categorical_types:
            return True
        patterns = ['type', 'status', 'category', 'kind', 'class', 'group', 'level', 'grade', 'rank']
        return any(p in column_name.lower() for p in patterns)

    async def get_schema(
        self,
        include_samples: bool = True,
        sample_size: int = 1,
        include_categorical_values: bool = True,
        max_categorical_values: int = 10
    ) -> Dict[str, Any]:
        if not self.schema:
            self.schema = await self._get_schema(
                include_samples=include_samples,
                sample_size=sample_size,
                include_categorical_values=include_categorical_values,
                max_categorical_values=max_categorical_values
            )
        return self.schema

    async def initialize(self):
        await self.connect()
        await self.get_schema()

from typing import Dict, List, Any, Tuple, Optional
import logging
import yaml
import os
from sshtunnel import SSHTunnelForwarder
from app.core.utils.encryption_utils import decrypt_key
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from sqlalchemy.pool import NullPool
import asyncio
from app.modules.integration.snowflake import SnowflakeManager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Handles interaction with the database, including SSH tunneling if necessary.
    """

    def __init__(self, config: Dict[str, Any]):
        # self.config: Dict = self._load_config(config_path)
        self.config = config
        self.connection_string = self.config.get("connection_string")
        # Map source_type to database_type for compatibility
        # For Snowflake, source_type is "Snowflake" and there's no database_type
        source_type = self.config.get("source_type", "").lower()
        if source_type == "snowflake":
            self.db_type = "snowflake"
        else:
            self.db_type = self.config.get("database_type") or self.config.get("source_type")

        ssh_config = {
            'ssh_tunnel_host': self.config.get('ssh_tunnel_host'),
            'ssh_tunnel_port': self.config.get('ssh_tunnel_port'),
            'ssh_tunnel_user': self.config.get('ssh_tunnel_user'),
            'ssh_tunnel_private_key': self.config.get('ssh_tunnel_private_key')
        }
        # self.ssh_config will remain empty if no SSH tunneling is configured
        self.ssh_config = {k: v for k,
                           v in ssh_config.items() if v is not None}

        self.engine: Optional[AsyncEngine] = None
        self.tunnel = None
        self.snowflake_manager: Optional[SnowflakeManager] = None

        allowed_tables = self.config.get("allowed_tables", None)
        if isinstance(allowed_tables, list):
            self.allowed_tables = allowed_tables
        elif allowed_tables and isinstance(allowed_tables, str):
            self.allowed_tables = [table.strip()
                                   for table in allowed_tables.split(",")]
        else:
            self.allowed_tables = []

    def get_db_type(self) -> str:
        return self.db_type

    async def initialize(self):
        await self.connect()
        self.schema = await self._get_schema(include_samples=True, sample_size=1)

    def _load_config(self, config_path: str) -> Dict:
        """
        Loads configuration from a YAML or JSON file.

        Args:
            config_path: Path to the configuration file (YAML or JSON)

        Returns:
            Dictionary containing configuration parameters
        """
        import json
        import os

        if not config_path:
            logger.warning("No config path provided")
            return {}

        try:
            file_extension = os.path.splitext(config_path)[1].lower()
            with open(config_path, "r") as file:
                if file_extension in ['.yaml', '.yml']:
                    config = yaml.safe_load(file)
                elif file_extension in ['.json']:
                    config = json.load(file)
                else:
                    # Try to detect format based on content
                    content = file.read()
                    file.seek(0)  # Reset file pointer to beginning

                    try:
                        # First try JSON
                        config = json.loads(content)
                    except json.JSONDecodeError:
                        # If that fails, try YAML
                        config = yaml.safe_load(file)

                logger.info(
                    f"Configuration loaded successfully from {config_path}")
                return config
        except Exception as e:
            logger.error(
                f"Error loading configuration from {config_path}: {e}")
            return {}

    async def connect(self):
        """Establishes an async connection to the database using SQLAlchemy."""

        try:
            if self.ssh_config:
                await self._setup_ssh_tunnel()

            if self.db_type == "postgresql":
                # Use asyncpg for PostgreSQL connections
                if not hasattr(self, "connection_string") or not self.connection_string:
                    port = self.tunnel.local_bind_port if (hasattr(
                        self, 'tunnel') and self.tunnel) else self.config.get("database_port", 5432)
                    host = "127.0.0.1" if (hasattr(self, 'tunnel') and self.tunnel) else self.config.get(
                        "database_host", "localhost")
                    connection_string = f"postgresql+asyncpg://{self.config.get('database_user')}:" \
                        f"{decrypt_key(self.config.get('database_password'))}@{host}:" \
                        f"{port}/{self.config.get('database_name')}"
                else:
                    connection_string = self.connection_string
                logger.info(
                    f"Connecting to PostgreSQL with connection string: {connection_string}")
                self.engine = create_async_engine(
                    connection_string,
                    echo=False,
                    poolclass=NullPool,  # Use NullPool for external database connections
                    future=True
                )
                logger.info("Connected to PostgreSQL database")
            elif self.db_type == "mysql":
                # Use aiomysql for MySQL connections
                port = self.tunnel.local_bind_port if (hasattr(
                    self, 'tunnel') and self.tunnel) else self.config.get("database_port", 3306)
                host = "127.0.0.1" if (hasattr(self, 'tunnel') and self.tunnel) else self.config.get(
                    "database_host", "localhost")
                connection_string = f"mysql+aiomysql://{self.config.get('database_user')}:" \
                    f"{decrypt_key(self.config.get('database_password'))}@{host}:" \
                    f"{port}/{self.config.get('database_name')}"
                logger.info(
                    f"Connecting to MySQL with connection string: {connection_string}")
                self.engine = create_async_engine(
                    connection_string,
                    echo=False,
                    poolclass=NullPool,  # Use NullPool for external database connections
                    future=True
                )
                logger.info("Connected to MySQL database")
            elif self.db_type == "sqlite":
                # Use aiosqlite for SQLite connections
                db_path = self.config.get("database_path", ":memory:")
                connection_string = f"sqlite+aiosqlite:///{db_path}"
                logger.info(
                    f"Connecting to SQLite with connection string: {connection_string}")
                self.engine = create_async_engine(
                    connection_string,
                    echo=False,
                    future=True
                )
                logger.info("Connected to SQLite database")
            elif self.db_type and self.db_type.lower() == "snowflake":
                # Use SnowflakeManager for Snowflake connections
                logger.info("Initializing Snowflake connection")
                self.snowflake_manager = SnowflakeManager(self.config)
                await self.snowflake_manager.connect()
                logger.info("Connected to Snowflake database")
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            await self.disconnect()
            raise

    async def _setup_ssh_tunnel(self):
        """Sets up an SSH tunnel for database connection."""
        ssh_key_path = None
        try:
            logger.info("Setting up ssh tunnel")
            ssh_host = self.ssh_config.get("ssh_tunnel_host")
            ssh_port = self.ssh_config.get("ssh_tunnel_port", 22)
            ssh_user = self.ssh_config.get("ssh_tunnel_user")
            ssh_key_content = decrypt_key(self.ssh_config.get(
                "ssh_tunnel_private_key"))  # PEM content as string
            db_host = self.config.get("database_host")
            db_port = self.config.get("database_port")

            current_dir = os.path.dirname(os.path.abspath(__file__))
            ssh_key_path = os.path.join(
                current_dir, f"{self.config.get('database_name')}_ssh_key.pem")
            logger.info("ssh key path: %s", ssh_key_path)

            self._save_key_to_file(ssh_key_content, ssh_key_path)
            logger.info("Saved tunnel key to %s", ssh_key_path)

            self.tunnel = SSHTunnelForwarder(
                (ssh_host, int(ssh_port)),
                ssh_username=ssh_user,
                ssh_pkey=ssh_key_path,
                # ssh_pkey=private_key,
                remote_bind_address=(db_host, int(db_port))
            )

            await asyncio.to_thread(self.tunnel.start)
            logger.info(f"SSH tunnel established to {ssh_host}:{ssh_port}")

        except Exception as e:
            logger.error(f"Error setting up SSH tunnel: {e}")
            if self.tunnel and self.tunnel.is_active:
                await asyncio.to_thread(self.tunnel.stop)
                self.tunnel = None
            raise

        finally:
            # Delete the key file after tunnel is successfully opened
            if ssh_key_path and os.path.isfile(ssh_key_path):
                try:
                    os.remove(ssh_key_path)
                    logger.info(f"SSH key file deleted: {ssh_key_path}")
                except OSError as e:
                    logger.warning(
                        f"Could not delete SSH key file {ssh_key_path}: {e}")

    def _save_key_to_file(self, key_content, file_path):
        """
        Save an SSH key string to a file with the specified path.

        Args:
            key_content (str): The SSH key content as a string
            file_path (str): The path where the key should be saved

        Returns:
            str: The file path where the key was saved
        """
        import re
        # Make sure the directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # First replace all spaces with newlines
        formatted_key = key_content.replace(' ', '\n')

        # Fix the header and footer lines using regex
        # Fix: -----BEGIN\nOPENSSH\nPRIVATE\nKEY----- -> -----BEGIN OPENSSH PRIVATE KEY-----
        formatted_key = re.sub(r'-----BEGIN\nOPENSSH\nPRIVATE\nKEY-----',
                               '-----BEGIN OPENSSH PRIVATE KEY-----', formatted_key)

        # Fix: -----END\nOPENSSH\nPRIVATE\nKEY----- -> -----END OPENSSH PRIVATE KEY-----
        formatted_key = re.sub(r'-----END\nOPENSSH\nPRIVATE\nKEY-----',
                               '-----END OPENSSH PRIVATE KEY-----', formatted_key)

        # Remove any empty lines
        lines = [line for line in formatted_key.split('\n') if line.strip()]
        formatted_key = '\n'.join(lines)

        if not formatted_key.endswith('\n'):
            formatted_key += '\n'
        with open(file_path, 'w') as key_file:
            key_file.write(formatted_key)

        os.chmod(file_path, 0o600)

        return file_path

    async def disconnect(self):
        """Closes the database connection and ssh tunnel if necessary."""
        if self.engine:
            try:
                await self.engine.dispose()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self.engine = None
        
        if self.snowflake_manager:
            try:
                await self.snowflake_manager.disconnect()
                logger.info("Snowflake connection closed")
            except Exception as e:
                logger.error(f"Error closing Snowflake connection: {e}")
            finally:
                self.snowflake_manager = None
        if self.tunnel and self.tunnel.is_active:
            try:
                self.tunnel.stop()
                logger.info("SSH tunnel stopped")
            except Exception as e:
                logger.error(f"Error stopping SSH tunnel: {e}")
            finally:
                self.tunnel = None

    async def execute_query(self, query: str, parameters: List = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Executes a database query and returns the results.

        Args:
            query: The SQL query to execute
            parameters: Query parameters to bind

        Returns:
            Tuple containing:
                - List of result rows as dictionaries
                - Error message if an error occurred, None otherwise
        """

        try:
            # Handle Snowflake queries
            if self.db_type and self.db_type.lower() == "snowflake":
                if not self.snowflake_manager:
                    await self.connect()
                return await self.snowflake_manager.execute_query(query, parameters)
            
            # Handle other database types
            if not self.engine:
                await self.connect()

            logger.info(f"Executing query: {query}")

            async with self.engine.begin() as conn:
                if parameters:
                    result = await conn.execute(text(query), parameters)
                else:
                    result = await conn.execute(text(query))

                # Get column names
                columns = list(result.keys()) if result.keys() else []

                # Convert rows to dictionaries
                results = []
                for row in result.fetchall():
                    results.append(dict(zip(columns, row)))

            return results, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing query: {error_msg}")
            return [], error_msg

    async def _get_schema(self, include_samples: bool = True, sample_size: int = 1, include_categorical_values: bool = True, max_categorical_values: int = 10) -> Dict[str, Any]:
        """
        Retrieves the database schema including tables, columns, relationships,
        and optionally sample data for each table and categorical column values.

        Args:
            include_samples: Whether to include sample rows from each table
            sample_size: Number of sample rows to fetch per table
            include_categorical_values: Whether to include possible values for categorical columns
            max_categorical_values: Maximum number of distinct values to fetch for categorical columns

        Returns:
            Dictionary containing the database schema information
        """

        try:
            # Handle Snowflake schema
            if self.db_type and self.db_type.lower() == "snowflake":
                if not self.snowflake_manager:
                    await self.connect()
                return await self.snowflake_manager.get_schema(
                    include_samples=include_samples, 
                    sample_size=sample_size,
                    include_categorical_values=include_categorical_values,
                    max_categorical_values=max_categorical_values
                )
            
            # Handle other database types
            if not self.engine:
                await self.connect()

            schema = {
                "tables": [],
                "relationships": []
            }

            # Use the configured database type
            db_type = self.db_type

            # Get list of tables based on database type
            if db_type == "postgresql":
                # PostgreSQL: Get tables from information_schema
                async with self.engine.begin() as conn:
                    result = await conn.execute(text("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_type = 'BASE TABLE'
                    """))
                    tables = [row[0] for row in result.fetchall()]

                    if self.allowed_tables is None or len(self.allowed_tables) == 0:
                        # If no allowed tables specified, use all tables
                        allowed_tables = tables
                    else:
                        allowed_tables = self.allowed_tables
                    logger.info(f"Allowed tables: {allowed_tables}")
                    # Get column information for each table
                    for table in tables:
                        if table not in allowed_tables:
                            continue

                        table_info = {"name": table, "columns": []}

                        result = await conn.execute(text("""
                            SELECT
                                column_name,
                                data_type,
                                is_nullable,
                                column_default,
                                character_maximum_length,
                                numeric_precision,
                                numeric_scale
                            FROM information_schema.columns
                            WHERE table_name = :table_name
                            AND table_schema = 'public'
                            ORDER BY ordinal_position
                        """), {"table_name": table})

                        columns = result.fetchall()

                        # Get primary key information
                        result = await conn.execute(text("""
                            SELECT column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            WHERE tc.constraint_type = 'PRIMARY KEY'
                            AND tc.table_name = :table_name
                            AND tc.table_schema = 'public'
                        """), {"table_name": table})

                        primary_keys = [pk[0] for pk in result.fetchall()]

                        for column in columns:
                            col_info = {
                                "name": column[0],
                                "type": column[1],
                                "nullable": column[2] == "YES",
                                "primary_key": column[0] in primary_keys,
                                "default": column[3],
                                "max_length": column[4],
                                "precision": column[5],
                                "scale": column[6]
                            }

                            # Add categorical values if requested and column appears to be categorical
                            if include_categorical_values and self._is_categorical_column(column[1], column[4]):
                                try:
                                    # Get distinct values for categorical columns
                                    result = await conn.execute(text(f"""
                                        SELECT DISTINCT "{column[0]}"
                                        FROM "{table}"
                                        WHERE "{column[0]}" IS NOT NULL
                                        ORDER BY "{column[0]}"
                                        LIMIT :limit
                                    """), {"limit": max_categorical_values})

                                    distinct_values = [row[0]
                                                       for row in result.fetchall()]
                                    col_info["possible_values"] = distinct_values

                                    # Get count of distinct values to know if we hit the limit
                                    result = await conn.execute(text(f"""
                                        SELECT COUNT(DISTINCT "{column[0]}")
                                        FROM "{table}"
                                        WHERE "{column[0]}" IS NOT NULL
                                    """))
                                    total_distinct = result.fetchone()[0]
                                    col_info["total_distinct_count"] = total_distinct

                                    if total_distinct > max_categorical_values:
                                        col_info["values_truncated"] = True
                                        logger.info(
                                            f"Column {column[0]} in {table} has {total_distinct} distinct values, showing first {max_categorical_values}")

                                except Exception as e:
                                    logger.warning(
                                        f"Could not fetch categorical values for {table}.{column[0]}: {e}")
                                    col_info["possible_values"] = []

                            table_info["columns"].append(col_info)

                        # Add sample data if requested
                        if include_samples and sample_size > 0:
                            try:
                                # Get sample rows (using double quotes for PostgreSQL)
                                sample_query = f'SELECT * FROM "{table}" LIMIT :limit'
                                result = await conn.execute(text(sample_query), {"limit": sample_size})

                                rows = result.fetchall()
                                columns = list(result.keys())

                                # Convert to list of dicts for better readability
                                samples = []
                                for row in rows:
                                    sample_row = {}
                                    for i, col_name in enumerate(columns):
                                        val = row[i]

                                        # Handle PostgreSQL-specific data types
                                        if isinstance(val, bytes):
                                            try:
                                                val = val.decode('utf-8')
                                            except UnicodeDecodeError:
                                                val = f"<binary data, {len(val)} bytes>"
                                        elif hasattr(val, 'strftime'):
                                            val = val.strftime(
                                                '%Y-%m-%d %H:%M:%S')
                                        elif isinstance(val, (list, dict)):
                                            # Handle JSON/array types
                                            val = str(val)

                                        sample_row[col_name] = val
                                    samples.append(sample_row)

                                table_info["samples"] = samples

                                logger.info(
                                    f"Samples fetched for table {table}: {samples}")

                            except Exception as e:
                                logger.warning(
                                    f"Could not fetch samples for table {table}: {e}")
                                table_info["samples"] = []

                        schema["tables"].append(table_info)

                    # Get foreign key relationships for PostgreSQL
                    for table in tables:
                        if table not in allowed_tables:
                            continue

                        result = await conn.execute(text("""
                            SELECT
                                kcu.column_name,
                                ccu.table_name AS foreign_table_name,
                                ccu.column_name AS foreign_column_name
                            FROM information_schema.table_constraints AS tc
                            JOIN information_schema.key_column_usage AS kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            JOIN information_schema.constraint_column_usage AS ccu
                                ON ccu.constraint_name = tc.constraint_name
                                AND ccu.table_schema = tc.table_schema
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                            AND tc.table_name = :table_name
                            AND tc.table_schema = 'public'
                        """), {"table_name": table})

                        foreign_keys = result.fetchall()

                        for fk in foreign_keys:
                            relationship = {
                                "table": table,
                                "column": fk[0],
                                "referenced_table": fk[1],
                                "referenced_column": fk[2]
                            }
                            schema["relationships"].append(relationship)

            elif db_type in ["sql", "mysql"]:
                async with self.engine.begin() as conn:
                    result = await conn.execute(text("SHOW TABLES"))
                    tables = [row[0] for row in result.fetchall()]
                    if not self.allowed_tables or len(self.allowed_tables) == 0:
                        # If no allowed tables specified, use all tables
                        allowed_tables = tables
                    else:
                        allowed_tables = self.allowed_tables

                    # Get column information for each table
                    for table in tables:
                        if table not in allowed_tables:
                            continue
                        table_info = {"name": table, "columns": []}

                        # Get column details
                        result = await conn.execute(text(f"DESCRIBE `{table}`"))
                        columns = result.fetchall()

                        for column in columns:
                            # Column structure in MySQL: (Field, Type, Null, Key, Default, Extra)
                            col_info = {
                                "name": column[0],
                                "type": column[1],
                                "nullable": column[2] == "YES",
                                "primary_key": column[3] == "PRI",
                                "default": column[4],
                                "extra": column[5]
                            }

                            # Add categorical values if requested and column appears to be categorical
                            if include_categorical_values and self._is_categorical_column(column[1]):
                                try:
                                    # Get distinct values for categorical columns
                                    query = f"""
                                        SELECT DISTINCT `{column[0]}`
                                        FROM `{table}`
                                        WHERE `{column[0]}` IS NOT NULL
                                        ORDER BY `{column[0]}`
                                        LIMIT {max_categorical_values}
                                    """
                                    result = await conn.execute(text(query))

                                    distinct_values = [row[0]
                                                       for row in result.fetchall()]
                                    col_info["possible_values"] = distinct_values

                                    # Get count of distinct values
                                    result = await conn.execute(text(f"""
                                        SELECT COUNT(DISTINCT `{column[0]}`)
                                        FROM `{table}`
                                        WHERE `{column[0]}` IS NOT NULL
                                    """))
                                    total_distinct = result.fetchone()[0]
                                    col_info["total_distinct_count"] = total_distinct

                                    if total_distinct > max_categorical_values:
                                        col_info["values_truncated"] = True
                                        logger.info(
                                            f"Column {column[0]} in {table} has {total_distinct} distinct values, showing first {max_categorical_values}")

                                except Exception as e:
                                    logger.warning(
                                        f"Could not fetch categorical values for {table}.{column[0]}: {e}")
                                    col_info["possible_values"] = []

                            table_info["columns"].append(col_info)

                        # Add sample data if requested
                        if include_samples and sample_size > 0:
                            try:
                                # Get sample rows
                                sample_query = f"SELECT * FROM `{table}` LIMIT :limit"
                                result = await conn.execute(text(sample_query), {"limit": sample_size})

                                rows = result.fetchall()
                                columns = list(result.keys())

                                # Convert to list of dicts for better readability
                                samples = []
                                for row in rows:
                                    sample_row = {}
                                    for i, col_name in enumerate(columns):
                                        # Handle special data types for better readability
                                        val = row[i]

                                        # Convert bytes to strings
                                        if isinstance(val, bytes):
                                            try:
                                                val = val.decode('utf-8')
                                            except UnicodeDecodeError:
                                                val = f"<binary data, {len(val)} bytes>"

                                        # Format dates and datetimes
                                        elif hasattr(val, 'strftime'):
                                            val = val.strftime(
                                                '%Y-%m-%d %H:%M:%S')

                                        sample_row[col_name] = val
                                    samples.append(sample_row)

                                table_info["samples"] = samples

                            except Exception as e:
                                logger.warning(
                                    f"Could not fetch samples for table {table}: {e}")
                                table_info["samples"] = []

                        schema["tables"].append(table_info)

                    # Get foreign key relationships for MySQL
                    for table in tables:
                        if table not in allowed_tables:
                            continue
                        # Get foreign key constraints
                        result = await conn.execute(text("""
                            SELECT
                                COLUMN_NAME,
                                REFERENCED_TABLE_NAME,
                                REFERENCED_COLUMN_NAME
                            FROM
                                INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                            WHERE
                                TABLE_NAME = :table_name
                                AND REFERENCED_TABLE_NAME IS NOT NULL
                                AND TABLE_SCHEMA = DATABASE()
                        """), {"table_name": table})

                        foreign_keys = result.fetchall()

                        for fk in foreign_keys:
                            relationship = {
                                "table": table,
                                "column": fk[0],
                                "referenced_table": fk[1],
                                "referenced_column": fk[2]
                            }
                            schema["relationships"].append(relationship)

            elif db_type == "sqlite":
                async with self.engine.begin() as conn:
                    result = await conn.execute(text(
                        "SELECT name FROM sqlite_master WHERE type='table'"))
                    tables = [row[0] for row in result.fetchall()]

                    if not self.allowed_tables or len(self.allowed_tables) == 0:
                        # If no allowed tables specified, use all tables
                        allowed_tables = tables
                    else:
                        allowed_tables = self.allowed_tables

                    for table in tables:
                        if table not in allowed_tables:
                            continue
                        table_info = {"name": table, "columns": []}

                        result = await conn.execute(text(f"PRAGMA table_info(`{table}`)"))
                        columns = result.fetchall()

                        for column in columns:
                            # Column structure in SQLite: (cid, name, type, notnull, dflt_value, pk)
                            col_info = {
                                "name": column[1],
                                "type": column[2],
                                "nullable": not column[3],
                                "primary_key": bool(column[5]),
                                "default": column[4]
                            }

                            # Add categorical values if requested and column appears to be categorical
                            if include_categorical_values and self._is_categorical_column(column[2]):
                                try:
                                    # Get distinct values for categorical columns
                                    result = await conn.execute(text(f"""
                                        SELECT DISTINCT `{column[1]}`
                                        FROM `{table}`
                                        WHERE `{column[1]}` IS NOT NULL
                                        ORDER BY `{column[1]}`
                                        LIMIT :limit
                                    """), {"limit": max_categorical_values})

                                    distinct_values = [row[0]
                                                       for row in result.fetchall()]
                                    col_info["possible_values"] = distinct_values

                                    # Get count of distinct values
                                    result = await conn.execute(text(f"""
                                        SELECT COUNT(DISTINCT `{column[1]}`)
                                        FROM `{table}`
                                        WHERE `{column[1]}` IS NOT NULL
                                    """))
                                    total_distinct = result.fetchone()[0]
                                    col_info["total_distinct_count"] = total_distinct

                                    if total_distinct > max_categorical_values:
                                        col_info["values_truncated"] = True
                                        logger.info(
                                            f"Column {column[1]} in {table} has {total_distinct} distinct values, showing first {max_categorical_values}")

                                except Exception as e:
                                    logger.warning(
                                        f"Could not fetch categorical values for {table}.{column[1]}: {e}")
                                    col_info["possible_values"] = []

                            table_info["columns"].append(col_info)

                        # Add sample data if requested
                        if include_samples and sample_size > 0:
                            try:
                                # Get sample rows
                                sample_query = f"SELECT * FROM `{table}` LIMIT :limit"
                                result = await conn.execute(text(sample_query), {"limit": sample_size})

                                rows = result.fetchall()
                                columns = list(result.keys())

                                # Convert to list of dicts for better readability
                                samples = []
                                for row in rows:
                                    sample_row = {}
                                    for i, col_name in enumerate(columns):
                                        sample_row[col_name] = row[i]
                                    samples.append(sample_row)

                                table_info["samples"] = samples

                            except Exception as e:
                                logger.warning(
                                    f"Could not fetch samples for table {table}: {e}")
                                table_info["samples"] = []

                        schema["tables"].append(table_info)

                    # Get foreign key relationships
                    for table in tables:
                        if table not in allowed_tables:
                            continue
                        result = await conn.execute(text(f"PRAGMA foreign_key_list(`{table}`)"))
                        foreign_keys = result.fetchall()

                        for fk in foreign_keys:
                            # Foreign key structure: (id, seq, table, from, to, on_update, on_delete, match)
                            relationship = {
                                "table": table,
                                "column": fk[3],
                                "referenced_table": fk[2],
                                "referenced_column": fk[4]
                            }
                            schema["relationships"].append(relationship)

            logger.info(
                f"Retrieved schema with {len(schema['tables'])} tables and {len(schema['relationships'])} relationships")

            return schema

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error retrieving database schema: {error_msg}")
            return {"error": error_msg}
        finally:
            if self.engine:
                await self.disconnect()

    def _is_categorical_column(self, data_type: str, max_length: int = None) -> bool:
        """
        Determines if a column is likely to be categorical based on its data type.

        Args:
            data_type: The database column data type
            max_length: Maximum length for character fields (PostgreSQL)

        Returns:
            Boolean indicating if the column is likely categorical
        """
        data_type_lower = data_type.lower()

        # Explicit categorical types
        if any(cat_type in data_type_lower for cat_type in ['enum', 'set']):
            return True

        # String/character types with reasonable length limits
        if any(str_type in data_type_lower for str_type in ['varchar', 'char', 'text', 'string']):
            # For PostgreSQL, use max_length if available
            if max_length is not None:
                return max_length <= 100  # Arbitrary threshold for categorical vs free text
            # For MySQL/SQLite, extract length from type definition
            elif '(' in data_type_lower:
                try:
                    length_str = data_type_lower.split('(')[1].split(')')[0]
                    length = int(length_str)
                    return length <= 100
                except (ValueError, IndexError):
                    pass
            # Default for text types without clear length
            return True

        # Boolean types
        if any(bool_type in data_type_lower for bool_type in ['bool', 'boolean', 'bit']):
            return True

        # Small integer types (likely categorical)
        if any(int_type in data_type_lower for int_type in ['tinyint', 'smallint']):
            return True

        # Regular integers and large types are typically not categorical
        return False

    async def get_schema(self) -> Dict[str, Any]:
        """
        Returns the database schema.

        Returns:
            Dictionary containing the database schema information
        """
        if not self.schema:
            self.schema = await self._get_schema(include_samples=True, sample_size=1)
        return self.schema

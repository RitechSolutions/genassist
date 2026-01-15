"""
pgvector vector database implementation
"""

import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from app.db.multi_tenant_session import multi_tenant_manager
from app.core.tenant_scope import get_tenant_context

from .base import BaseVectorDB, VectorDBConfig, SearchResult

logger = logging.getLogger(__name__)


class PgVectorDB(BaseVectorDB):
    """pgvector vector database provider using PostgreSQL"""

    def __init__(self, config: VectorDBConfig):
        super().__init__(config)
        self.engine: Optional[AsyncEngine] = None
        self.table_name: str = f"vector_store_{config.collection_name.replace('-', '_').replace('.', '_')}"
        self.dimension: Optional[int] = None

    async def initialize(self) -> bool:
        """Initialize the pgvector connection"""
        try:
            # Get tenant context for multi-tenant support
            tenant_id = get_tenant_context()

            # Get the database engine for the current tenant
            self.engine = multi_tenant_manager.get_tenant_engine(tenant_id)

            # Ensure pgvector extension is enabled
            async with self.engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            logger.info(f"Initialized pgvector connection for tenant: {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize pgvector: {e}")
            return False

    async def create_collection(self, dimension: int) -> bool:
        """Create a new collection (table)"""
        try:
            if not self.engine:
                if not await self.initialize():
                    return False

            self.dimension = dimension

            # Create table with vector column
            # Table name is sanitized to be a valid PostgreSQL identifier
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                embedding vector({dimension}),
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """

            # Create index based on distance metric
            if not self.engine:
                return False
            async with self.engine.begin() as conn:  # type: ignore[union-attr]
                await conn.execute(text(create_table_sql))

                # Create index for efficient vector search
                # For cosine similarity, we use the <=> operator
                # For L2 distance, we use the <-> operator
                if self.config.distance_metric == "cosine":
                    # Cosine distance index
                    index_sql = f"""
                    CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
                    ON {self.table_name}
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                elif self.config.distance_metric == "euclidean":
                    # L2 distance index
                    index_sql = f"""
                    CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
                    ON {self.table_name}
                    USING ivfflat (embedding vector_l2_ops)
                    WITH (lists = 100)
                    """
                else:  # dot_product
                    # Inner product index
                    index_sql = f"""
                    CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
                    ON {self.table_name}
                    USING ivfflat (embedding vector_ip_ops)
                    WITH (lists = 100)
                    """

                await conn.execute(text(index_sql))

                # Create GIN index on metadata for efficient filtering
                metadata_index_sql = f"""
                CREATE INDEX IF NOT EXISTS {self.table_name}_metadata_idx
                ON {self.table_name}
                USING GIN (metadata)
                """
                await conn.execute(text(metadata_index_sql))

            logger.info(f"Created/accessed pgvector table: {self.table_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create pgvector collection: {e}")
            return False

    async def delete_collection(self) -> bool:
        """Delete the collection (table)"""
        try:
            if not self.engine:
                return True  # Nothing to delete

            async with self.engine.begin() as conn:
                await conn.execute(text(f"DROP TABLE IF EXISTS {self.table_name}"))

            logger.info(f"Deleted pgvector table: {self.table_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete pgvector collection: {e}")
            return False

    async def add_vectors(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        contents: List[str]
    ) -> bool:
        """Add vectors to the collection"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return False

            # Prepare data for batch insert
            async with self.engine.begin() as conn:
                for doc_id, vector, metadata, content in zip(ids, vectors, metadatas, contents):
                    # Convert vector to PostgreSQL array format
                    vector_str = "[" + ",".join(map(str, vector)) + "]"
                    metadata_json = json.dumps(metadata)

                    # Use CAST() function instead of :: syntax to avoid asyncpg parameter binding issues
                    insert_sql = text(f"""
                        INSERT INTO {self.table_name} (id, embedding, content, metadata)
                        SELECT
                            :id,
                            CAST(:embedding_array AS vector),
                            :content,
                            CAST(:metadata_json AS jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata
                    """)

                    await conn.execute(
                        insert_sql,
                        {
                            "id": doc_id,
                            "embedding_array": vector_str,
                            "content": content,
                            "metadata_json": metadata_json
                        }
                    )

            logger.info(f"Added {len(ids)} vectors to pgvector table")
            return True

        except Exception as e:
            logger.error(f"Failed to add vectors to pgvector: {e}")
            return False

    async def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors by IDs"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return False

            if not ids:
                return True

            async with self.engine.begin() as conn:
                # Use parameterized query for safety
                placeholders = ",".join([f":id_{i}" for i in range(len(ids))])
                delete_sql = text(f"""
                    DELETE FROM {self.table_name}
                    WHERE id IN ({placeholders})
                """)

                params = {f"id_{i}": doc_id for i, doc_id in enumerate(ids)}
                await conn.execute(delete_sql, params)

            logger.info(f"Deleted {len(ids)} vectors from pgvector table")
            return True

        except Exception as e:
            logger.error(f"Failed to delete vectors from pgvector: {e}")
            return False

    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar vectors"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return []

            # Convert query vector to PostgreSQL array format
            vector_str = "[" + ",".join(map(str, query_vector)) + "]"

            # Build WHERE clause for metadata filtering
            where_clause = ""
            params = {"query_vector": vector_str, "limit": limit}

            if filter_dict:
                # Build JSONB filter conditions
                filter_conditions = []
                for i, (key, value) in enumerate(filter_dict.items()):
                    param_key = f"filter_{i}"
                    filter_conditions.append(f"metadata->>'{key}' = :{param_key}")
                    params[param_key] = str(value)

                if filter_conditions:
                    where_clause = "WHERE " + " AND ".join(filter_conditions)

            # Build query based on distance metric
            # Use CAST() instead of :: syntax to avoid asyncpg parameter binding issues
            if self.config.distance_metric == "cosine":
                # Cosine distance (<=> operator)
                distance_expr = "embedding <=> CAST(:query_vector AS vector)"
            elif self.config.distance_metric == "euclidean":
                # L2 distance (<-> operator)
                distance_expr = "embedding <-> CAST(:query_vector AS vector)"
            else:  # dot_product
                # Inner product (negative for similarity, since lower is better)
                distance_expr = "embedding <#> CAST(:query_vector AS vector)"

            search_sql = text(f"""
                SELECT id, content, metadata, {distance_expr} as distance
                FROM {self.table_name}
                {where_clause}
                ORDER BY {distance_expr}
                LIMIT :limit
            """)

            async with self.engine.begin() as conn:
                db_result = await conn.execute(search_sql, params)
                rows = db_result.fetchall()

            # Convert to SearchResult objects
            search_results = []
            for row in rows:
                search_result = SearchResult(
                    id=row.id,
                    content=row.content,
                    metadata=json.loads(row.metadata) if isinstance(row.metadata, str) else row.metadata,
                    score=None,  # Will be calculated from distance
                    distance=float(row.distance)
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search pgvector: {e}")
            return []

    async def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Get vectors by their IDs"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return []

            if not ids:
                return []

            async with self.engine.begin() as conn:
                placeholders = ",".join([f":id_{i}" for i in range(len(ids))])
                select_sql = text(f"""
                    SELECT id, content, metadata
                    FROM {self.table_name}
                    WHERE id IN ({placeholders})
                """)

                params = {f"id_{i}": doc_id for i, doc_id in enumerate(ids)}
                db_result = await conn.execute(select_sql, params)
                rows = db_result.fetchall()

            # Convert to SearchResult objects
            search_results = []
            for row in rows:
                search_result = SearchResult(
                    id=row.id,
                    content=row.content,
                    metadata=json.loads(row.metadata) if isinstance(row.metadata, str) else row.metadata,
                    score=1.0,  # No distance for direct retrieval
                    distance=0.0
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to get vectors by IDs from pgvector: {e}")
            return []

    async def get_all_ids(self, filter_dict: Optional[Dict[str, Any]] = None) -> List[str]:
        """Get all document IDs in the collection"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return []

            where_clause = ""
            params = {}

            if filter_dict:
                filter_conditions = []
                for i, (key, value) in enumerate(filter_dict.items()):
                    param_key = f"filter_{i}"
                    filter_conditions.append(f"metadata->>'{key}' = :{param_key}")
                    params[param_key] = str(value)

                if filter_conditions:
                    where_clause = "WHERE " + " AND ".join(filter_conditions)

            async with self.engine.begin() as conn:
                select_sql = text(f"""
                    SELECT id
                    FROM {self.table_name}
                    {where_clause}
                """)
                db_result = await conn.execute(select_sql, params)
                rows = db_result.fetchall()

            return [row.id for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all IDs from pgvector: {e}")
            return []

    async def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents in the collection"""
        try:
            if not self.engine:
                logger.error("Engine not initialized")
                return 0

            where_clause = ""
            params = {}

            if filter_dict:
                filter_conditions = []
                for i, (key, value) in enumerate(filter_dict.items()):
                    param_key = f"filter_{i}"
                    filter_conditions.append(f"metadata->>'{key}' = :{param_key}")
                    params[param_key] = str(value)

                if filter_conditions:
                    where_clause = "WHERE " + " AND ".join(filter_conditions)

            async with self.engine.begin() as conn:
                count_sql = text(f"""
                    SELECT COUNT(*) as count
                    FROM {self.table_name}
                    {where_clause}
                """)
                db_result = await conn.execute(count_sql, params)
                row = db_result.fetchone()

            return int(row.count) if row and row.count is not None else 0

        except Exception as e:
            logger.error(f"Failed to count documents in pgvector: {e}")
            return 0

    def close(self):
        """Close the database connection"""
        # The engine is managed by MultiTenantSessionManager, so we don't dispose it here
        # Just clear the reference
        self.engine = None
        logger.debug("Closed pgvector connection")

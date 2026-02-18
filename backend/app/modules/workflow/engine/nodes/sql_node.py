"""
SQL node implementation using the BaseNode class.
"""

import logging
from typing import Any, Dict

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.modules.integration.database import db_provider_manager, translate_to_query
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


@inject
class SQLNode(BaseNode):
    """SQL node that can execute SQL queries using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an SQL node with SQL query execution.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with SQL query response and execution steps
        """
        mode = config.get("mode")
        datasource_id = config.get("dataSourceId")
        sql_query = config.get("sqlQuery", "")
        human_query = config.get("humanQuery", "")
        provider_id = config.get("providerId")
        system_prompt = config.get("systemPrompt", "")
        node_parameters = config.get("parameters", {})

        # Validate required fields
        if not datasource_id:
            raise AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)

        if not mode:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

        # Validate mode-specific required fields
        if mode == "humanQuery":
            if not provider_id:
                raise AppException(error_key=ErrorKey.MISSING_PARAMETER)
            if not human_query:
                raise AppException(error_key=ErrorKey.MISSING_PARAMETER)
        elif mode == "sqlQuery":
            if not sql_query:
                raise AppException(error_key=ErrorKey.MISSING_PARAMETER)
        else:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

        # Get database manager
        db_manager = await db_provider_manager.get_database_manager(datasource_id)

        if not db_manager:
            logger.error(
                "Database manager not found for datasource_id: %s", datasource_id
            )
            return {
                "status": 500,
                "data": {
                    "error": (
                        f"Database connection not available for datasource {datasource_id}. "
                        "Please check datasource configuration."
                    )
                },
                "parameters": {
                    "node_parameters": node_parameters,
                    "datasource_id": datasource_id,
                },
            }

        if node_parameters:
            logger.info("Node parameters: %s", node_parameters)

        try:
            # Prepare query based on mode
            if mode == "humanQuery":
                llm_provider = injector.get(LLMProvider)
                llm_model = await llm_provider.get_model(provider_id)

                query_text = human_query
                if node_parameters:
                    param_context = " Use these specific values: "
                    for key, value in node_parameters.items():
                        param_context += f"{key} = {value}, "
                    param_context = param_context.rstrip(", ") + "."
                    query_text = query_text + param_context
                    logger.info(f"Enhanced human query with parameters: {query_text}")

                db_query = await translate_to_query(
                    db_manager,
                    llm_model=llm_model,
                    natural_language_query=query_text,
                    system_prompt=system_prompt,
                )
            else:
                if node_parameters:
                    logger.info(
                        "Node parameters provided but not used in manual SQL mode: %s",
                        node_parameters,
                    )

                db_query = {
                    "formatted_query": sql_query,
                }

            results, error_msg = await db_manager.execute_query(
                db_query["formatted_query"]
            )

            if error_msg:
                logger.error("Database query execution failed: %s", error_msg)
                return {
                    "status": 500,
                    "data": {
                        "error": (f"Database query execution failed: {error_msg}")
                    },
                    "query": db_query,
                    "parameters": {
                        "node_parameters": node_parameters,
                        "datasource_id": datasource_id,
                    },
                }
            else:
                return {
                    "status": 200,
                    "data": results,
                    "query": db_query,
                    "parameters": {
                        "node_parameters": node_parameters,
                        "datasource_id": datasource_id,
                    },
                }

        except Exception as e:
            logger.error("SQL node execution failed: %s", e)
            return {
                "status": 500,
                "data": {
                    "error": (
                        f"SQL node execution failed: {str(e)}. Please check query syntax "
                        "and database connectivity."
                    )
                },
                "parameters": {
                    "node_parameters": node_parameters,
                    "datasource_id": datasource_id,
                },
            }

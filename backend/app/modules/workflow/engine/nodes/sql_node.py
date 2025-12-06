"""
SQL node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from injector import inject
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.integration.database import translate_to_query, db_provider_manager
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
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
        provider_id = config.get("providerId")
        datasource_id = config.get("dataSourceId")
        query = config.get("query", "What information do you have?")
        system_prompt = config.get("systemPrompt", "")
        node_parameters = config.get("parameters", {})
        if not provider_id:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)
        if not datasource_id:
            raise AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)

        llm_provider = injector.get(LLMProvider)
        llm_model = await llm_provider.get_model(provider_id)
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
            # Inject node parameters into the query if they exist
            if node_parameters:
                # Create a parameter context string to append to the query
                param_context = " Use these specific values: "
                for key, value in node_parameters.items():
                    param_context += f"{key} = {value}, "
                param_context = param_context.rstrip(", ") + "."
                query = query + param_context
                logger.info(f"Enhanced query with parameters: {query}")
            
            db_query = await translate_to_query(
                db_manager,
                llm_model=llm_model,
                natural_language_query=query,
                system_prompt=system_prompt,
            )

            results, error_msg = await db_manager.execute_query(
                db_query["formatted_query"]
            )

            if error_msg:
                logger.error(
                    "Database query execution failed: %s", error_msg
                )
                return {
                    "status": 500,
                    "data": {
                        "error": (
                            f"Database query execution failed: {error_msg}"
                        )
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
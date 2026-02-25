"""
OpenAPI node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from injector import inject
from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.data.utils.file_extractor import FileTextExtractor


logger = logging.getLogger(__name__)


@inject
class OpenAPINode(BaseNode):
    """OpenAPI node that answers questions about OpenAPI specifications using LLM"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an OpenAPI node by answering questions about the specification.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with the answer to the user's query about the specification
        """
        provider_id, query, server_file_path, original_file_name, server_file_url = (
            config.get("providerId"),
            config.get("query"),
            config.get("serverFilePath"),
            config.get("originalFileName"),
            config.get("serverFileUrl")
        )

        if not provider_id:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

        if not query:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

        if not server_file_path and not server_file_url:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

        try:
            extractor = FileTextExtractor()

            # If file_url is present, download and extract from bytes
            if server_file_url:
                from app.dependencies.injector import injector
                from app.services.file_manager import FileManagerService
                file_manager_service = injector.get(FileManagerService)
                file_content = await file_manager_service.get_file_content_from_url(server_file_url)

                # Use original_file_name if available, otherwise try to infer from URL
                filename = original_file_name or server_file_url.split("/")[-1]
                spec_content = extractor.extract_from_bytes(filename=filename, content=file_content)
            else:
                # Fallback to existing path-based extraction
                spec_content = extractor.extract(path=server_file_path)

            if not spec_content:
                file_source = server_file_url or server_file_path
                logger.error(
                    "Failed to load OpenAPI specification from: %s",
                    file_source
                )
                return {
                    "status": 500,
                    "error": (
                        f"Failed to load OpenAPI specification. "
                        "Please check file path/URL and format."
                    ),
                }

            # Get LLM provider
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(provider_id)

            # Use LLM to answer the question about the spec
            answer = await self._answer_query_about_spec(
                llm_model,
                query,
                spec_content
            )

            return {
                "status": 200,
                "answer": answer,
                "query": query
            }

        except Exception as e:
            logger.error("OpenAPI node execution failed: %s", e, exc_info=True)
            return {
                "status": 500,
                "error": f"OpenAPI node execution failed: {str(e)}"
            }

    async def _answer_query_about_spec(
        self,
        llm_model,
        query: str,
        spec_content: str
    ) -> str:
        """
        Use LLM to answer a question about the OpenAPI specification.

        Args:
            llm_model: LLM model instance
            query: Natural language question from user
            spec_content: Raw OpenAPI specification content

        Returns:
            String answer to the user's question
        """
        try:
            # Construct prompt for the LLM
            prompt = f"""Answer the user's question about the following OpenAPI specification.

OpenAPI Specification:
{spec_content}

User Question: {query}

Provide a clear, concise answer to the user's question based on the specification above. If the information is not available in the specification, say so.

Answer:"""

            # Call LLM to get the answer
            response = await llm_model.ainvoke(prompt)

            # Extract answer from response
            answer = response.content if hasattr(
                response, 'content') else str(response)

            logger.info(f"Generated answer for query: {query}")

            return answer.strip()

        except Exception as e:
            logger.error(
                f"Error answering query about spec: {str(e)}", exc_info=True)
            return f"Error processing query: {str(e)}"

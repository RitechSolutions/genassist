"""
API tool node implementation using the BaseNode class.
"""

import json
import logging
from typing import Dict, Any
import aiohttp
from app.modules.workflow.engine import BaseNode


logger = logging.getLogger(__name__)


class ApiToolNode(BaseNode):
    """API tool node that makes HTTP requests using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an API tool node with dynamic parameter replacement.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with API response data
        """

        # Get configuration values (already resolved by BaseNode)
        method = config.get("method", "GET")
        endpoint = config.get("endpoint", "")
        headers = config.get("headers", {})
        parameters = config.get("parameters", {})
        request_body: str | dict = config.get("requestBody", {})

        try:
            # Make the API call
            response = await self._make_api_call(method, endpoint, headers, parameters, request_body)
            logger.info(f"API Response: {response}")
            return response

        except (aiohttp.ClientError, json.JSONDecodeError, ValueError) as e:
            error_msg = f"Error processing API tool: {str(e)}"
            logger.error(error_msg)
            return {
                "status": 500,
                "data": {"error": error_msg},
                "headers": {}
            }

    async def _make_api_call(self, method: str, endpoint: str, headers: Dict[str, str],
                             parameters: Dict[str, Any], request_body: str | dict) -> Dict[str, Any]:
        """Make an API call with the given parameters"""
        try:
            # Add https:// if no schema is provided
            if not endpoint.startswith(('http://', 'https://')):
                endpoint = f'https://{endpoint}'
                logger.info(f"Added https:// schema to endpoint: {endpoint}")

            method = method.upper()

            # Prepare request data
            json_data = None
            if request_body:
                if isinstance(request_body, str):
                    json_data = json.loads(request_body)
                else:
                    json_data = request_body

            # Use aiohttp session for connection pooling with timeout
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Make the request based on HTTP method
                if method == "GET":
                    async with session.get(endpoint, headers=headers, params=parameters) as response:
                        return await self._process_response(response, method)
                elif method == "POST":
                    async with session.post(endpoint, headers=headers, params=parameters, json=json_data) as response:
                        return await self._process_response(response, method)
                elif method == "PUT":
                    async with session.put(endpoint, headers=headers, params=parameters, json=json_data) as response:
                        return await self._process_response(response, method)
                elif method == "DELETE":
                    async with session.delete(endpoint, headers=headers, params=parameters, json=json_data) as response:
                        return await self._process_response(response, method)
                elif method == "PATCH":
                    async with session.patch(endpoint, headers=headers, params=parameters, json=json_data) as response:
                        return await self._process_response(response, method)
                elif method == "HEAD":
                    async with session.head(endpoint, headers=headers, params=parameters) as response:
                        return await self._process_response(response, method)
                elif method == "OPTIONS":
                    async with session.options(endpoint, headers=headers, params=parameters) as response:
                        return await self._process_response(response, method)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

        except (aiohttp.ClientError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"API call failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
            }

    async def _process_response(self, response: aiohttp.ClientResponse, method: str) -> Dict[str, Any]:
        """Process the aiohttp response and return standardized format"""
        try:
            # Check for HTTP errors
            response.raise_for_status()

            # Get response data
            data = None
            if method not in ["HEAD", "OPTIONS"]:
                try:
                    data = await response.json()
                    logger.info("Response: %s", data)
                except aiohttp.ContentTypeError:
                    # If response is not JSON, get as text
                    data = await response.text()
                    logger.info("Response (text): %s", data)

            return {
                "status": response.status,
                "data": data,
                "headers": dict(response.headers)
            }

        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error {e.status}: {e.message}")
            return {
                "status": e.status,
                "data": {"error": e.message},
                "headers": dict(response.headers) if hasattr(response, 'headers') else {}
            }

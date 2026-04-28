"""
External agent node — calls an external agent API and normalises the response
to the standard agent output format {"message": str, "steps": list}.
"""

import base64
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

from app.modules.workflow.engine import BaseNode
from app.modules.workflow.utils import execute_python_code

logger = logging.getLogger(__name__)


class ExternalAgentNode(BaseNode):
    """Calls an external agent API and maps its response to the standard agent format."""

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        endpoint: str = config.get("endpoint", "")
        method: str = config.get("method", "POST").upper()
        headers: Dict[str, str] = dict(config.get("headers") or {})
        request_body: str = config.get("requestBody", "")
        auth_type: str = config.get("authType", "none")
        auth_token: str = config.get("authToken", "")
        auth_header: str = config.get("authHeader", "Authorization")
        auth_username: str = config.get("authUsername", "")
        auth_password: str = config.get("authPassword", "")
        message_field: str = config.get("messageField", "message")
        steps_field: str = config.get("stepsField", "steps")
        mapping_script: str = config.get("mappingScript", "")

        self.set_node_input({
            "endpoint": endpoint,
            "method": method,
            "authType": auth_type,
            "messageField": message_field,
            "stepsField": steps_field,
            "hasMappingScript": bool(mapping_script),
        })

        if not endpoint:
            return {"error": "No endpoint configured for external agent node"}

        headers = self._build_auth_headers(
            headers, auth_type, auth_token, auth_header, auth_username, auth_password
        )

        try:
            api_response = await self._call_endpoint(method, endpoint, headers, request_body)
        except Exception as e:
            logger.error("External agent HTTP call failed: %s", e)
            return {"error": f"HTTP call failed: {e}"}

        if "error" in api_response and api_response.get("status", 200) >= 400:
            return {"error": api_response.get("data", {}).get("error", "HTTP error")}

        response_data = api_response.get("data", api_response)

        if mapping_script:
            return await self._apply_mapping_script(mapping_script, response_data)

        return self._apply_field_mapping(response_data, message_field, steps_field)

    # ------------------------------------------------------------------ #
    # Auth helpers                                                          #
    # ------------------------------------------------------------------ #

    def _build_auth_headers(
        self,
        headers: Dict[str, str],
        auth_type: str,
        auth_token: str,
        auth_header: str,
        auth_username: str,
        auth_password: str,
    ) -> Dict[str, str]:
        result = dict(headers)
        if auth_type == "bearer" and auth_token:
            result["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "api_key" and auth_token:
            result[auth_header or "Authorization"] = auth_token
        elif auth_type == "basic" and auth_username:
            credentials = base64.b64encode(
                f"{auth_username}:{auth_password}".encode()
            ).decode()
            result["Authorization"] = f"Basic {credentials}"
        return result

    # ------------------------------------------------------------------ #
    # HTTP call                                                             #
    # ------------------------------------------------------------------ #

    async def _call_endpoint(
        self, method: str, endpoint: str, headers: Dict[str, str], request_body: str
    ) -> Dict[str, Any]:
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"https://{endpoint}"

        json_data: Optional[Any] = None
        if request_body and method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                json_data = json.loads(request_body) if isinstance(request_body, str) else request_body
            except json.JSONDecodeError:
                logger.warning("Request body is not valid JSON; sending as plain text")

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            request_kwargs: Dict[str, Any] = {"headers": headers}
            if json_data is not None:
                request_kwargs["json"] = json_data

            method_map = {
                "GET": session.get,
                "POST": session.post,
                "PUT": session.put,
                "DELETE": session.delete,
                "PATCH": session.patch,
            }
            http_fn = method_map.get(method)
            if not http_fn:
                raise ValueError(f"Unsupported HTTP method: {method}")

            async with http_fn(endpoint, **request_kwargs) as response:
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    data = await response.text()

                if response.status >= 400:
                    return {"status": response.status, "data": {"error": data}}

                return {"status": response.status, "data": data}

    # ------------------------------------------------------------------ #
    # Response mapping                                                      #
    # ------------------------------------------------------------------ #

    async def _apply_mapping_script(
        self, script: str, response_data: Any
    ) -> Dict[str, Any]:
        try:
            result = await execute_python_code(script, params={"response": response_data})
            if not isinstance(result, dict) or "message" not in result:
                logger.warning("Mapping script did not return expected format; wrapping output")
                return {"message": str(result), "steps": []}
            result.setdefault("steps", [])
            return result
        except Exception as e:
            logger.error("Mapping script error: %s", e)
            return {"error": f"Mapping script error: {e}"}

    def _apply_field_mapping(
        self, data: Any, message_field: str, steps_field: str
    ) -> Dict[str, Any]:
        message = self._get_nested(data, message_field)
        if message is None:
            # Fall back to the raw data as message if no field matched
            message = str(data) if data is not None else ""
        steps = self._get_nested(data, steps_field) or []
        if not isinstance(steps, list):
            steps = [steps]
        return {"message": str(message), "steps": steps}

    @staticmethod
    def _get_nested(data: Any, path: str) -> Any:
        """Resolve a dot-notation path against a nested dict/list structure."""
        if not path or data is None:
            return None
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
from typing import Dict, Any, List, Union
import json
import logging
import aiohttp
from app.core.utils.string_utils import replace_template_vars
from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)

class ApiToolNodeProcessor(NodeProcessor):
    """Processor for API tool nodes"""
    


    async def _make_api_call(self, method: str, endpoint: str, headers: Dict[str, str], 
                           parameters: Dict[str, Any], request_body: str) -> Dict[str, Any]:
        """Make an API call with the given parameters"""
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(endpoint, headers=headers, params=parameters) as response:
                        response.raise_for_status()
                        return {
                            "status": response.status,
                            "data": await response.json(),
                            # "headers": dict(response.headers)
                        }
                elif method.upper() == "POST":
                    async with session.post(endpoint, headers=headers, json=json.loads(request_body) if request_body else None) as response:
                        response.raise_for_status()
                        return {
                            "status": response.status,
                            "data": await response.json(),
                            # "headers": dict(response.headers)
                        }
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                # "headers": {}
            }
    
    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process an API tool node with dynamic parameter replacement"""
        # Get base configuration
        node_config = self.get_node_config()
        
        # Get input data
        edge_inputs = await self.get_process_input(input_data)
        user_metadata = self.get_state().get_session_metadata()

        # Merge all inputs
        input_object = {
            **edge_inputs,  # Edge-based inputs
            **user_metadata  # Session data
        }
        self.set_input(input_object)
        
        node_config = replace_template_vars(json.dumps(node_config), input_object)
        node_config = json.loads(node_config)
        method = node_config.get("method", "GET")
        endpoint = node_config.get("endpoint", "")
        headers = node_config.get("headers", {})
        parameters = node_config.get("parameters", {})
        request_body = node_config.get("requestBody", "")
        
        if not endpoint:
            error_msg = "No endpoint specified for API tool"
            logger.error(error_msg)
            self.output = {
                "status": 400,
                "data": {"error": error_msg},
                "headers": {}
            }
            return self.output
        
        try:
            # Process dynamic values in all components

            # Log the processed values for debugging
            logger.debug(f"Processed API call configuration:")
            logger.debug(f"Endpoint: {endpoint}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Parameters: {parameters}")
            logger.debug(f"Request body: {request_body}")
            
            # Make the API call
            # loop = asyncio.get_event_loop()
            # response = loop.run_until_complete(
            #     self._make_api_call(method, endpoint, headers, parameters, request_body)
            # )
            response = await self._make_api_call(method, endpoint, headers, parameters, request_body)
            self.save_output(response)
            return response
        except Exception as e:
            error_msg = f"Error processing API tool: {str(e)}"
            logger.error(error_msg)
            self.output = {
                "status": 500,
                "data": {"error": error_msg},
                "headers": {}
            }
            return self.output


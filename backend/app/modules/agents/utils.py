import json
from typing import Dict, Any, List

def generate_python_function_template(parameters_schema: Dict[str, Any]) -> str:
    """
    Generate a Python function template based on the parameters schema.
    
    Args:
        parameters_schema: A dictionary with parameter definitions
        
    Returns:
        A Python code template as a string
    """
    # Start with the default template
    template_lines = [
        "# Generated Python function template",
        "# Access parameters via the 'params' dictionary",
        "# Store your result in the 'result' variable",
        "",
        "# Import any additional libraries you need",
        "# import json",
        "# import requests",
        "# import datetime",
        "",
        "try:",
        "    # Extract parameters with type validation"
    ]
    
    # Add parameter extraction code based on schema
    if not parameters_schema:
        template_lines.append("    # No parameters defined in schema")
        template_lines.append("    pass")
    else:
        for param_name, param_info in parameters_schema.items():
            param_type = param_info.get("type", "string")
            description = param_info.get("description", f"Parameter: {param_name}")
            
            # Add comment with parameter description
            template_lines.append(f"    # {description}")
            
            # Generate code to extract and validate parameter based on type
            if param_type == "string":
                template_lines.append(f"    {param_name} = params.get('{param_name}', '')")
                template_lines.append(f"    if not isinstance({param_name}, str):")
                template_lines.append(f"        {param_name} = str({param_name}) if {param_name} is not None else ''")
            elif param_type == "number" or param_type == "integer":
                default = "0"
                convert_func = "float" if param_type == "number" else "int"
                template_lines.append(f"    {param_name} = params.get('{param_name}', {default})")
                template_lines.append(f"    if {param_name} is not None:")
                template_lines.append(f"        try:")
                template_lines.append(f"            {param_name} = {convert_func}({param_name})")
                template_lines.append(f"        except (ValueError, TypeError):")
                template_lines.append(f"            {param_name} = {default}")
                template_lines.append(f"    else:")
                template_lines.append(f"        {param_name} = {default}")
            elif param_type == "boolean":
                template_lines.append(f"    {param_name} = params.get('{param_name}', False)")
                template_lines.append(f"    {param_name} = bool({param_name})")
            elif param_type == "array":
                template_lines.append(f"    {param_name} = params.get('{param_name}', [])")
                template_lines.append(f"    if not isinstance({param_name}, list):")
                template_lines.append(f"        {param_name} = [{param_name}] if {param_name} is not None else []")
            elif param_type == "object":
                template_lines.append(f"    {param_name} = params.get('{param_name}', {{}})")
                template_lines.append(f"    if not isinstance({param_name}, dict):")
                template_lines.append(f"        {param_name} = {{}} if {param_name} is None else {param_name}")
            else:
                # Default to string for unknown types
                template_lines.append(f"    {param_name} = params.get('{param_name}', None)")
            
            template_lines.append("")  # Add blank line between parameters
    
    # Add example usage section for the extracted parameters
    template_lines.append("    # Your code logic here - example using the parameters:")
    if parameters_schema:
        example_lines = ["    result = {"]
        for param_name in parameters_schema.keys():
            example_lines.append(f"        '{param_name}': {param_name},")
        example_lines.append("    }")
        template_lines.extend(example_lines)
    else:
        template_lines.append("    result = 'Successfully executed function with no parameters'")
    
    # Add exception handling
    template_lines.extend([
        "",
        "except Exception as e:",
        "    # Handle any errors",
        "    import traceback",
        "    result = f\"Error processing parameters: {str(e)}\\n{traceback.format_exc()}\"",
        ""
    ])
    
    return "\n".join(template_lines)

def validate_params_against_schema(params: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and enhance parameters against a schema.
    This is a simplified version of the Agent._validate_params_against_schema method.
    
    Args:
        params: The parameters to validate
        schema: The parameters schema definition
        
    Returns:
        The validated and enhanced parameters
    """
    if not schema:
        return params
        
    result_params = {}
    
    # Apply defaults and type conversions based on schema
    for param_name, param_info in schema.items():
        param_type = param_info.get("type", "string")
        
        # If parameter is provided, process it
        if param_name in params:
            value = params[param_name]
            
            # Apply type conversion if needed
            if param_type == "string" and not isinstance(value, str):
                result_params[param_name] = str(value) if value is not None else ""
            elif param_type == "number" and not isinstance(value, (int, float)):
                try:
                    result_params[param_name] = float(value)
                except (ValueError, TypeError):
                    result_params[param_name] = 0
            elif param_type == "integer" and not isinstance(value, int):
                try:
                    result_params[param_name] = int(float(value))
                except (ValueError, TypeError):
                    result_params[param_name] = 0
            elif param_type == "boolean" and not isinstance(value, bool):
                result_params[param_name] = bool(value)
            elif param_type == "array" and not isinstance(value, list):
                result_params[param_name] = [value] if value is not None else []
            elif param_type == "object" and not isinstance(value, dict):
                result_params[param_name] = {} if value is None else value
            else:
                result_params[param_name] = value
        else:
            # Parameter not provided, use default based on type
            if param_type == "string":
                result_params[param_name] = ""
            elif param_type in ["number", "integer"]:
                result_params[param_name] = 0
            elif param_type == "boolean":
                result_params[param_name] = False
            elif param_type == "array":
                result_params[param_name] = []
            elif param_type == "object":
                result_params[param_name] = {}
            else:
                result_params[param_name] = None
                
    # Include any extra parameters not in the schema
    for param_name, value in params.items():
        if param_name not in result_params:
            result_params[param_name] = value
            
    return result_params


def create_tool_description(tool: Dict[str, Any], index: int) -> str:
        """Create a description for a specific tool"""
        # Basic information for all tools
        description = [
            f"Tool {index+1}: {tool['name']}",
            f"Type: {tool['type'].replace('Node', '')}",
            f"Description: {tool['description']}"
        ]
        
        # Add tool-specific details
        if tool["type"] == "apiToolNode":
            description.extend([
                f"API Endpoint: {tool['endpoint']}",
                f"Method: {tool['method']}"
            ])
        elif tool["type"] in ["knowledgeToolNode", "knowledgeBaseNode"]:
            description.append(f"Knowledge bases: {len(tool.get('selectedBases', []))} selected")
        
        # Add input parameters
        input_params = []
        for param_name, param_info in tool.get('inputSchema', {}).items():
            required = "required" if param_info.get('required', False) else "optional"
            param_desc = param_info.get('description', '')
            param_type = param_info.get('type', 'any')
            input_params.append(f"  - {param_name}: {param_type} ({required}){' - ' + param_desc if param_desc else ''}")
        
        if input_params:
            description.append("Required Parameters:")
            description.extend(input_params)
        
        # Add output information if available
        output_params = []
        for param_name, param_info in tool.get('outputSchema', {}).items():
            output_params.append(f"  - {param_name}: {param_info.get('type', 'any')}")
        
        if output_params:
            description.append("Output Schema:")
            description.extend(output_params)
        
        return "\n".join(description)
    


def create_tool_selection_prompt(user_input: str, tools: List[Dict[str, Any]]) -> str:
        """Create a prompt for the agent to select appropriate tools and extract required parameters"""
        # Create descriptions for each tool
        tool_descriptions = [create_tool_description(tool, i) for i, tool in enumerate(tools)]
        tools_description = "\n\n".join(tool_descriptions)
        
        return f"""You are an AI assistant that can help users by selecting and using appropriate tools.
                Available tools:

                {tools_description}

                User request: {user_input}

                Please analyze the user's request and determine which tool(s) would be most appropriate to use.
                For each selected tool, extract the required parameters from the user's request.

                Respond in JSON format with the following structure:
                {{
                    "selected_tools": [
                        {{
                            "tool_index": <index of the tool (1-based)>,
                            "reason": "<explanation of why this tool is appropriate>",
                            "extracted_parameters": {{
                                "<parameter_name>": <extracted_value>,
                                ...
                            }},
                            "missing_parameters": [
                                "<list of required parameters that couldn't be extracted>"
                            ]
                        }}
                    ],
                    "should_execute": <true/false>,
                    "explanation": "<explanation of your decision>"
                }}

                Important:
                1. Only select tools where you can extract all required parameters from the user's request
                2. If a tool requires parameters that aren't in the user's request, list them in missing_parameters
                3. For each selected tool, provide the extracted parameters in the format expected by the tool's input schema
                4. If no tool can be used with the available information, set should_execute to false and explain why
                5. For knowledge tools, you should extract a 'query' parameter from the user's request
                6. For API tools, extract parameters matching the input schema or API endpoint requirements"""


def create_direct_response_prompt(prompt: str) -> str:
    return f"""You are a helpful AI assistant. Please provide a clear and helpful response to the following user request:

    User request: {prompt}

    Please provide a direct and informative response that addresses the user's request."""
    
def create_json_human_prompt(prompt: str, results: Dict[str, Any]) -> str:
    return f"""You are a helpful AI assistant. Please format the following tool execution results into a clear, natural response for the user.

    Original user request: {prompt}

    Tool execution results:
    {json.dumps(results, indent=2)}

    Please provide a natural, conversational response that incorporates the results in a helpful way. Do not mention the tools or technical details unless necessary. Focus on answering the user's request in a clear and helpful manner."""
    
def map_tool_to_schema(node: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of available tools from connected nodes"""
        node_type = node.get("type")
        tool_data = node.get("data", {})
            
        # Skip non-tool nodes
   
                    
        # Create a standardized tool representation
        tool = {
            "node_id": node.get("id"),
            "type": node_type,
            "name": tool_data.get("name", f"Unnamed {node_type.replace('Node', '')}"),
            "description": tool_data.get("description", ""),
            "inputSchema": tool_data.get("inputSchema", {}),
            "outputSchema": tool_data.get("outputSchema", {})
        }
        if node_type not in ["apiToolNode", "knowledgeToolNode", "knowledgeBaseNode"]:
            return tool
        # Add tool-specific properties
        if node_type == "apiToolNode":
            tool.update({
                "endpoint": tool_data.get("endpoint", ""),
                "method": tool_data.get("method", "GET"),
                "parameters": tool_data.get("parameters", {})
            })
        elif node_type in ["knowledgeToolNode", "knowledgeBaseNode"]:
            tool.update({
                "selectedBases": tool_data.get("selectedBases", []),
                "query_type": "semantic search"
            })
        
            
        return tool
    
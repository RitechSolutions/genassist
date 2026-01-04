from typing import List, Dict, Any, Optional
import logging
import json
import re

from app.modules.workflow.agents.base_tool import BaseTool

logger = logging.getLogger(__name__)


# ==================== PARAMETER VALIDATION UTILITIES ====================

def validate_tool_parameters(tool: BaseTool, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and process tool parameters"""
    if not hasattr(tool, 'parameters') or not tool.parameters:
        return args
    
    validated_args = {}
    errors = []
    
    for param_name, param_info in tool.parameters.items():
        required = param_info.get('required', False)
        param_type = param_info.get('type', 'any')
        default = param_info.get('default', None)
        
        if param_name in args:
            value = convert_parameter_type(args[param_name], param_type, param_name, errors)
            if value is not None:
                validated_args[param_name] = value
        elif required:
            errors.append(f"Required parameter '{param_name}' is missing")
        elif default is not None:
            validated_args[param_name] = default
    
    if errors:
        raise ValueError(f"Parameter validation errors: {'; '.join(errors)}")
    
    return validated_args


def convert_parameter_type(value: Any, param_type: str, param_name: str, errors: List[str]) -> Any:
    """Convert parameter to the expected type"""
    try:
        if param_type == 'string' and not isinstance(value, str):
            return str(value)
        elif param_type in ['number', 'float'] and not isinstance(value, (int, float)):
            return float(value)
        elif param_type == 'integer' and not isinstance(value, int):
            return int(value)
        elif param_type == 'boolean' and not isinstance(value, bool):
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            else:
                return bool(value)
        return value
    except (ValueError, TypeError):
        errors.append(f"Parameter '{param_name}' must be a {param_type}")
        return None


# ==================== TOOL FORMATTING UTILITIES ====================

def format_tool_parameters(tool: BaseTool) -> str:
    """Format tool parameters for display in prompts"""
    if not hasattr(tool, 'parameters') or not tool.parameters:
        return "No parameters required"
    
    param_descriptions = []
    for param_name, param_info in tool.parameters.items():
        try:
            param_type = param_info.get('type', 'any')
            param_desc = param_info.get('description', '')
            required = param_info.get('required', False)
            default = param_info.get('default', None)
            
            param_line = f"    - {param_name} ({param_type})"
            if required:
                param_line += " [REQUIRED]"
            if default is not None:
                param_line += f" [default: {default}]"
            if param_desc:
                param_line += f" - {param_desc}"
            
            param_descriptions.append(param_line)
        except Exception as e:
            logger.error(f"Error formatting tool parameters: {str(e)}")
            logger.error(f"Tool parameters: {param_info}")
    return "\n".join(param_descriptions)


def create_tool_descriptions(tools: List[BaseTool]) -> List[str]:
    """Create detailed tool descriptions for prompt generation"""
    tool_descriptions = []
    for tool in tools:
        tool_desc = f"- {tool.name}: {tool.description}"
        param_info = format_tool_parameters(tool)
        
        if param_info != "No parameters required":
            tool_desc += f"\n  Parameters:\n{param_info}"
        else:
            tool_desc += "\n  Parameters: None"
        
        tool_descriptions.append(tool_desc)
    return tool_descriptions


def get_tool_parameter_help(tool: BaseTool, tool_name: str) -> str:
    """Get parameter help for a specific tool"""
    if not tool:
        return f"Tool '{tool_name}' not found"
    
    param_info = format_tool_parameters(tool)
    return f"Parameters for {tool_name}:\n{param_info}"


# ==================== TOOL EXECUTION UTILITIES ====================

async def execute_tool_safely(tool: BaseTool, tool_input: Dict[str, Any], tool_name: str) -> str:
    """Execute a tool with proper error handling and parameter validation"""
    try:
        validated_args = validate_tool_parameters(tool, tool_input)
        result = await tool.invoke(**validated_args)
        return str(result)
    except ValueError as e:
        logger.error(f"Parameter validation failed for tool {tool_name}: {str(e)}")
        return f"Parameter validation failed: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return f"Tool execution failed: {str(e)}"


def create_tool_execution_info(iteration: int, tool_name: str, tool_input: Dict[str, Any], 
                               result: str, reasoning: str = "") -> Dict[str, Any]:
    """Create standardized tool execution information"""
    return {
        "iteration": iteration,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "result": result,
        "reasoning": reasoning
    }


# ==================== ERROR HANDLING UTILITIES ====================

def create_error_response(error_msg: str, agent_type: str, **kwargs) -> Dict[str, Any]:
    """Create standardized error response"""
    response = {
        "status": "error",
        "error": error_msg,
        "agent_type": agent_type
    }
    response.update(kwargs)
    return response


def create_success_response(result: str, agent_type: str, **kwargs) -> Dict[str, Any]:
    """Create standardized success response"""
    response = {
        "status": "success",
        "response": result,
        "agent_type": agent_type
    }
    response.update(kwargs)
    return response


def handle_parameter_validation_error(error: ValueError, tool_name: str, tool: BaseTool, 
                                       agent_type: str, **kwargs) -> Dict[str, Any]:
    """Handle parameter validation errors in a standardized way"""
    error_msg = f"Parameter validation failed for tool '{tool_name}': {str(error)}"
    param_help = get_tool_parameter_help(tool, tool_name)
    
    response = create_error_response(error_msg, agent_type, **kwargs)
    response["parameter_help"] = param_help
    return response


def handle_tool_execution_error(error: Exception, tool_name: str, agent_type: str, **kwargs) -> Dict[str, Any]:
    """Handle tool execution errors in a standardized way"""
    error_msg = f"Tool execution failed: {str(error)}"
    return create_error_response(error_msg, agent_type, tool_name=tool_name, **kwargs)


# ==================== TOOL MANAGEMENT UTILITIES ====================

def get_available_tools_info(tools: List[BaseTool]) -> List[Dict[str, str]]:
    """Get list of available tools with their descriptions and parameter info"""
    if not tools:
        return []
    
    tools_info = []
    for tool in tools:
        tool_info = {
            "name": tool.name,
            "description": tool.description,
            "parameters": getattr(tool, 'parameters', {}),
            "parameter_summary": format_tool_parameters(tool)
        }
        tools_info.append(tool_info)
    
    return tools_info


def get_tool_schemas(tools: List[BaseTool]) -> Dict[str, Dict]:
    """Get comprehensive schemas for all available tools including parameters"""
    if not tools:
        return {}
    
    schemas = {}
    for tool in tools:
        schema = {
            "name": tool.name,
            "description": tool.description,
            "parameters": getattr(tool, 'parameters', {}),
            "parameter_details": format_tool_parameters(tool)
        }
        
        if hasattr(tool, 'node_id'):
            schema["node_id"] = tool.node_id
        
        schemas[tool.name] = schema
    
    return schemas


def get_tool_parameter_info(tool_map: Dict[str, BaseTool], tool_name: str) -> Dict[str, Any]:
    """Get detailed parameter information for a specific tool"""
    if tool_name not in tool_map:
        return {
            "status": "error",
            "error": f"Tool '{tool_name}' not found",
            "available_tools": list(tool_map.keys())
        }
    
    tool = tool_map[tool_name]
    
    return {
        "status": "success",
        "tool_name": tool_name,
        "description": tool.description,
        "parameters": getattr(tool, 'parameters', {}),
        "parameter_help": get_tool_parameter_help(tool, tool_name),
        "has_required_params": any(
            param.get('required', False) 
            for param in getattr(tool, 'parameters', {}).values() 
            if isinstance(param, dict)
        )
    }


def add_tool_to_agent(tools: List[BaseTool], tool_map: Dict[str, BaseTool], tool: BaseTool):
    """Add a new tool to the agent's tool list and map"""
    tools.append(tool)
    tool_map[tool.name] = tool


def remove_tool_from_agent(tools: List[BaseTool], tool_map: Dict[str, BaseTool], tool_name: str) -> bool:
    """Remove a tool from the agent's tool list and map"""
    original_count = len(tools)
    tools[:] = [tool for tool in tools if tool.name != tool_name]
    
    if len(tools) < original_count:
        if tool_name in tool_map:
            del tool_map[tool_name]
        return True
    return False


# ==================== JSON PARSING UTILITIES ====================

def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON formatted response"""
    try:
        response_clean = response.strip()
        json_start = response_clean.find('{')
        json_end = response_clean.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = response_clean[json_start:json_end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    return None


def extract_direct_response(response: str) -> Optional[str]:
    """Extract direct response from JSON format"""
    parsed_response = parse_json_response(response)
    if parsed_response and parsed_response.get("action") == "direct_response":
        return parsed_response.get("response", "")
    return response


# ==================== REACT PARSING UTILITIES ====================

def extract_final_answer(text: str) -> Optional[str]:
    """Extract final answer from ReAct response"""
    final_match = re.search(r'Final Answer:\s*(.+)', text, re.DOTALL)
    if not final_match:
        return None
    
    answer = final_match.group(1).strip()
    
    # Clean up markdown formatting that might be included
    # Remove trailing ``` or ``` markdown blocks
    if answer.endswith('```'):
        answer = answer[:-3].strip()
    
    # Remove any trailing newlines or whitespace
    answer = answer.strip()
    
    return answer if answer else None


def extract_thought(text: str) -> str:
    """Extract thought from ReAct response"""
    thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|$)', text, re.DOTALL)
    return thought_match.group(1).strip() if thought_match else ""


def parse_react_action(text: str) -> Dict[str, Any]:
    """Parse action from ReAct response format"""
    action_match = re.search(r'Action:\s*(.+)', text)
    action_input_match = re.search(r'Action Input:\s*(.+)', text, re.DOTALL)
    
    action = action_match.group(1).strip() if action_match else "none"
    action_input = {}
    
    if action_input_match:
        input_text = action_input_match.group(1).strip()
        try:
            action_input = json.loads(input_text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse action input as JSON: {input_text}")
            action_input = {"input": input_text}
    
    return {"action": action, "action_input": action_input} 




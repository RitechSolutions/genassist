from typing import List


# ==================== REACT AGENT PROMPTS ====================

def create_react_tools_available_prompt(base_prompt: str, tool_descriptions: List[str]) -> str:
    """Create ReAct system prompt when tools are available"""
    react_guidance = f"""

AVAILABLE TOOLS:
{chr(10).join(tool_descriptions)}

REACT REASONING PATTERN:
Follow this exact reasoning pattern for each step:

1. **Thought**: Think about what you need to do and what information you have
2. **Action**: Choose a tool to use, or "none" if no tool is needed
3. **Action Input**: Provide the parameters for the tool in JSON format
4. **Observation**: [This will be filled automatically with tool results]

Continue this pattern until you can provide a Final Answer.

RESPONSE FORMAT:
Use this exact format for each reasoning step:

```
Thought: [Your reasoning about what to do next]
Action: [tool_name or "none"]
Action Input: {{"param1": "value1", "param2": "value2"}}
```

When you have enough information to answer the user's question, provide:
```
Final Answer: [Your complete response to the user]
```

GUIDELINES:
- Always include your reasoning in the Thought section
- Pay attention to required parameters - all required parameters must be provided
- Use tools when they can provide more accurate or up-to-date information
- If a tool fails, analyze the error and try a different approach
- Provide clear and comprehensive Final Answers
"""
    return base_prompt + react_guidance


def create_react_no_tools_prompt(base_prompt: str) -> str:
    """Create ReAct system prompt when no tools are available"""
    no_tools_guidance = """

NO TOOLS AVAILABLE:
- You do not have access to any external tools
- Use the ReAct pattern but with Action: none for all steps
- Provide reasoning in Thought sections and conclude with Final Answer

RESPONSE FORMAT:
```
Thought: [Your reasoning based on available knowledge]
Action: none
Action Input: {}
Final Answer: [Your response based on available knowledge]
```
"""
    return base_prompt + no_tools_guidance


def create_react_query_prompt(enhanced_prompt: str, context: str, query: str) -> str:
    """Create the main query prompt for ReAct agent"""
    return f"""{enhanced_prompt}

{context}

Question: {query}

Begin your reasoning using the ReAct pattern. Remember to follow the exact format specified above."""

def create_chain_of_thought_prompt(enhanced_prompt: str, context: str, query: str, examples: list = None) -> str:
    """Create the main query prompt for Chain of Thought reasoning with optional few-shot examples"""
    
    examples_section = ""
    if examples:
        examples_section = "\n\nHere are some examples of how to approach similar problems:\n\n"
        for i, example in enumerate(examples):
            examples_section += f"Example {i}:\n"
            examples_section += f"Q: {example['question']}\n"
            examples_section += f"A: {example['reasoning']} {example['answer']}\n\n"
    
    return f"""{enhanced_prompt}

{context} {examples_section}

Question: {query}

Think through this step-by-step. Break down your reasoning process and show your work clearly before arriving at your final answer.
Respond with a human readable explanation of your thought process and the final answer in a structured format."""

# ==================== TOOL AGENT PROMPTS ====================

def create_tool_agent_tools_available_prompt(base_prompt: str, tool_descriptions: List[str]) -> str:
    """Create ToolAgent system prompt when tools are available"""
    tool_guidance = f"""

AVAILABLE TOOLS:
{chr(10).join(tool_descriptions)}

TOOL USAGE GUIDELINES:
- Always consider which tools are available before responding
- Use tools when they can provide more accurate, up-to-date, or comprehensive information
- Pay attention to required parameters - all required parameters must be provided
- If a parameter has a default value, you can omit it from the tool call
- If multiple tools could be useful, consider using them in sequence
- Always explain your tool selection reasoning and parameter choices
- If a tool fails due to missing or invalid parameters, check the parameter requirements
- Provide clear summaries of tool results to the user

TOOL CALL FORMAT:
When you need to use a tool, respond with a JSON object in this exact format:
{{
    "action": "tool_call",
    "tool_name": "tool_name_here",
    "parameters": {{
        "param1": "value1",
        "param2": "value2"
    }},
    "reasoning": "Brief explanation of why you chose this tool and these parameters"
}}

If you don't need to use any tools, respond with:
{{
    "action": "direct_response",
    "response": "Your direct answer here",
    "reasoning": "Brief explanation of why no tools were needed"
}}
"""
    return base_prompt + tool_guidance


def create_tool_agent_no_tools_prompt(base_prompt: str) -> str:
    """Create ToolAgent system prompt when no tools are available"""
    no_tools_guidance = """

NO TOOLS AVAILABLE:
- You do not have access to any external tools
- Provide direct responses based on your knowledge and training
- Be clear about any limitations in your responses
- If you cannot provide accurate information, acknowledge this limitation

RESPONSE FORMAT:
Always respond with a JSON object in this format:
{{
    "action": "direct_response",
    "response": "Your answer here",
    "reasoning": "Brief explanation based on available knowledge"
}}
"""
    return base_prompt + no_tools_guidance


def create_tool_agent_no_tools_query_prompt(enhanced_prompt: str, context: str, query: str) -> str:
    """Create query prompt for ToolAgent when no tools are available"""
    return f"""{enhanced_prompt}

{context}

User Query: {query}

Since no tools are available, provide a direct response based on your knowledge using the JSON format specified above."""


def create_tool_agent_tools_query_prompt(enhanced_prompt: str, context: str, query: str) -> str:
    """Create query prompt for ToolAgent when tools are available"""
    return f"""{enhanced_prompt}

{context}

User Query: {query}

Analyze the query and decide if you need to use any tools. Respond using the JSON format specified above.
- If you need a tool, use the "tool_call" action format
- If you can answer directly, use the "direct_response" action format
- Make sure to include all required parameters and follow the parameter types specified
- Always include your reasoning for the decision"""


def create_tool_agent_iteration_continuation_prompt(last_tool_name: str, last_tool_result: str) -> str:
    """Create continuation prompt for ToolAgent iterations"""
    return f"""

Tool Result from {last_tool_name}: {last_tool_result}

Based on this result, provide your response using the JSON format:
- If you need another tool, use "tool_call" action
- If you have enough information to answer, use "direct_response" action
- Include your reasoning for the decision"""


def create_tool_selection_prompt(query: str, tool_descriptions: List[str]) -> str:
    """Create prompt for tool selection without execution"""
    return f"""Based on the query: "{query}"

Available tools:
{chr(10).join(tool_descriptions)}

Which tool(s) would be most appropriate for this query? Consider:
1. The tool's functionality and description
2. Whether you have the required parameters or can infer them from the query
3. The parameter types and constraints

Explain your reasoning and mention any parameters that would be needed.
Do not execute any tools, just recommend which ones to use and why."""


# ==================== SHARED PROMPTS ====================

def create_conversation_context(chat_history: List[dict], max_messages: int = 6) -> str:
    """Create conversation context section for prompts"""
    if not chat_history:
        return ""
    
    context = "\n\nConversation history:\n"
    for msg in chat_history[-max_messages:]:  # Keep last N messages
        context += f"{msg['role'].capitalize()}: {msg['content']}\n"
    
    return context 
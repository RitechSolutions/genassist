from typing import Dict, Any, List
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
import os


from app.modules.agents.llm.provider import LLMProvider
from app.modules.agents.utils import create_direct_response_prompt, create_json_human_prompt, create_tool_selection_prompt
from app.modules.agents.workflow.base_processor import NodeProcessor
from app.modules.agents.workflow.nodes.api_tool import ApiToolNodeProcessor
from app.modules.agents.workflow.nodes.knowledge_tool import KnowledgeToolNodeProcessor
from app.modules.agents.workflow.nodes.python_tool import PythonFunctionNodeProcessor

from app.modules.agents.workflow.nodes.slack_tool import SlackMessageNodeProcessor
from app.modules.agents.workflow.nodes.zendesk_tool import ZendeskTicketNodeProcessor


from app.schemas.llm import LlmProviderUpdate
logger = logging.getLogger(__name__)

class AgentNodeProcessor(NodeProcessor):
    """Processor for agent nodes that can select and execute tools"""
    

    

    def _clean_and_parse_json(self, content: str) -> Dict:
        """Clean and parse JSON content that might include markdown code blocks."""
        # Remove markdown code block syntax if present
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        # Clean any leading/trailing whitespace
        content = content.strip()
        try:
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise

    async def process(self, input_data: Dict[str, Any] = None) -> str:
        """Process an agent node with tool selection and execution"""
        # Get agent configuration
        node_config = self.get_node_config()
        # Get model configuration
        new_llm_provider = LlmProviderUpdate(
            llm_model=node_config.get("model", "gpt-3.5-turbo"),
            llm_model_provider=node_config.get("provider", "openai"),
            connection_data={"apiKey": node_config.get("apiKey", ""),
                            "temperature": node_config.get("temperature", 0.7),
                            "maxTokens": node_config.get("maxTokens", 1024)
                            },
        )
        provider_id = node_config.get("providerId", None)
        
        human_enabled = not node_config.get("jsonParsing", False)

        # prompt = await self.get_process_input(input_data, 'prompt')
        input_data = await self.get_process_input(input_data)
        logger.info(f"Input data: {input_data}")
        system_prompt = input_data.get("system_prompt")
        logger.info(f"System prompt: {system_prompt}")
        
        system_prompt_messages = []
        if system_prompt:
            system_prompt_messages.append(SystemMessage(content=system_prompt))

        prompt = input_data.get("prompt")
        tools = input_data.get("tools")
        self.set_input(prompt)
        
        
        # try:
        if True:
            # Set up the environment for the model
            llm = LLMProvider.get_instance().get_model(provider_id);
            
            if tools:
            # Create tool selection prompt
                tool_selection_prompt = create_tool_selection_prompt(str(prompt), tools)
                # Get tool selection decision
                tool_selection_response = llm.invoke([*system_prompt_messages, HumanMessage(content=tool_selection_prompt)])
                tool_selection = self._clean_and_parse_json(tool_selection_response.content)
            
            
            response = None
            
            
            # Process the results
            if tools and tool_selection.get("should_execute", False):
                results = []

                for selected_tool in tool_selection.get("selected_tools", []):
                    tool_index = selected_tool["tool_index"] - 1
                    tool = tools[tool_index]
                    node_id = tool["node_id"]
                    node_type = tool["type"]
                    tool_data = self.get_context().get_node_by_id(node_id)["data"]
                        # Create the appropriate processor based on tool type
                    tool_processor = None
                    if node_type == "apiToolNode":
                        tool_processor = ApiToolNodeProcessor(self.get_context(), node_id, tool_data)
                    elif node_type in ["knowledgeToolNode", "knowledgeBaseNode"]:
                        tool_processor = KnowledgeToolNodeProcessor(
                            self.get_context(),
                            node_id, 
                            tool_data
                        )
                    elif node_type == "pythonCodeNode":
                        tool_processor = PythonFunctionNodeProcessor(
                            self.get_context(),
                            node_id, 
                            tool_data
                        )
                    elif node_type == "slackMessageNode":
                        tool_processor = SlackMessageNodeProcessor(
                            self.get_context(),
                            node_id,
                            tool_data
                        )
                    elif node_type == "zendeskTicketNode":
                        tool_processor = ZendeskTicketNodeProcessor(self.context, node_id, tool_data)

                    if tool_processor:
                        # Update tool parameters with extracted values
                        extracted_parameters = selected_tool.get("extracted_parameters", {})
                        tool_result = await tool_processor.process(extracted_parameters)
                        results.append({
                            "tool": tool["name"],
                            "type": node_type,
                            "result": tool_result,
                            "missing_parameters": selected_tool.get("missing_parameters", [])
                        })
                logger.info(f"Results: {results}")
                response = json.dumps(results, indent=2)
                logger.info(f"Response: {response}")
                if human_enabled:
                # Create a prompt to format the results in a human-friendly way
                    format_prompt = create_json_human_prompt(prompt, results)
                    formatted_response = llm.invoke([*system_prompt_messages, HumanMessage(content=format_prompt)])
                    response = formatted_response.content
            else:
                # If no tools are selected, use the LLM to directly answer the input
                direct_response_prompt = create_direct_response_prompt(str(prompt))

                direct_response = llm.invoke([*system_prompt_messages, HumanMessage(content=direct_response_prompt)])
                response = direct_response.content
            # Create final response
          
          
          
            # else:
            #     # Return the structured JSON response
           
            #     final_response = {
            #         "tool_selection": tool_selection,
            #         "execution_results": results,
            #         "original_input": prompt
            #     }
            #     results.append({
            #         "type": "final_response",
            #         "result": final_response
            #     })
            self.save_output(response)
            
            return self.get_output()
            
        # except Exception as e:
        #     logger.error(f"Error processing agent node: {str(e)}")
        #     error_message = f"Error: {str(e)}"
        #     self.save_output(error_message)
        #     return error_message

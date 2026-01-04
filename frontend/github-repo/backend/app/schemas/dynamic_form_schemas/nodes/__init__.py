from typing import Dict, List
from ..base import FieldSchema
from .chat_input_schema import CHAT_INPUT_NODE_DIALOG_SCHEMA
from .chat_output_schema import CHAT_OUTPUT_NODE_DIALOG_SCHEMA
from .router_schema import ROUTER_NODE_DIALOG_SCHEMA
from .agent_schema import AGENT_NODE_DIALOG_SCHEMA
from .api_tool_schema import API_TOOL_NODE_DIALOG_SCHEMA
from .template_schema import TEMPLATE_NODE_DIALOG_SCHEMA
from .llm_model_schema import LLM_MODEL_NODE_DIALOG_SCHEMA
from .knowledge_base_schema import KNOWLEDGE_BASE_NODE_DIALOG_SCHEMA
from .data_mapper_schema import DATA_MAPPER_NODE_DIALOG_SCHEMA
from .tool_builder_schema import TOOL_BUILDER_NODE_DIALOG_SCHEMA
from .slack_output_schema import SLACK_OUTPUT_NODE_DIALOG_SCHEMA
from .calendar_event_tool_schema import CALENDAR_EVENT_TOOL_NODE_DIALOG_SCHEMA
from .read_mails_schema import READ_MAILS_NODE_DIALOG_SCHEMA
from .gmail_schema import GMAIL_NODE_DIALOG_SCHEMA
from .whatsapp_schema import WHATSAPP_NODE_DIALOG_SCHEMA
from .zendesk_ticket_schema import ZENDESK_TICKET_NODE_DIALOG_SCHEMA
from .python_code_schema import PYTHON_CODE_NODE_DIALOG_SCHEMA
from .sql_schema import SQL_NODE_DIALOG_SCHEMA
from .aggregator_schema import AGGREGATOR_NODE_DIALOG_SCHEMA
from .jira_schema import JIRA_NODE_DIALOG_SCHEMA
from .ml_model_inference_schema import ML_MODEL_INFERENCE_NODE_DIALOG_SCHEMA
from .train_data_source_schema import TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA
from .thread_rag_schema import THREAD_RAG_NODE_DIALOG_SCHEMA
from .preprocessing_schema import PREPROCESSING_NODE_DIALOG_SCHEMA
from .train_model_schema import TRAIN_MODEL_NODE_DIALOG_SCHEMA

NODE_DIALOG_SCHEMAS: Dict[str, List[FieldSchema]] = {
    "chatInputNode": CHAT_INPUT_NODE_DIALOG_SCHEMA,
    "chatOutputNode": CHAT_OUTPUT_NODE_DIALOG_SCHEMA,
    "routerNode": ROUTER_NODE_DIALOG_SCHEMA,
    "agentNode": AGENT_NODE_DIALOG_SCHEMA,
    "apiToolNode": API_TOOL_NODE_DIALOG_SCHEMA,
    "templateNode": TEMPLATE_NODE_DIALOG_SCHEMA,
    "llmModelNode": LLM_MODEL_NODE_DIALOG_SCHEMA,
    "knowledgeBaseNode": KNOWLEDGE_BASE_NODE_DIALOG_SCHEMA,
    "dataMapperNode": DATA_MAPPER_NODE_DIALOG_SCHEMA,
    "toolBuilderNode": TOOL_BUILDER_NODE_DIALOG_SCHEMA,
    "slackMessageNode": SLACK_OUTPUT_NODE_DIALOG_SCHEMA,
    "calendarEventNode": CALENDAR_EVENT_TOOL_NODE_DIALOG_SCHEMA,
    "readMailsNode": READ_MAILS_NODE_DIALOG_SCHEMA,
    "gmailNode": GMAIL_NODE_DIALOG_SCHEMA,
    "whatsappToolNode": WHATSAPP_NODE_DIALOG_SCHEMA,
    "zendeskTicketNode": ZENDESK_TICKET_NODE_DIALOG_SCHEMA,
    "pythonCodeNode": PYTHON_CODE_NODE_DIALOG_SCHEMA,
    "sqlNode": SQL_NODE_DIALOG_SCHEMA,
    "aggregatorNode": AGGREGATOR_NODE_DIALOG_SCHEMA,
    "jiraNode": JIRA_NODE_DIALOG_SCHEMA,
    "mlModelInferenceNode": ML_MODEL_INFERENCE_NODE_DIALOG_SCHEMA,
    "trainDataSourceNode": TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA,
    "threadRAGNode": THREAD_RAG_NODE_DIALOG_SCHEMA,
    "preprocessingNode": PREPROCESSING_NODE_DIALOG_SCHEMA,
    "trainModelNode": TRAIN_MODEL_NODE_DIALOG_SCHEMA,
}


def get_node_dialog_schema(node_type: str):
    return NODE_DIALOG_SCHEMAS.get(node_type)

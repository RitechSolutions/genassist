from typing import List

from ..base import FieldSchema

EXTERNAL_AGENT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(name="name", type="text", label="Node Name", required=False),
    FieldSchema(name="endpoint", type="text", label="Endpoint URL", required=True, default="https://"),
    FieldSchema(name="method", type="select", label="HTTP Method", required=True, default="POST"),
    FieldSchema(name="authType", type="select", label="Authentication Type", required=False, default="none"),
    FieldSchema(name="authToken", type="text", label="Token / API Key", required=False),
    FieldSchema(name="authHeader", type="text", label="Auth Header Name", required=False, default="Authorization"),
    FieldSchema(name="authUsername", type="text", label="Username (Basic Auth)", required=False),
    FieldSchema(name="authPassword", type="text", label="Password (Basic Auth)", required=False),
    FieldSchema(name="requestBody", type="text", label="Request Body (JSON)", required=False),
    FieldSchema(name="messageField", type="text", label="Message Field Path", required=False, default="message"),
    FieldSchema(name="stepsField", type="text", label="Steps Field Path", required=False, default="steps"),
    FieldSchema(name="mappingScript", type="code", label="Advanced Mapping Script (Python)", required=False),
]
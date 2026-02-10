import { NodeProps } from "reactflow";
import {
  APIToolNodeData,
  OpenApiNodeData,
  KnowledgeBaseNodeData,
  NodeData,
  NodeTypeDefinition,
  PythonCodeNodeData,
  SQLNodeData,
  MLModelInferenceNodeData,
  ThreadRAGNodeData,
  WorkflowExecutorNodeData,
} from "../../types/nodes";

import APIToolNode from "./apiToolNode";
import OpenApiNode from "./openApiNode";
import KnowledgeBaseNode from "./knowledgeBaseNode";
import PythonCodeNode from "./pythonCodeNode";
import SQLNode from "./sqlNode";
import MLModelInferenceNode from "./mlModelInferenceNode";
import ThreadRAGNode from "./threadRAGNode";
import WorkflowExecutorNode from "./workflowExecutorNode";

export const API_TOOL_NODE_DEFINITION: NodeTypeDefinition<APIToolNodeData> = {
  type: "apiToolNode",
  label: "API Connector",
  description:
    "Makes HTTP requests to external APIs using configurable methods, headers, and bodies.",
  shortDescription: "Call an external API",
  configSubtitle:
    "Configure API request settings, including endpoint, method, headers, and body.",
  category: "tools",
  icon: "Globe",
  defaultData: {
    name: "API Connector",
    endpoint: "https://",
    method: "GET",
    headers: {},
    parameters: {},
    requestBody: "",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: APIToolNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "apiToolNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const OPEN_API_NODE_DEFINITION: NodeTypeDefinition<OpenApiNodeData> = {
  type: "openApiNode",
  label: "OpenAPI Explorer",
  description:
    "Uses an OpenAPI specification and an LLM to answer questions about an API.",
  shortDescription: "Explore an API specification",
  configSubtitle:
    "Select an LLM provider, upload an OpenAPI spec, and define the query.",
  category: "tools",
  icon: "Search",
  defaultData: {
    name: "OpenAPI Explorer",
    providerId: "",
    originalFileName: "",
    query: "",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: OpenApiNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "openApiNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const KNOWLEDGE_BASE_NODE_DEFINITION: NodeTypeDefinition<KnowledgeBaseNodeData> =
  {
    type: "knowledgeBaseNode",
    label: "Knowledge Query",
    description:
      "Queries connected knowledge bases to retrieve relevant information.",
    shortDescription: "Query knowledge bases",
    configSubtitle:
      "Configure knowledge base query settings, including selected sources and limits.",
    category: "tools",
    icon: "Database",
    defaultData: {
      name: "Knowledge Query",
      selectedBases: [],
      query: "",
      limit: 5,
      force: false,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    } as KnowledgeBaseNodeData,
    component: KnowledgeBaseNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "knowledgeBaseNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const PYTHON_CODE_NODE_DEFINITION: NodeTypeDefinition<PythonCodeNodeData> =
  {
    type: "pythonCodeNode",
    label: "Python Executor",
    description:
      "Executes Python code to transform data or perform custom logic.",
    shortDescription: "Execute Python code",
    configSubtitle:
      "Configure the Python execution environment, including script and parameters.",
    category: "tools",
    icon: "Code",
    defaultData: {
      name: "Python Executor",
      code: `# Generated Python function template
from typing import Optional

# Store your result in the 'result' variable
# Import any additional libraries you need
# import json
# import requests
# import datetime

def executable_function(params):
    
    # Your code logic here - example using the parameters:
    result = 'Successfully executed {{parameter1}} function with no parameters'

    return result`,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    },
    component: PythonCodeNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "pythonCodeNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const SQL_NODE_DEFINITION: NodeTypeDefinition<SQLNodeData> = {
  type: "sqlNode",
  label: "SQL Generator",
  description:
    "Generates SQL queries using an AI model to retrieve structured data.",
  shortDescription: "Generate SQL queries",
  configSubtitle:
    "Configure SQL generation settings, including model provider, data source, and prompts.",
  category: "tools",
  icon: "Database",
  defaultData: {
    name: "SQL Generator",
    providerId: "",
    dataSourceId: "",
    query: "",
    systemPrompt: "",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  } as SQLNodeData,
  component: SQLNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "sqlNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const ML_MODEL_INFERENCE_NODE_DEFINITION: NodeTypeDefinition<MLModelInferenceNodeData> =
  {
    type: "mlModelInferenceNode",
    label: "ML Model Inference",
    description: "Run inference using a trained ML model",
    category: "tools",
    icon: "Brain",
    defaultData: {
      name: "ML Model",
      modelId: "",
      modelName: "",
      inferenceInputs: {},
      features: {},
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    } as MLModelInferenceNodeData,
    component: MLModelInferenceNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "mlModelInferenceNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const THREAD_RAG_NODE_DEFINITION: NodeTypeDefinition<ThreadRAGNodeData> =
  {
    type: "threadRAGNode",
    label: "Thread RAG",
    description: "Retrieve context from or add messages to thread RAG",
    category: "tools",
    icon: "Database",
    defaultData: {
      name: "Thread RAG",
      action: "retrieve",
      query: "{{query}}",
      top_k: 5,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    } as ThreadRAGNodeData,
    component: ThreadRAGNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "threadRAGNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const WORKFLOW_EXECUTOR_NODE_DEFINITION: NodeTypeDefinition<WorkflowExecutorNodeData> =
  {
    type: "workflowExecutorNode",
    label: "Workflow Executor",
    description:
      "Executes another workflow as a sub-workflow, allowing you to compose workflows together.",
    shortDescription: "Execute another workflow",
    configSubtitle:
      "Select a workflow to execute and configure its input parameters.",
    category: "tools",
    icon: "Workflow",
    defaultData: {
      name: "Workflow Executor",
      workflowId: undefined,
      workflowName: undefined,
      inputParameters: {},
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    } as WorkflowExecutorNodeData,
    component: WorkflowExecutorNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "workflowExecutorNode",
      position,
      data: {
        ...data,
      },
    }),
  };

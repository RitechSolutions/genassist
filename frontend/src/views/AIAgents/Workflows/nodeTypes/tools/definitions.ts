import { NodeProps } from "reactflow";
import {
  KnowledgeBaseNodeData,
  NodeData,
  NodeTypeDefinition,
  PythonCodeNodeData,
} from "../../types/nodes";

import { APIToolNodeData } from "../../types/nodes";
import APIToolNode from "./apiToolNode";
import KnowledgeBaseNode from "./knowledgeBaseNode";
import PythonCodeNode from "./pythonCodeNode";

export const API_TOOL_NODE_DEFINITION: NodeTypeDefinition<APIToolNodeData> = {
  type: "apiToolNode",
  label: "API Tool",
  description: "Make real-time API calls to external services",
  category: "tools",
  icon: "Globe",
  defaultData: {
    name: "API Tool",
    description: "Makes API calls to external services",
    endpoint: "https://",
    method: "GET",
    headers: {},
    parameters: {},
    requestBody: "",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "json",
      },

      {
        id: "output_reference",
        type: "source",
        compatibility: "tools",
      },
      {
        id: "output",
        type: "source",
        compatibility: "json",
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
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },

        {
          id: "output_reference",
          type: "source",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
        },
      ],
    },
  }),
};

export const KNOWLEDGE_BASE_NODE_DEFINITION: NodeTypeDefinition<KnowledgeBaseNodeData> =
  {
    type: "knowledgeBaseNode",
    label: "Knowledge Base",
    description: "Query multiple knowledge bases for information",
    category: "tools",
    icon: "Database",
    defaultData: {
      name: "Knowledge Base",
      description: "Query multiple knowledge bases",
      selectedBases: [],
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },

        {
          id: "output_reference",
          type: "source",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
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
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "json",
          },

          {
            id: "output_reference",
            type: "source",
            compatibility: "tools",
          },
          {
            id: "output",
            type: "source",
            compatibility: "json",
          },
        ],
      },
    }),
  };

export const PYTHON_CODE_NODE_DEFINITION: NodeTypeDefinition<PythonCodeNodeData> =
  {
    type: "pythonCodeNode",
    label: "Python Code",
    description: "Execute Python code in a sandboxed environment",
    category: "tools",
    icon: "Code",
    defaultData: {
      name: "Python Code",
      description: "Execute Python code in a sandboxed environment",
      code: "",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },

        {
          id: "output_reference",
          type: "source",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
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
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "json",
          },
          {
            id: "output_reference",
            type: "source",
            compatibility: "tools",
          },
          {
            id: "output",
            type: "source",
            compatibility: "json",
          },
        ],
      },
    }),
  };

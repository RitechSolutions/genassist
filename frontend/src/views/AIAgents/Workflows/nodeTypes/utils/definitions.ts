import { NodeProps } from "reactflow";
import { NodeTypeDefinition, NodeData, TemplateNodeData } from "../../types/nodes";
import PromptNode from "./templateNode";

export const TEMPLATE_NODE_DEFINITION: NodeTypeDefinition<TemplateNodeData> = {
    type: "promptNode",
    label: "Prompt Template",
    description: "Create dynamic prompt templates with placeholders",
    category: "process",
    icon: "FileText",
    defaultData: {
      label: "Prompt Template",
      template:
        "You are my assistent! Please answer the following question: {{user_query}}",
      handlers: [
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
      ],
    },
    component: PromptNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "promptNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "output",
            type: "source",
            compatibility: "text",
          },
        ],
      },
    }),
  }
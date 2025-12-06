import { NodeProps } from "reactflow";
import {
  NodeTypeDefinition,
  NodeData,
  TemplateNodeData,
  DataMapperNodeData,
} from "../../types/nodes";
import TemplateNode from "./templateNode";
import DataMapperNode from "./dataMapperNode";

export const TEMPLATE_NODE_DEFINITION: NodeTypeDefinition<TemplateNodeData> = {
  type: "templateNode",
  label: "Text Template",
  description:
    "Generates formatted text using a configurable template with dynamic variables.",
  shortDescription: "Generate text from a template",
  configSubtitle: "Configure the text template and its dynamic variables.",
  category: "formatting",
  icon: "FileText",
  defaultData: {
    name: "Text Template",
    template: "You are my AI assistant!",

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
  component: TemplateNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "templateNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const DATA_MAPPER_NODE_DEFINITION: NodeTypeDefinition<DataMapperNodeData> =
  {
    type: "dataMapperNode",
    label: "Data Transformer",
    description:
      "Transforms data using mapping rules or custom Python scripts.",
    shortDescription: "Transform data",
    configSubtitle:
      "Configure data transformation rules, including mapping logic and Python script.",
    category: "formatting",
    icon: "ArrowLeftRight",
    defaultData: {
      name: "Data Transformer",
      pythonScript: `# Generated Python function template
from typing import Optional

# Store your result in the 'result' variable
# Import any additional libraries you need
# import json
# import requests
# import datetime

def executable_function(params):
    
    # Your transformation logic here - example using the parameters:
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
    component: DataMapperNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "dataMapperNode",
      position,
      data: {
        ...data,
      },
    }),
  };

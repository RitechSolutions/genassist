import { NodeProps } from "reactflow";
import {
  NodeTypeDefinition,
  NodeData,
  TemplateNodeData,
  DataMapperNodeData,
  GuardrailProvenanceNodeData,
  GuardrailNliNodeData,
} from "../../types/nodes";
import TemplateNode from "./templateNode";
import DataMapperNode from "./dataMapperNode";
import GuardrailProvenanceNode from "./guardrailProvenanceNode";
import GuardrailNliNode from "./guardrailNliNode";

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

export const GUARDRAIL_PROVENANCE_NODE_DEFINITION: NodeTypeDefinition<GuardrailProvenanceNodeData> =
  {
    type: "guardrailProvenanceNode",
    label: "Guardrail: Provenance",
    description:
      "Checks whether the model answer is grounded in the provided context.",
    shortDescription: "Check answer provenance",
    configSubtitle:
      "Configure which fields contain the answer and context, and the minimum provenance score.",
    category: "utils",
    icon: "ShieldCheck",
    defaultData: {
      name: "Guardrail Provenance",
      answer_field: "",
      context_field: "",
      min_score: 0.5,
      fail_on_violation: false,
      provenance_mode: "embeddings",
      embedding_type: "huggingface",
      embedding_model_name: "all-MiniLM-L6-v2",
      use_llm_judge: false,
      llm_provider_id: "",
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
    component:
      GuardrailProvenanceNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "guardrailProvenanceNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const GUARDRAIL_NLI_NODE_DEFINITION: NodeTypeDefinition<GuardrailNliNodeData> =
  {
    type: "guardrailNliNode",
    label: "Guardrail: NLI Fact-check",
    description:
      "Runs a simple NLI-style fact-check between the answer and evidence.",
    shortDescription: "NLI fact-check answer",
    configSubtitle:
      "Configure which fields contain the answer and evidence, and the minimum entailment score.",
    category: "utils",
    icon: "ShieldAlert",
    defaultData: {
      name: "Guardrail NLI",
      answer_field: "",
      evidence_field: "",
      min_entail_score: 0.5,
      fail_on_contradiction: false,
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
    component: GuardrailNliNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "guardrailNliNode",
      position,
      data: {
        ...data,
      },
    }),
  };



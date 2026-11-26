import { NodeProps } from "reactflow";
import { defaultGuardrailPolicy } from "@/helpers/guardrailChecks";
import {
  NodeTypeDefinition,
  NodeData,
  TemplateNodeData,
  DataMapperNodeData,
  GuardrailNodeData,
  GuardrailProvenanceNodeData,
  GuardrailNliNodeData,
  FileReaderNodeData,
  NodeHandler,
} from '../../types/nodes';
import TemplateNode from "./templateNode";
import DataMapperNode from "./dataMapperNode";
import GuardrailProvenanceNode from "./guardrailProvenanceNode";
import GuardrailNliNode from "./guardrailNliNode";
import GuardrailNode from "./guardrailNode";
import FileReaderNode from './fileReaderNode';
import {
  DATA_TRANSFORMER_HELP_CONTENT,
  FILE_READER_HELP_CONTENT,
  GUARDRAIL_HELP_CONTENT,
  GUARDRAIL_NLI_HELP_CONTENT,
  GUARDRAIL_PROVENANCE_HELP_CONTENT,
  TEXT_TEMPLATE_HELP_CONTENT,
} from "./helperDefinition";

export const TEMPLATE_NODE_DEFINITION: NodeTypeDefinition<TemplateNodeData> = {
  type: "templateNode",
  label: "Text Template",
  description:
    "Generates formatted text using a configurable template with dynamic variables.",
  shortDescription: "Generate text from a template",
  helpContent: TEXT_TEMPLATE_HELP_CONTENT,
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
    helpContent: DATA_TRANSFORMER_HELP_CONTENT,
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

const GUARDRAIL_HANDLERS: NodeHandler[] = [
  { id: "input", type: "target", compatibility: "any", position: "left" },
  {
    id: "output",
    type: "source",
    compatibility: "any",
    position: "right",
    label: "Passed",
  },
  {
    id: "output_blocked",
    type: "source",
    compatibility: "any",
    position: "right",
    label: "Blocked",
  },
];

export const GUARDRAIL_NODE_DEFINITION: NodeTypeDefinition<GuardrailNodeData> = {
  type: "guardrailNode",
  label: "Guardrail",
  description:
    "Checks text for prompt attacks, harmful content, denied topics and blocked words.",
  shortDescription: "Check text before it moves on",
  helpContent: GUARDRAIL_HELP_CONTENT,
  configSubtitle:
    "Configure the text to check, the checks to run and the message sent when it is blocked.",
  category: "guardrails",
  icon: "ShieldCheck",
  defaultData: {
    name: "Guardrail",
    text: "{{session.message}}",
    providerId: "",
    prompt_attack: "off",
    harmful_content: defaultGuardrailPolicy().harmful_content,
    denied_topics: [],
    blocked_words: [],
    previous_reply_context: true,
    blocked_message: "",
    handlers: GUARDRAIL_HANDLERS,
  },
  getHandlers: () => GUARDRAIL_HANDLERS,
  component: GuardrailNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "guardrailNode",
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
    helpContent: GUARDRAIL_PROVENANCE_HELP_CONTENT,
    configSubtitle:
      "Configure which fields contain the answer and context, and the minimum provenance score.",
    category: "guardrails",
    icon: "ShieldQuestionMark",
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
      handlers: GUARDRAIL_HANDLERS,
    },
    getHandlers: () => GUARDRAIL_HANDLERS,
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
    helpContent: GUARDRAIL_NLI_HELP_CONTENT,
    configSubtitle:
      "Configure which fields contain the answer and evidence, and the minimum entailment score.",
    category: "guardrails",
    icon: "ShieldAlert",
    defaultData: {
      name: "Guardrail NLI",
      answer_field: "",
      evidence_field: "",
      min_entail_score: 0.5,
      fail_on_contradiction: false,
      handlers: GUARDRAIL_HANDLERS,
    },
    getHandlers: () => GUARDRAIL_HANDLERS,
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

export const FILE_READER_NODE_DEFINITION: NodeTypeDefinition<FileReaderNodeData> = {
  type: 'fileReaderNode',
  label: 'File Reader',
  description: 'Reads the content of an uploaded file and outputs it as text.',
  shortDescription: 'Extract content of a file',
  helpContent: FILE_READER_HELP_CONTENT,
  configSubtitle: 'Extract text from a chat-attached document or an uploaded file.',
  category: 'utils',
  icon: 'FileText',
  defaultData: {
    name: 'File Reader',
    fileSource: 'chatAttachment',
    handlers: [
      {
        id: 'input',
        type: 'target',
        compatibility: 'any',
        position: 'left',
      },
      {
        id: 'output',
        type: 'source',
        compatibility: 'any',
        position: 'right',
      },
    ],
  },
  component: FileReaderNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: 'fileReaderNode',
    position,
    data: {
      ...data,
    },
  }),
};


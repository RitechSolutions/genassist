import type { NodeHelpContent } from "../../types/nodes";

export const UTILS_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Utils nodes help you validate, safeguard, and inspect workflow data before it moves to the next step. They are useful when you want to add quality checks, confidence thresholds, or protective logic around model outputs.",
  sections: [
    {
      title: "When To Use Utils Nodes",
      body: "Use utils nodes when you need to:",
      bullets: [
        "Verify whether an answer is supported by evidence",
        "Check whether generated output is grounded in the provided context",
        "Apply confidence thresholds before allowing an answer through",
        "Add safety and reliability checks to LLM workflows",
      ],
    },
    {
      title: "Summary",
      body: "Utils nodes are especially helpful near the end of AI flows where you want to reduce hallucinations or block unsupported answers.",
    },
  ],
};

export const FORMATTING_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Formatting nodes help prepare, reshape, and standardize data inside a workflow. These nodes are useful when the output of one step must be converted into a structure that another step can use more effectively.",
  sections: [
    {
      title: "When To Use Formatting Nodes",
      body: "Use formatting nodes when you need to:",
      bullets: [
        "Reformat raw text into a structured template",
        "Clean or reshape incoming data",
        "Convert outputs into a more usable format",
        "Prepare data before sending it to an AI node, tool, or integration",
      ],
    },
    {
      title: "Summary",
      body: "Formatting nodes are especially helpful when workflows depend on consistent structure and predictable outputs.",
    },
  ],
};

export const TEXT_TEMPLATE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Text Template node formats text using a predefined template. It is useful when you want to generate consistent messages, prompts, summaries, or outputs based on workflow variables.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Text Template node when you need to:",
      bullets: [
        "Build consistent prompts for AI nodes",
        "Create reusable message formats",
        "Insert dynamic values into a fixed template",
        "Standardize outputs before passing them to another node",
      ],
    },
  ],
};

export const DATA_TRANSFORMER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Data Transformer node reshapes and converts workflow data into the format required by later steps. It helps make sure outputs are structured correctly before they are passed to other nodes.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Data Transformer node when you need to:",
      bullets: [
        "Rename or remap fields",
        "Convert data into a required structure",
        "Clean and normalize workflow values",
        "Prepare data for integrations, tools, or AI processing",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Data Transformer dialog will open.",
        "Enter the Node Name.",
        "Add or edit the Python Script used for the transformation.",
        "Insert any workflow variables that should be used inside the script.",
        "Verify that the script stores the final value in the expected result output.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const GUARDRAIL_PROVENANCE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Guardrail Provenance node checks whether an answer is grounded in the provided context by measuring provenance similarity. It is designed to catch answers that are weakly supported or not traceable to the retrieved content.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Guardrail Provenance node when you need to:",
      bullets: [
        "Check whether an answer is grounded in retrieved context",
        "Enforce a provenance threshold before returning a response",
        "Reduce unsupported generations in RAG pipelines",
        "Add a validation layer after answer generation",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Guardrail Provenance dialog will open.",
        "Set the Answer field key.",
        "Set the Context field key.",
        "Define the Minimum provenance score (0-1).",
        "Toggle Fallback answer on violation if the node should substitute a fallback response instead of blocking.",
        "Choose the Provenance mode.",
        "Select the Embedding provider.",
        "Enter the Embedding model name.",
        "Click Save Changes.",
      ],
    },
  ],
};

export const GUARDRAIL_NLI_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Guardrail NLI node fact-checks an answer against supporting evidence using a natural language inference model. It helps determine whether the answer is entailed by the context before the response is passed forward in the workflow.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Guardrail NLI node when you need to:",
      bullets: [
        "Validate that an answer is supported by source evidence",
        "Block or replace contradictory responses",
        "Add a confidence threshold before returning model output",
        "Reduce hallucinations in question-answering flows",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Guardrail NLI dialog will open.",
        "Set the Answer field key.",
        "Set the Evidence field key.",
        "Choose the NLI model.",
        "Define the Minimum entailment score (0-1).",
        "Toggle Fallback answer on contradiction if the node should substitute a fallback response instead of blocking.",
        "Click Save Changes.",
      ],
    },
  ],
};

export const FILE_READER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The File Reader node uploads a file and extracts its content for use in later workflow steps. It is useful when your flow needs to read documents or file-based inputs before processing, analysis, or generation.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the File Reader node when you need to:",
      bullets: [
        "Extract text from an uploaded file",
        "Pass file content into an AI or utility node",
        "Start a workflow from a document input",
        "Prepare uploaded content for downstream processing",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure File Reader dialog will open.",
        "Enter the Node Name.",
        "Upload the File whose content should be extracted.",
        "Review the selected file.",
        "Click Save Changes.",
      ],
    },
  ],
};

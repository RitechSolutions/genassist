import type { NodeHelpContent } from "../../types/nodes";

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

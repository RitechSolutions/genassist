import type { NodeHelpContent } from "../../types/nodes";

export const AI_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "AI nodes bring model-driven intelligence into your workflows. These nodes are used for text generation, reasoning, agent behavior, tool orchestration, and advanced AI-powered interactions.",
  sections: [
    {
      title: "When To Use AI Nodes",
      body: "Use AI nodes when you need to:",
      bullets: [
        "Generate or transform natural language",
        "Let an AI model reason over inputs",
        "Build autonomous or semi-autonomous agents",
        "Create tool-enabled AI behaviors",
        "Connect to model-serving infrastructure",
      ],
    },
    {
      title: "Summary",
      body: "AI nodes are a strong fit for workflows that involve interpretation, generation, planning, or intelligent responses.",
    },
  ],
};

export const AI_AGENT_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The AI Agent node enables goal-oriented AI behavior inside a workflow. It can reason about inputs, decide what to do next, and interact with available tools or connected systems based on its instructions.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the AI Agent node when you need to:",
      bullets: [
        "Build multi-step AI-driven behavior",
        "Let AI choose between actions dynamically",
        "Combine model reasoning with tools",
        "Support conversational or decision-based workflows",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure AI Agent dialog will open.",
        "Enter the Node Name.",
        "Select the Provider that will run the agent.",
        "Add the System Prompt and User Prompt.",
        "Choose the Agent Type, set the Max Iterations, and enable optional settings such as memory or PII masking if needed.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const LANGUAGE_MODEL_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Language Model node sends input to a configured language model and returns the generated result. It is commonly used for prompting, summarization, rewriting, extraction, and conversational responses.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Language Model node when you need to:",
      bullets: [
        "Generate text from prompts",
        "Summarize documents or messages",
        "Extract structured information from text",
        "Rewrite or classify content",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Language Model dialog will open.",
        "Enter the Node Name.",
        "Select the model or provider to use.",
        "Add the prompt or input instructions.",
        "Configure generation settings if available.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const TOOL_BUILDER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Tool Builder node defines a tool that can be used by other workflow components, especially AI-driven nodes. It helps package actions, inputs, and outputs into a reusable interface.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Tool Builder node when you need to:",
      bullets: [
        "Expose workflow actions as reusable tools",
        "Let an AI agent call structured operations",
        "Standardize how tool inputs and outputs are defined",
        "Encapsulate repeatable logic for use across flows",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Tool Builder dialog will open.",
        "Enter the Node Name.",
        "Add a clear Description for what the tool does.",
        "Configure any Required Parameters the tool should accept.",
        "Decide whether the tool should Return data directly as agent output.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const MCP_SERVER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The MCP Server node connects your workflow to an MCP-compatible server so models and agents can access external tools, resources, or actions through a structured interface.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the MCP Server node when you need to:",
      bullets: [
        "Connect AI workflows to MCP services",
        "Access remote tools through a standard protocol",
        "Provide structured resources to agents",
        "Extend workflows with external capabilities",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure MCP Server dialog will open.",
        "Enter the Node Name.",
        "Add the Description, choose the Connection Type, and enter the MCP Server URL.",
        "Configure optional settings such as API Key, Timeout, and Custom Headers.",
        "Discover and select the available tools you want to expose to the agent.",
        "Save the node configuration.",
      ],
    },
  ],
};

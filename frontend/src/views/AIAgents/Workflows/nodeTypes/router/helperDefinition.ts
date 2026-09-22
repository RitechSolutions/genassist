import type { NodeHelpContent } from "../../types/nodes";

export const ROUTING_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Routing nodes control workflow direction by evaluating outcomes and combining results. They are useful when a workflow must branch, merge, or make logic-based transitions between steps.",
  sections: [
    {
      title: "When To Use Routing Nodes",
      body: "Use routing nodes when you need to:",
      bullets: [
        "Branch workflow execution based on conditions",
        "Merge multiple paths into one output",
        "Control decision points in the flow",
        "Build more dynamic workflow structures",
      ],
    },
    {
      title: "Summary",
      body: "Routing nodes are essential for creating flexible workflows that adapt to different inputs or execution outcomes.",
    },
  ],
};

export const CONDITIONAL_ROUTER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Conditional Router node directs workflow execution to different paths based on defined conditions. It is used to create branching logic and decision-based flow control.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Conditional Router node when you need to:",
      bullets: [
        "Branch logic based on input values",
        "Route different request types to different paths",
        "Build decision trees inside workflows",
        "Control execution based on rules",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Conditional Router dialog will open.",
        "Enter the Node Name.",
        "Enter the First Value to compare.",
        "Select the Compare Condition.",
        "Enter the Second Value and save the router logic.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const SWITCH_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Switch node provides deterministic N-way branching based on a single value. Instead of chaining several binary routers, one Switch routes execution into multiple clearly defined branches — one per case, plus a default branch for anything that doesn't match.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Switch node when you need to:",
      bullets: [
        "Route classified intents (billing, account, technical support, sales, cancellation) into separate branches",
        "Run different logic per status such as new, pending, approved, rejected, or completed",
        "Send low-, medium-, high-, and critical-priority items through different handling paths",
        "Branch on a known category, type, region, product, department, or workflow result",
        "Use a Classifier's output to decide which downstream workflow runs",
      ],
    },
    {
      title: "How it differs",
      body: "The Conditional Router is a binary true/false decision, and the Result Merger joins branches back together. Switch selects exactly one of many cases, keeping multi-option decisions readable on the canvas. A typical flow is Classifier → Switch → Specialist workflow.",
    },
    {
      title: "Smart Mode",
      body: "Turn on Smart Mode to let an LLM choose the case instead of comparing a value. Write a routing prompt (it can include variables such as the user's message) and describe each case; the model picks one of them. If the provider, prompt, or model answer is invalid, the Default branch is used.",
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Switch dialog will open.",
        "Enter the Node Name.",
        "Set the Value to route on, usually a variable from an upstream node, or turn on Smart Mode and write a routing prompt.",
        "Choose the Match Mode and whether matching is case sensitive (rule mode only).",
        "Add one case per branch and give each a name and a value to match (or a description, in Smart Mode).",
        "Connect each case output, plus the Default output, to its branch.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const RESULT_MERGER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Result Merger node combines outputs from multiple workflow branches into a single result. It is useful for collecting parallel outputs and preparing them for later steps.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Result Merger node when you need to:",
      bullets: [
        "Join outputs from multiple branches",
        "Consolidate parallel execution results",
        "Prepare merged data for later nodes",
        "Simplify downstream processing",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Result Merger dialog will open.",
        "Enter the Node Name.",
        "Select the Aggregation Strategy used to combine inputs.",
        "Set the Timeout and optional Forward Template.",
        "Choose whether the node should Require complete results before continuing.",
        "Save the node configuration.",
      ],
    },
  ],
};

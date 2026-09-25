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

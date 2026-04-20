import type { NodeHelpContent } from "../../types/nodes";

export const START_NODE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Start node marks the entry point of a workflow. It defines how execution begins and which input parameters are exposed to the rest of the workflow.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Start node when you need to:",
      bullets: [
        "Define the beginning of a workflow",
        "Accept initial inputs or parameters",
        "Trigger execution from a known entry point",
        "Structure the first step in a flow",
      ],
    },
  ],
};

export const FINISH_NODE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Finish node marks the end of a workflow and defines the final output returned by the process. It is used to complete execution and expose results in a clear way.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Finish node when you need to:",
      bullets: [
        "End a workflow explicitly",
        "Return final output data",
        "Control what result is exposed to the caller",
        "Finalize a multi-step process",
      ],
    },
  ],
};

export const SET_STATE_NODE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Set State node stores or updates workflow state during execution. It is useful for preserving values, tracking progress, and passing persistent context between steps.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Set State node when you need to:",
      bullets: [
        "Save values for later workflow steps",
        "Update state during execution",
        "Track process variables across nodes",
        "Preserve context inside longer workflows",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Set State dialog will open.",
        "Enter the Node Name.",
        "Add one or more State Entries.",
        "Enter the State Key that matches a stateful parameter.",
        "Set the State Value directly or by using a workflow variable.",
        "Save the node configuration.",
      ],
    },
  ],
};

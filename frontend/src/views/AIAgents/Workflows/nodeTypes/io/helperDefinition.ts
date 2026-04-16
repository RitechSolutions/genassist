import type { NodeHelpContent } from "../../types/nodes";

export const IO_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "I/O nodes define how workflows begin, end, exchange state, and involve human review. They are core orchestration components that control how information enters, exits, and pauses within the flow.",
  sections: [
    {
      title: "When To Use I/O Nodes",
      body: "Use I/O nodes when you need to:",
      bullets: [
        "Start or finish workflow execution",
        "Store or update workflow state",
        "Add human review or approval steps",
        "Control the operational flow of data",
      ],
    },
    {
      title: "Summary",
      body: "I/O nodes are foundational in almost every workflow because they shape how the workflow interacts with its inputs, outputs, and participants.",
    },
  ],
};

export const HUMAN_IN_THE_LOOP_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Human in the Loop node pauses the workflow for manual review, approval, or input. It is used when automated logic must be validated or completed by a person before the workflow continues.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Human in the Loop node when you need to:",
      bullets: [
        "Add approval steps to automation",
        "Request manual validation",
        "Collect human input before continuing",
        "Reduce risk in sensitive workflow decisions",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Human in the Loop dialog will open.",
        "Enter the Node Name.",
        "Add the Message shown to the reviewer.",
        "Choose whether to Ask once per conversation.",
        "Configure any required Form Fields for the human response.",
        "Save the node configuration.",
      ],
    },
  ],
};

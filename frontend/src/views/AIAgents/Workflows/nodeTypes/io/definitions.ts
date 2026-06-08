import {
  HumanInTheLoopNodeData,
  NodeData,
  NodeTypeDefinition,
} from "../../types/nodes";
import HumanInTheLoopNode from "./humanInTheLoopNode";
import { NodeProps } from "reactflow";
import { HUMAN_IN_THE_LOOP_HELP_CONTENT } from "./helperDefinition";

export const HUMAN_IN_THE_LOOP_NODE_DEFINITION: NodeTypeDefinition<HumanInTheLoopNodeData> =
  {
    type: "humanInTheLoopNode",
    label: "Human In The Loop",
    description:
      "Pauses the workflow to collect human input via a dynamic form.",
    shortDescription: "Collect human input",
    helpContent: HUMAN_IN_THE_LOOP_HELP_CONTENT,
    category: "io",
    icon: "ClipboardList",
    defaultData: {
      name: "Human In The Loop",
      message: "Please provide the following information:",
      form_fields: [],
      ask_once: true,
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
    component: HumanInTheLoopNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "humanInTheLoopNode",
      position,
      data: {
        ...data,
      },
    }),
  };

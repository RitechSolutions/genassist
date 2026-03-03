import {
  HumanInTheLoopNodeData,
  NodeData,
  NodeTypeDefinition,
} from "../../types/nodes";
import HumanInTheLoopNode from "./humanInTheLoopNode";
import { NodeProps } from "reactflow";

export const HUMAN_IN_THE_LOOP_NODE_DEFINITION: NodeTypeDefinition<HumanInTheLoopNodeData> =
  {
    type: "humanInTheLoopNode",
    label: "Human In The Loop",
    description:
      "Pauses the workflow to collect human input via a dynamic form.",
    shortDescription: "Collect human input",
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

import {
  UserInputNodeData,
  NodeData,
  NodeTypeDefinition,
} from "../../types/nodes";
import UserInputNode from "./userInputNode";
import { NodeProps } from "reactflow";

export const USER_INPUT_NODE_DEFINITION: NodeTypeDefinition<UserInputNodeData> =
  {
    type: "userInputNode",
    label: "User Input",
    description:
      "Pauses the workflow to collect structured data from the user via a dynamic form.",
    shortDescription: "Collect user input",
    category: "io",
    icon: "ClipboardList",
    defaultData: {
      name: "User Input",
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
    component: UserInputNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "userInputNode",
      position,
      data: {
        ...data,
      },
    }),
  };

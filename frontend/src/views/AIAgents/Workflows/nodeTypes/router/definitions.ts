import { NodeProps } from "reactflow";
import {
  AggregatorNodeData,
  NodeData,
  NodeTypeDefinition,
  RouterNodeData,
} from "../../types/nodes";
import RouterNode from "./routerNode";
import AggregatorNode from "./aggregatorNode";

export const ROUTER_NODE_DEFINITION: NodeTypeDefinition<RouterNodeData> = {
  type: "routerNode",
  label: "Conditional Router",
  description:
    "Routes data along different branches based on evaluation of a condition.",
  shortDescription: "Route based on a condition",
  configSubtitle:
    "Configure routing conditions, including comparison values and logic.",
  category: "routing",
  icon: "SplitRotated",
  defaultData: {
    name: "Conditional Router",
    first_value: "",
    compare_condition: "contains",
    second_value: "",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output_true",
        type: "source",
        compatibility: "any",
        position: "right",
      },
      {
        id: "output_false",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: RouterNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "routerNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const AGGREGATOR_NODE_DEFINITION: NodeTypeDefinition<AggregatorNodeData> =
  {
    type: "aggregatorNode",
    label: "Result Merger",
    description:
      "Merges results from multiple branches and returns once conditions are met.",
    shortDescription: "Merge results",
    configSubtitle:
      "Configure result aggregation settings, including strategy and timeout.",
    category: "routing",
    icon: "MergeRotated",
    defaultData: {
      name: "Result Merger",
      aggregationStrategy: "list",
      forwardTemplate: "",
      timeoutSeconds: 15,
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
    component: AggregatorNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "aggregatorNode",
      position,
      data: {
        ...data,
      },
    }),
  };

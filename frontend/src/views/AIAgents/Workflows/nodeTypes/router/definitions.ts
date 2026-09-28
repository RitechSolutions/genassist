import { NodeProps } from "reactflow";
import {
  AggregatorNodeData,
  FilterNodeData,
  NodeData,
  NodeTypeDefinition,
  RouterNodeData,
  SwitchNodeData,
} from "../../types/nodes";
import RouterNode from "./routerNode";
import AggregatorNode from "./aggregatorNode";
import SwitchNode from "./switchNode";
import FilterNode from "./filterNode";
import {
  CONDITIONAL_ROUTER_HELP_CONTENT,
  RESULT_MERGER_HELP_CONTENT,
  SWITCH_HELP_CONTENT,
  FILTER_HELP_CONTENT,
} from "./helperDefinition";
import { buildSwitchHandlers, DEFAULT_SWITCH_CASES } from "./switchCases";

export const ROUTER_NODE_DEFINITION: NodeTypeDefinition<RouterNodeData> = {
  type: "routerNode",
  label: "Conditional Router",
  description:
    "Routes data along different branches based on evaluation of a condition.",
  shortDescription: "Route based on a condition",
  helpContent: CONDITIONAL_ROUTER_HELP_CONTENT,
  configSubtitle:
    "Configure routing conditions, including comparison values and logic.",
  category: "routing",
  icon: "SplitRotated",
  defaultData: {
    name: "Conditional Router",
    smartModeEnabled: false,
    providerId: "",
    smartPrompt: "",
    systemPrompt: "",
    fallbackRoute: "false",
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

export const SWITCH_NODE_DEFINITION: NodeTypeDefinition<SwitchNodeData> = {
  type: "switchNode",
  label: "Switch",
  description:
    "Routes execution into one of several branches based on the value of a single input.",
  shortDescription: "Multi-way routing",
  helpContent: SWITCH_HELP_CONTENT,
  configSubtitle:
    "Configure how a case is chosen (by value or by LLM) and the cases for each branch.",
  category: "routing",
  icon: "Signpost",
  defaultData: {
    name: "Switch",
    smartModeEnabled: false,
    providerId: "",
    smartPrompt: "",
    systemPrompt: "",
    switchValue: "",
    matchMode: "equal",
    caseSensitive: false,
    cases: DEFAULT_SWITCH_CASES,
    handlers: buildSwitchHandlers(DEFAULT_SWITCH_CASES),
  },
  getHandlers: (data) => buildSwitchHandlers(data.cases ?? []),
  component: SwitchNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "switchNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const FILTER_NODE_DEFINITION: NodeTypeDefinition<FilterNodeData> = {
  type: "filterNode",
  label: "Filter",
  description:
    "Lets the branch continue only when a condition is true; otherwise the branch stops.",
  shortDescription: "Continue or stop",
  helpContent: FILTER_HELP_CONTENT,
  configSubtitle:
    "Configure the condition that must hold for the branch to continue.",
  category: "routing",
  icon: "Filter",
  defaultData: {
    name: "Filter",
    field: "",
    operator: "equal",
    value: "",
    caseSensitive: false,
    stopMessage: "",
    handlers: [
      { id: "input", type: "target", compatibility: "any", position: "left" },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
        label: "Passed",
      },
    ],
  },
  component: FilterNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "filterNode",
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
    helpContent: RESULT_MERGER_HELP_CONTENT,
    configSubtitle:
      "Configure result aggregation settings, including strategy and timeout.",
    category: "routing",
    icon: "MergeRotated",
    defaultData: {
      name: "Result Merger",
      aggregationStrategy: "list",
      forwardTemplate: "",
      timeoutSeconds: 15,
      requireAllInputs: true,
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

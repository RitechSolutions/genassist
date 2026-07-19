import { describe, it, expect, beforeAll } from "vitest";
import { Node } from "reactflow";
import nodeRegistry from "../registry/nodeRegistry";
import { NodeData, NodeTypeDefinition } from "../types/nodes";
import {
  parseAgentActions,
  createNodeFromAction,
  AddNodeAction,
} from "./assistantActionParser";

beforeAll(() => {
  nodeRegistry.register({
    type: "agentNode",
    label: "AI Agent",
    category: "ai",
    defaultData: { name: "AI Agent", handlers: [] },
  } as unknown as NodeTypeDefinition<NodeData>);
  nodeRegistry.register({
    type: "subAgentNode",
    label: "Sub-Agent",
    category: "ai",
    defaultData: { name: "Sub-Agent", mode: "single_turn", handlers: [] },
  } as unknown as NodeTypeDefinition<NodeData>);
});

const agentNode: Node = {
  id: "agent-1",
  type: "agentNode",
  position: { x: 100, y: 100 },
  data: { name: "AI Agent" },
};

describe("parseAgentActions", () => {
  it("parses as_sub_agent_for from an ADD_NODE block", () => {
    const text = `<ADD_NODE>{"node_type":"subAgentNode","label":"Flight Search","as_sub_agent_for":"agent-1"}</ADD_NODE>`;
    const { actions } = parseAgentActions(text);
    expect(actions).toHaveLength(1);
    const action = actions[0] as AddNodeAction;
    expect(action.type).toBe("add_node");
    expect(action.nodeType).toBe("subAgentNode");
    expect(action.asSubAgentFor).toBe("agent-1");
  });
});

describe("createNodeFromAction — as_sub_agent_for", () => {
  it("creates the sub-agent and a single delegation edge to the parent", () => {
    const action: AddNodeAction = {
      type: "add_node",
      nodeType: "subAgentNode",
      label: "Flight Search",
      asSubAgentFor: "agent-1",
    };
    const { nodes, edges } = createNodeFromAction(action, [agentNode]);

    expect(nodes).toHaveLength(1);
    expect(edges).toHaveLength(1);

    const child = nodes[0];
    const edge = edges[0];
    expect(edge.source).toBe(child.id);
    expect(edge.target).toBe("agent-1");
    expect(edge.sourceHandle).toBe("output_sub_agent");
    expect(edge.targetHandle).toBe("input_sub_agents");
    expect(edge.id).toBe(
      `reactflow__edge-${child.id}output_sub_agent-agent-1input_sub_agents`
    );
    expect(child.position.y).toBeGreaterThan(agentNode.position.y);
  });

  it("does not create a delegation edge when the parent is not an agent/sub-agent", () => {
    const plainNode: Node = {
      id: "tpl-1",
      type: "templateNode",
      position: { x: 0, y: 0 },
      data: {},
    };
    const action: AddNodeAction = {
      type: "add_node",
      nodeType: "subAgentNode",
      asSubAgentFor: "tpl-1",
    };
    const { edges } = createNodeFromAction(action, [plainNode]);
    expect(edges).toHaveLength(0);
  });

  it("does not create a delegation edge when the new node is not a subAgentNode", () => {
    const action: AddNodeAction = {
      type: "add_node",
      nodeType: "agentNode",
      asSubAgentFor: "agent-1",
    };
    const { edges } = createNodeFromAction(action, [agentNode]);
    expect(edges).toHaveLength(0);
  });
});

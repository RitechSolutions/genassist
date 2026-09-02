import { describe, it, expect } from "vitest";
import {
  clampToolName,
  connectedToolNodes,
  countSubAgentEdges,
  delegationToolName,
  toSnakeCase,
  validateSubAgentConnection,
  SubAgentGraphNode,
  SubAgentGraphEdge,
} from "@/views/AIAgents/Workflows/utils/subAgentGraph";

const node = (
  id: string,
  type: string,
  data: { name?: string; mode?: string } = {}
): SubAgentGraphNode => ({ id, type, data });

const delegationEdge = (child: string, parent: string): SubAgentGraphEdge => ({
  source: child,
  target: parent,
  sourceHandle: "output_sub_agent",
  targetHandle: "input_sub_agents",
});

describe("toSnakeCase", () => {
  it("mirrors the backend normalizer", () => {
    expect(toSnakeCase("My Child")).toBe("my_child");
    expect(toSnakeCase("my_child")).toBe("my_child");
    expect(toSnakeCase("FlightSearch")).toBe("flight_search");
    expect(toSnakeCase("")).toBe("");
  });

  it("collapses 'My Child' and 'my_child' to the same delegation tool name", () => {
    expect(delegationToolName("My Child")).toBe(delegationToolName("my_child"));
    expect(delegationToolName("Flight Search")).toBe("request_task_flight_search");
  });
});

describe("shared node helpers", () => {
  it("counts only sub-agent edges targeting the node", () => {
    const edges: SubAgentGraphEdge[] = [
      delegationEdge("c1", "a"),
      delegationEdge("c2", "a"),
      delegationEdge("c3", "b"),
      { source: "t", target: "a", sourceHandle: "output_tool", targetHandle: "input_tools" },
    ];
    expect(countSubAgentEdges("a", edges)).toBe(2);
    expect(countSubAgentEdges("b", edges)).toBe(1);
    expect(countSubAgentEdges("x", edges)).toBe(0);
  });

  it("returns only tool-typed nodes wired into the tools port", () => {
    const nodes = [
      node("t1", "toolBuilderNode", { name: "T1" }),
      node("t2", "toolBuilderNode", { name: "T2" }),
      node("c", "subAgentNode", { name: "C" }),
    ];
    const edges: SubAgentGraphEdge[] = [
      { source: "t1", target: "a", sourceHandle: "output_tool", targetHandle: "input_tools" },
      { source: "c", target: "a", sourceHandle: "output_sub_agent", targetHandle: "input_sub_agents" },
    ];
    const connected = connectedToolNodes("a", nodes, edges, ["toolBuilderNode"]);
    expect(connected.map((n) => n.id)).toEqual(["t1"]);
  });
});

describe("clampToolName", () => {
  it("matches the backend clamp on the shared vectors", () => {
    expect(delegationToolName("Billing/Refunds")).toBe("request_task_billing_refunds");
    expect(delegationToolName("Éclair Vérification")).toBe("request_task_eclair_verification");
    expect(delegationToolName("straße")).toBe("request_task_stra_e");
    expect(delegationToolName("Flight  Search!")).toBe("request_task_flight_search");
    expect(delegationToolName("data—sync")).toBe("request_task_data_sync");
    expect(clampToolName("中文名")).toBe("");
  });
});

describe("validateSubAgentConnection", () => {
  it("ignores connections that don't touch a sub-agent port", () => {
    const nodes = [node("a", "agentNode"), node("b", "chatOutputNode")];
    const res = validateSubAgentConnection(
      { source: "a", target: "b", sourceHandle: "output", targetHandle: "input" },
      nodes,
      []
    );
    expect(res.ok).toBe(true);
  });

  it("rejects a sub-agent output going to a non-sub-agent port", () => {
    const nodes = [node("c", "subAgentNode"), node("x", "templateNode")];
    const res = validateSubAgentConnection(
      { source: "c", target: "x", sourceHandle: "output_sub_agent", targetHandle: "input" },
      nodes,
      []
    );
    expect(res.ok).toBe(false);
  });

  it("rejects a non-sub-agent source feeding a sub-agent port", () => {
    const nodes = [node("in", "chatInputNode"), node("a", "agentNode")];
    const res = validateSubAgentConnection(
      { source: "in", target: "a", sourceHandle: "output", targetHandle: "input_sub_agents" },
      nodes,
      []
    );
    expect(res.ok).toBe(false);
  });

  it("accepts a single_turn sub-agent attached to an agent", () => {
    const nodes = [node("a", "agentNode"), node("c", "subAgentNode", { mode: "single_turn" })];
    const res = validateSubAgentConnection(delegationEdge("c", "a"), nodes, []);
    expect(res.ok).toBe(true);
  });

  it("rejects self-attachment", () => {
    const nodes = [node("c", "subAgentNode")];
    const res = validateSubAgentConnection(delegationEdge("c", "c"), nodes, []);
    expect(res.ok).toBe(false);
  });

  it("rejects a child that is not a subAgentNode", () => {
    const nodes = [node("a", "agentNode"), node("t", "toolBuilderNode")];
    const res = validateSubAgentConnection(delegationEdge("t", "a"), nodes, []);
    expect(res.ok).toBe(false);
  });

  it("rejects a parent that is not an agent or sub-agent", () => {
    const nodes = [node("tpl", "templateNode"), node("c", "subAgentNode")];
    const res = validateSubAgentConnection(delegationEdge("c", "tpl"), nodes, []);
    expect(res.ok).toBe(false);
  });

  it("rejects attaching a child that already has a parent", () => {
    const nodes = [
      node("a", "agentNode"),
      node("a2", "agentNode"),
      node("c", "subAgentNode", { mode: "single_turn" }),
    ];
    const edges = [delegationEdge("c", "a")];
    const res = validateSubAgentConnection(delegationEdge("c", "a2"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects a delegation cycle", () => {
    const nodes = [
      node("a", "subAgentNode", { mode: "single_turn" }),
      node("b", "subAgentNode", { mode: "single_turn" }),
    ];
    const edges = [delegationEdge("a", "b")];
    const res = validateSubAgentConnection(delegationEdge("b", "a"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects exceeding max delegation depth", () => {
    const nodes = [
      node("a", "agentNode"),
      node("s1", "subAgentNode", { mode: "single_turn" }),
      node("s2", "subAgentNode", { mode: "single_turn" }),
      node("s3", "subAgentNode", { mode: "single_turn" }),
    ];
    const edges = [delegationEdge("s1", "a"), delegationEdge("s2", "s1")];
    const res = validateSubAgentConnection(delegationEdge("s3", "s2"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects a task/chat sub-agent attached to another sub-agent", () => {
    const nodes = [
      node("a", "agentNode"),
      node("s1", "subAgentNode", { mode: "single_turn" }),
      node("c", "subAgentNode", { mode: "chat" }),
    ];
    const edges = [delegationEdge("s1", "a")];
    const res = validateSubAgentConnection(delegationEdge("c", "s1"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects attaching any child under a task-mode parent", () => {
    const nodes = [
      node("a", "agentNode"),
      node("p", "subAgentNode", { mode: "task" }),
      node("c", "subAgentNode", { mode: "single_turn" }),
    ];
    const edges = [delegationEdge("p", "a")];
    const res = validateSubAgentConnection(delegationEdge("c", "p"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects a sibling with a colliding delegation name", () => {
    const nodes = [
      node("a", "agentNode"),
      node("c1", "subAgentNode", { name: "My Child", mode: "single_turn" }),
      node("c2", "subAgentNode", { name: "my_child", mode: "single_turn" }),
    ];
    const edges = [delegationEdge("c1", "a")];
    const res = validateSubAgentConnection(delegationEdge("c2", "a"), nodes, edges);
    expect(res.ok).toBe(false);
  });

  it("rejects a reserved sub-agent name", () => {
    const nodes = [
      node("a", "agentNode"),
      node("c", "subAgentNode", { name: "finish_task", mode: "single_turn" }),
    ];
    const res = validateSubAgentConnection(delegationEdge("c", "a"), nodes, []);
    expect(res.ok).toBe(false);
  });

  it("falls back to the node id for the reserved-name check", () => {
    const nodes = [node("a", "agentNode"), node("finish_task", "subAgentNode")];
    const res = validateSubAgentConnection(delegationEdge("finish_task", "a"), nodes, []);
    expect(res.ok).toBe(false);
  });

  it("rejects a name that clamps to empty", () => {
    const nodes = [node("a", "agentNode"), node("c", "subAgentNode", { name: "中文名" })];
    const res = validateSubAgentConnection(delegationEdge("c", "a"), nodes, []);
    expect(res.ok).toBe(false);
    expect(res.reason).toContain("letter or number");
  });

  it("rejects a delegation name colliding with a parent tool", () => {
    const nodes = [
      node("a", "agentNode"),
      node("t", "toolBuilderNode", { name: "Request Task Billing" }),
      node("c", "subAgentNode", { name: "Billing" }),
    ];
    const edges: SubAgentGraphEdge[] = [
      { source: "t", target: "a", sourceHandle: "output_tool", targetHandle: "input_tools" },
    ];
    const res = validateSubAgentConnection(delegationEdge("c", "a"), nodes, edges);
    expect(res.ok).toBe(false);
    expect(res.reason).toContain("tool");
  });
});

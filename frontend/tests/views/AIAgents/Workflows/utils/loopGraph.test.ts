import { describe, it, expect } from "vitest";
import {
  isLoopBackEdge,
  loopBody,
  loopTopologyError,
  validateLoopConnection,
  withoutLoopBackEdges,
  LoopGraphEdge,
  LoopGraphNode,
} from "@/views/AIAgents/Workflows/utils/loopGraph";

const node = (id: string, type = "templateNode"): LoopGraphNode => ({ id, type, data: { name: id } });

const edge = (
  source: string,
  target: string,
  sourceHandle = "output",
  targetHandle = "input"
): LoopGraphEdge => ({ source, target, sourceHandle, targetHandle });

// start → loop ─body→ a → b ─back→ loop ; loop ─done→ after
const nodes = [node("start"), node("loop", "loopNode"), node("a"), node("b"), node("after"), node("other")];
const edges = [
  edge("start", "loop"),
  edge("loop", "a", "output_loop"),
  edge("a", "b"),
  edge("b", "loop", "output", "input_loop"),
  edge("loop", "after", "output_done"),
];

describe("loop body", () => {
  it("is what the Loop body output reaches, ending at the back-edge", () => {
    expect(loopBody("loop", edges)).toEqual(new Set(["a", "b"]));
  });

  it("is empty when nothing is connected to the body output", () => {
    expect(loopBody("loop", [edge("start", "loop"), edge("loop", "after", "output_done")])).toEqual(new Set());
  });

  it("includes a nested loop and its body", () => {
    const nested = [
      ...edges.filter((e) => !(e.source === "a" && e.target === "b")),
      edge("a", "inner"),
      edge("inner", "cell", "output_loop"),
      edge("cell", "inner", "output", "input_loop"),
      edge("inner", "b", "output_done"),
    ];
    expect(loopBody("loop", nested)).toEqual(new Set(["a", "inner", "cell", "b"]));
    expect(loopBody("inner", nested)).toEqual(new Set(["cell"]));
  });
});

describe("back-edges", () => {
  it("are recognised by their target handle", () => {
    expect(isLoopBackEdge(edges[3])).toBe(true);
    expect(isLoopBackEdge(edges[0])).toBe(false);
  });

  it("are dropped for layouts, leaving an acyclic graph", () => {
    expect(withoutLoopBackEdges(edges)).toHaveLength(4);
  });
});

describe("loopTopologyError", () => {
  it("accepts a correctly wired loop and workflows without one", () => {
    expect(loopTopologyError(nodes, edges)).toBeNull();
    expect(loopTopologyError([node("x"), node("y")], [edge("x", "y"), edge("y", "x")])).toBeNull();
  });

  it("rejects a Loop back connection from outside the body", () => {
    expect(loopTopologyError(nodes, [...edges, edge("other", "loop", "output", "input_loop")])).toMatch(
      /runs inside "loop"/
    );
  });

  it("rejects a Human in the Loop node in the body", () => {
    const withHitl = nodes.map((n) => (n.id === "a" ? node("a", "humanInTheLoopNode") : n));
    expect(loopTopologyError(withHitl, edges)).toMatch(/not supported inside a loop/);
  });

  describe("with an agent in the body", () => {
    const agentNodes = nodes.map((n) => (n.id === "a" ? node("a", "agentNode") : n));
    const subAgent = (id: string, mode?: string): LoopGraphNode => ({ id, type: "subAgentNode", data: { name: id, mode } });
    const delegate = (child: string, parent: string) => edge(child, parent, "output_sub_agent", "input_sub_agents");

    it("rejects a task or chat sub-agent, however deep", () => {
      for (const mode of ["task", "chat"]) {
        const problem = loopTopologyError([...agentNodes, subAgent("helper", mode)], [...edges, delegate("helper", "a")]);
        expect(problem).toMatch(/"helper" pauses the workflow .* "a" in the body of "loop" uses it/);
      }
      const deep = [...agentNodes, subAgent("helper", "single_turn"), subAgent("deep", "chat")];
      expect(loopTopologyError(deep, [...edges, delegate("helper", "a"), delegate("deep", "helper")])).toMatch(
        /"deep" pauses/
      );
    });

    it("rejects a tool whose sub-flow reaches a Human in the Loop node", () => {
      const withTool = [...agentNodes, node("tool", "toolBuilderNode"), node("fetch"), node("approve", "humanInTheLoopNode")];
      const toolEdges = [
        ...edges,
        edge("tool", "a", "output_tool", "input_tools"),
        edge("tool", "fetch", "starter_processor"),
        edge("fetch", "approve"),
      ];
      expect(loopTopologyError(withTool, toolEdges)).toMatch(/"approve" pauses the workflow .* "a" in the body/);
    });

    it("accepts tools and single-turn sub-agents", () => {
      const fine = [...agentNodes, subAgent("helper", "single_turn"), subAgent("unset"), node("tool", "toolBuilderNode"), node("fetch")];
      const fineEdges = [
        ...edges,
        delegate("helper", "a"),
        delegate("unset", "a"),
        edge("tool", "a", "output_tool", "input_tools"),
        edge("tool", "fetch", "starter_processor"),
      ];
      expect(loopTopologyError(fine, fineEdges)).toBeNull();
    });

    it("does not blame the loop for what pauses outside it", () => {
      const shared = [
        ...agentNodes,
        node("tool", "toolBuilderNode"),
        node("fetch"),
        node("outside", "agentNode"),
        node("approve", "humanInTheLoopNode"),
        subAgent("helper", "chat"),
      ];
      const sharedEdges = [
        ...edges,
        edge("tool", "a", "output_tool", "input_tools"),
        edge("tool", "outside", "output_tool", "input_tools"),
        edge("tool", "fetch", "starter_processor"),
        edge("after", "outside"),
        edge("outside", "approve"),
        delegate("helper", "outside"),
      ];
      expect(loopTopologyError(shared, sharedEdges)).toBeNull();
    });
  });

  it("rejects a body node that also feeds the Done branch", () => {
    expect(loopTopologyError(nodes, [...edges, edge("b", "after")])).toMatch(/from Done only/);
  });
});

describe("validateLoopConnection", () => {
  const withoutBack = edges.filter((e) => e.targetHandle !== "input_loop");

  it("allows closing the loop from its body", () => {
    expect(validateLoopConnection(edge("b", "loop", "output", "input_loop"), nodes, withoutBack)).toEqual({ ok: true });
  });

  it("blocks closing the loop from a node outside its body", () => {
    const check = validateLoopConnection(edge("other", "loop", "output", "input_loop"), nodes, withoutBack);
    expect(check.ok).toBe(false);
    expect(check.reason).toMatch(/runs inside "loop"/);
  });

  it("blocks a plain connection that would create a cycle", () => {
    const check = validateLoopConnection(edge("b", "a"), nodes, withoutBack);
    expect(check.ok).toBe(false);
    expect(check.reason).toMatch(/use a Loop node/);
    expect(validateLoopConnection(edge("a", "a"), nodes, withoutBack).ok).toBe(false);
  });

  it("blocks wiring the body straight into the Done branch", () => {
    expect(validateLoopConnection(edge("b", "after"), nodes, edges).ok).toBe(false);
  });

  it("allows ordinary connections, including onto the Done branch", () => {
    expect(validateLoopConnection(edge("after", "other"), nodes, edges)).toEqual({ ok: true });
    expect(validateLoopConnection(edge("other", "start"), nodes, edges)).toEqual({ ok: true });
  });

  it("does not blame a new connection for a problem that was already there", () => {
    const broken = [...edges, edge("b", "after")];
    expect(validateLoopConnection(edge("after", "other"), nodes, broken)).toEqual({ ok: true });
  });

  it("leaves sub-agent delegation edges to their own rules", () => {
    const delegation = { source: "b", target: "a", sourceHandle: "output_sub_agent", targetHandle: "input_sub_agents" };
    expect(validateLoopConnection(delegation, nodes, edges)).toEqual({ ok: true });
  });

  it("blocks attaching a sub-agent that pauses to an agent in the body", () => {
    const delegation = { source: "helper", target: "a", sourceHandle: "output_sub_agent", targetHandle: "input_sub_agents" };
    const helper = (mode: string): LoopGraphNode => ({ id: "helper", type: "subAgentNode", data: { name: "helper", mode } });
    const check = validateLoopConnection(delegation, [...nodes, helper("chat")], edges);
    expect(check.ok).toBe(false);
    expect(check.reason).toMatch(/"helper" pauses the workflow/);
    expect(validateLoopConnection(delegation, [...nodes, helper("single_turn")], edges)).toEqual({ ok: true });
  });
});

describe("loopItemSample", () => {
  const available = {
    source: { tickets: [{ id: 1, email: "a@b.co" }, { id: 2, email: "c@d.co" }], text: "plain" },
    node_outputs: { api: { rows: '[{"name": "x"}]' } },
  };

  it("is the first element of the list Items points at", async () => {
    const { loopItemSample } = await import("@/views/AIAgents/Workflows/utils/loopGraph");
    expect(loopItemSample("{{source.tickets}}", available)).toEqual({ id: 1, email: "a@b.co" });
    expect(loopItemSample(" {{ node_outputs.api.rows }} ", available)).toEqual({ name: "x" });
  });

  it("is the first batch when the loop runs in batches", async () => {
    const { loopItemSample } = await import("@/views/AIAgents/Workflows/utils/loopGraph");
    expect(loopItemSample("{{source.tickets}}", available, 2)).toHaveLength(2);
  });

  it("is undefined when the list cannot be told at design time", async () => {
    const { loopItemSample } = await import("@/views/AIAgents/Workflows/utils/loopGraph");
    expect(loopItemSample("{{source.missing}}", available)).toBeUndefined();
    expect(loopItemSample("{{source.text}}", available)).toBeUndefined();
    expect(loopItemSample("a, b, c", available)).toBeUndefined();
    expect(loopItemSample("{{source.a}} {{source.b}}", available)).toBeUndefined();
    expect(loopItemSample(undefined, available)).toBeUndefined();
  });
});

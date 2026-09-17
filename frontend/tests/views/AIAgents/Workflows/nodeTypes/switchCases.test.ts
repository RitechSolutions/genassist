import { describe, it, expect, beforeAll } from "vitest";
import { Node } from "reactflow";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import {
  NodeData,
  NodeTypeDefinition,
  SwitchNodeData,
} from "@/views/AIAgents/Workflows/types/nodes";
import {
  buildSwitchHandlers,
  canAddSwitchCase,
  DEFAULT_SWITCH_CASES,
  isSwitchSmartMode,
  MAX_SWITCH_CASES,
  MAX_SWITCH_OUTPUTS,
  nextSwitchCaseId,
  SWITCH_DEFAULT_HANDLE_ID,
  switchCaseHandleId,
} from "@/views/AIAgents/Workflows/nodeTypes/router/switchCases";

const cases = [
  { id: "case_1", label: "Billing", value: "billing" },
  { id: "case_3", label: "", value: "sales" },
];

describe("buildSwitchHandlers", () => {
  it("puts the input first, one output per case in order, then the default", () => {
    const handlers = buildSwitchHandlers(cases);
    expect(handlers.map((h) => h.id)).toEqual([
      "input",
      "output_case_1",
      "output_case_3",
      SWITCH_DEFAULT_HANDLE_ID,
    ]);
    expect(handlers[0]).toMatchObject({ type: "target", position: "left" });
    expect(handlers.slice(1).every((h) => h.type === "source" && h.position === "right")).toBe(true);
  });

  it("labels each output by its case, falling back to the case position", () => {
    const labels = buildSwitchHandlers(cases).map((h) => h.label);
    expect(labels).toEqual([undefined, "Billing", "Case 2", "Default"]);
  });

  it("keeps the input and default handles when there are no cases", () => {
    expect(buildSwitchHandlers([]).map((h) => h.id)).toEqual(["input", "output_default"]);
  });
});

describe("switch case limit", () => {
  const casesOf = (n: number) =>
    Array.from({ length: n }, (_, i) => ({ id: `case_${i + 1}`, label: "", value: "" }));

  it("allows 5 cases, so a node has at most 6 outputs including Default", () => {
    expect(MAX_SWITCH_CASES).toBe(5);
    expect(MAX_SWITCH_OUTPUTS).toBe(6);
    expect(canAddSwitchCase(casesOf(4))).toBe(true);
    expect(canAddSwitchCase(casesOf(5))).toBe(false);
    expect(canAddSwitchCase(casesOf(7))).toBe(false);
    // Output handles at the limit: input + 5 cases + default.
    const outputs = buildSwitchHandlers(casesOf(MAX_SWITCH_CASES)).filter((h) => h.type === "source");
    expect(outputs).toHaveLength(MAX_SWITCH_OUTPUTS);
  });
});

describe("isSwitchSmartMode", () => {
  it("accepts a boolean or a persisted \"true\" string", () => {
    expect(isSwitchSmartMode(true)).toBe(true);
    expect(isSwitchSmartMode(" TRUE ")).toBe(true);
    expect(isSwitchSmartMode(false)).toBe(false);
    expect(isSwitchSmartMode("false")).toBe(false);
    expect(isSwitchSmartMode(undefined)).toBe(false);
  });
});

describe("switch case ids", () => {
  it("maps a case id to the handle the engine follows", () => {
    expect(switchCaseHandleId("case_7")).toBe("output_case_7");
  });

  it("picks the next id after the highest existing number, never reusing a gap", () => {
    expect(nextSwitchCaseId([])).toBe("case_1");
    expect(nextSwitchCaseId(cases)).toBe("case_4");
    expect(nextSwitchCaseId([{ id: "custom", label: "", value: "" }])).toBe("case_1");
  });
});

describe("nodeRegistry with config-derived handles", () => {
  beforeAll(() => {
    nodeRegistry.register({
      type: "switchNode",
      label: "Switch",
      category: "routing",
      defaultData: {
        name: "Switch",
        cases: DEFAULT_SWITCH_CASES,
        handlers: buildSwitchHandlers(DEFAULT_SWITCH_CASES),
      },
      getHandlers: (data: SwitchNodeData) => buildSwitchHandlers(data.cases ?? []),
    } as unknown as NodeTypeDefinition<NodeData>);
  });

  it("hydrates handles from the saved cases instead of re-adding removed defaults", () => {
    const saved: Node = {
      id: "sw",
      type: "switchNode",
      position: { x: 0, y: 0 },
      data: {
        name: "Switch",
        cases: [DEFAULT_SWITCH_CASES[1]],
        handlers: buildSwitchHandlers([DEFAULT_SWITCH_CASES[1]]),
      },
    };
    const hydrated = nodeRegistry.hydrateNode(saved);
    expect(hydrated.data.handlers.map((h: { id: string }) => h.id)).toEqual([
      "input",
      "output_case_2",
      "output_default",
    ]);
  });

  it("builds handles from override cases when creating a node", () => {
    const node = nodeRegistry.createNode("switchNode", "sw", { x: 0, y: 0 }, {
      cases: [{ id: "case_9", label: "VIP", value: "vip" }],
    });
    expect(node?.data.handlers.map((h: { id: string }) => h.id)).toEqual([
      "input",
      "output_case_9",
      "output_default",
    ]);
  });
});

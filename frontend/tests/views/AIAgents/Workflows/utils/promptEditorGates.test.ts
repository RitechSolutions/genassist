import { describe, expect, it } from "vitest";
import { promptEditorCapabilities } from "@/views/AIAgents/Workflows/utils/promptEditorCapabilities";
import {
  acceptGate,
  evaluateGate,
  optimizeGate,
  saveGate,
  type CasesState,
  type EvalInputs,
  type HistoryState,
} from "@/views/AIAgents/Workflows/utils/promptEditorGates";

const ADMIN = promptEditorCapabilities(["*"]);
const NONE = promptEditorCapabilities([]);

const ready = (overrides: Partial<HistoryState> = {}): HistoryState => ({
  status: "ready",
  nodeMissing: false,
  inlineCheckSupported: true,
  unsupportedReason: null,
  goldSuiteId: "suite-1",
  ...overrides,
});

const cases = (overrides: Partial<CasesState> = {}): CasesState => ({
  status: "success",
  count: 3,
  ...overrides,
});

const run = (overrides: Partial<EvalInputs> = {}): EvalInputs => ({
  content: "draft",
  contentNoun: "prompt",
  providerStatus: "ready",
  providerId: "provider-1",
  techniqueCount: 1,
  ...overrides,
});

const GATES = [
  { name: "save", run: (h: HistoryState) => saveGate(h, ADMIN, "draft") },
  { name: "evaluate", run: (h: HistoryState) => evaluateGate(h, cases(), ADMIN, run()) },
  { name: "optimize", run: (h: HistoryState) => optimizeGate(h, ADMIN, run()) },
  { name: "accept", run: (h: HistoryState) => acceptGate(h, ADMIN, false, "suggested") },
];

const WITHOUT_CAPABILITY = [
  { name: "save", gate: saveGate(ready(), NONE, "draft") },
  { name: "evaluate", gate: evaluateGate(ready(), cases(), NONE, run()) },
  { name: "optimize", gate: optimizeGate(ready(), NONE, run()) },
  { name: "accept", gate: acceptGate(ready(), NONE, false, "suggested") },
];

describe("prompt editor gates", () => {
  it.each(GATES)("$name is enabled on a ready live node", ({ run }) => {
    expect(run(ready())).toEqual({ enabled: true, reason: null });
  });

  it.each(GATES)("$name is blocked while history is pending", ({ run }) => {
    expect(run(ready({ status: "pending" })).enabled).toBe(false);
  });

  it.each(GATES)("$name is blocked when history failed", ({ run }) => {
    expect(run(ready({ status: "error" })).enabled).toBe(false);
  });

  it.each(GATES)("$name is blocked when history is forbidden", ({ run }) => {
    expect(run(ready({ status: "forbidden" })).enabled).toBe(false);
  });

  it.each(GATES)("$name is blocked when the node is missing", ({ run }) => {
    const gate = run(ready({ nodeMissing: true }));

    expect(gate.enabled).toBe(false);
    expect(gate.reason).toMatch(/Save the workflow/);
  });

  it.each(WITHOUT_CAPABILITY)(
    "$name is blocked without its permission",
    ({ gate }) => {
      expect(gate.enabled).toBe(false);
      expect(gate.reason).toMatch(/permission/);
    },
  );
});

describe("unsupported inline check", () => {
  const unsupported = ready({
    inlineCheckSupported: false,
    unsupportedReason: "Not run as a system prompt.",
  });

  it("blocks evaluate and optimize with the field's own reason", () => {
    expect(evaluateGate(unsupported, cases(), ADMIN, run())).toEqual({
      enabled: false,
      reason: "Not run as a system prompt.",
    });
    expect(optimizeGate(unsupported, ADMIN, run())).toEqual({
      enabled: false,
      reason: "Not run as a system prompt.",
    });
  });

  it("leaves version saving and accepting available", () => {
    expect(saveGate(unsupported, ADMIN, "draft").enabled).toBe(true);
    expect(acceptGate(unsupported, ADMIN, false, "suggested").enabled).toBe(true);
  });
});

describe("saveGate", () => {
  it("blocks a blank draft", () => {
    expect(saveGate(ready(), ADMIN, "   ").enabled).toBe(false);
  });

  it("blocks a draft over the body bound", () => {
    expect(saveGate(ready(), ADMIN, "x".repeat(200_001)).enabled).toBe(false);
    expect(saveGate(ready(), ADMIN, "x".repeat(200_000)).enabled).toBe(true);
  });
});

describe("evaluateGate", () => {
  it("needs a linked gold dataset", () => {
    const gate = evaluateGate(ready({ goldSuiteId: null }), cases(), ADMIN, run());

    expect(gate.enabled).toBe(false);
    expect(gate.reason).toMatch(/gold dataset/i);
  });

  it("blocks an empty dataset and allows a populated one", () => {
    expect(
      evaluateGate(ready(), cases({ status: "success", count: 0 }), ADMIN, run()).enabled,
    ).toBe(false);
    expect(
      evaluateGate(ready(), cases({ status: "success", count: 3 }), ADMIN, run()).enabled,
    ).toBe(true);
  });

  it("waits while the cases are loading", () => {
    const gate = evaluateGate(ready(), cases({ status: "pending", count: 0 }), ADMIN, run());

    expect(gate.enabled).toBe(false);
    expect(gate.reason).toMatch(/Loading cases/);
  });

  it.each(["idle", "error", "forbidden"] as const)(
    "leaves the decision to the server when the cases are %s",
    (status) => {
      expect(evaluateGate(ready(), cases({ status, count: 0 }), ADMIN, run()).enabled).toBe(
        true,
      );
    },
  );
});

describe("run inputs", () => {
  const evaluate = (overrides: Partial<EvalInputs>) =>
    evaluateGate(ready(), cases(), ADMIN, run(overrides));

  it("waits for the provider list and reports a failed load", () => {
    expect(evaluate({ providerStatus: "pending", providerId: "" }).reason).toMatch(
      /Loading LLM providers/,
    );
    expect(evaluate({ providerStatus: "error", providerId: "" }).reason).toMatch(
      /could not be loaded/,
    );
  });

  it("blocks a provider that is no longer active", () => {
    const gate = evaluate({ providerId: "" });

    expect(gate.enabled).toBe(false);
    expect(gate.reason).toMatch(/Select an LLM provider/);
  });

  it("blocks evaluation without a technique", () => {
    expect(evaluate({ techniqueCount: 0 }).reason).toMatch(/technique/);
  });

  it("names the content it blocks on", () => {
    expect(evaluate({ content: "  " }).reason).toBe("The prompt is empty.");
    expect(
      evaluate({ content: "  ", contentNoun: "suggested prompt" }).reason,
    ).toBe("The suggested prompt is empty.");
  });

  it("leaves the version-body length limit to save and accept", () => {
    const long = "x".repeat(200_001);

    expect(evaluate({ content: long }).enabled).toBe(true);
    expect(optimizeGate(ready(), ADMIN, run({ content: long })).enabled).toBe(
      true,
    );
    expect(saveGate(ready(), ADMIN, long).enabled).toBe(false);
    expect(acceptGate(ready(), ADMIN, false, long).enabled).toBe(false);
  });

  it("does not ask optimize for techniques", () => {
    expect(
      optimizeGate(ready(), ADMIN, run({ techniqueCount: 0 })).enabled,
    ).toBe(true);
  });
});

describe("acceptGate", () => {
  it("blocks while a save is already running", () => {
    expect(acceptGate(ready(), ADMIN, true, "suggested").enabled).toBe(false);
  });

  it("applies the save contract to the suggestion, not the draft", () => {
    const blank = acceptGate(ready(), ADMIN, false, "   ");

    expect(blank.enabled).toBe(false);
    expect(blank.reason).toMatch(/suggested prompt is empty/);
    expect(acceptGate(ready(), ADMIN, false, "x".repeat(200_001)).enabled).toBe(
      false,
    );
    expect(acceptGate(ready(), ADMIN, false, "x".repeat(200_000)).enabled).toBe(
      true,
    );
  });
});

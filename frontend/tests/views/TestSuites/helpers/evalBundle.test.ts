import { describe, expect, it } from "vitest";
import {
  bundleFilename,
  bundleSetFilename,
  apiErrorDetail,
  catalogOptionsForKind,
  buildNodeTypeIndex,
  narrowToOriginalType,
  nodeRefKey,
  parseBundleFile,
  bundleSetCaseCount,
} from "@/views/TestSuites/helpers/evalBundle";
import {
  EVALUATION_BUNDLE_KIND,
  EVALUATION_BUNDLE_SET_KIND,
} from "@/interfaces/evalBundle.interface";
import type { BundleRefCandidate } from "@/interfaces/evalBundle.interface";
import type { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";

const catalog: EvaluationToolCatalog = {
  workflow_id: "wf",
  agents: [
    {
      id: "agent-1",
      label: "Agent One",
      type: "agentNode",
      workflow_path: [],
      tools: [
        { id: "tool-1", name: "t1", label: "Tool One", type: "toolNode" },
        { id: "tool-2", name: "t2", label: "Tool Two", type: "" },
      ],
    },
    {
      id: "agent-2",
      label: "Agent Two",
      type: "agentNode",
      workflow_path: [],
      tools: [
        { id: "tool-1", name: "t1", label: "Tool One (dup)", type: "toolNode" },
        { id: "tool-3", name: "t3", label: "Tool Three", type: "httpToolNode" },
      ],
    },
  ],
  routers: [
    { id: "router-1", label: "Router One", workflow_path: [], branches: [] },
  ],
  action_nodes: [
    { id: "node-1", label: "Node One", type: "httpNode", workflow_path: [] },
    { id: "node-2", label: "Node Two", type: "", workflow_path: [] },
  ],
};

describe("bundleFilename", () => {
  it("slugifies the evaluation name into the filename", () => {
    expect(bundleFilename("My Eval 1")).toBe("evaluation-my-eval-1.json");
  });

  it("collapses non-alphanumeric runs and strips leading/trailing dashes", () => {
    expect(bundleFilename("Hello, World!")).toBe("evaluation-hello-world.json");
    expect(bundleFilename("A_B C")).toBe("evaluation-a-b-c.json");
  });

  it("falls back to 'bundle' when the name slugifies to empty", () => {
    expect(bundleFilename("")).toBe("evaluation-bundle.json");
    expect(bundleFilename("   ")).toBe("evaluation-bundle.json");
    expect(bundleFilename("!!!")).toBe("evaluation-bundle.json");
  });
});

describe("bundleSetFilename", () => {
  it("slugifies the workflow name into the filename", () => {
    expect(bundleSetFilename("Support Bot")).toBe("evaluations-support-bot.json");
  });

  it("falls back to 'workflow' when the name slugifies to empty", () => {
    expect(bundleSetFilename("")).toBe("evaluations-workflow.json");
    expect(bundleSetFilename("***")).toBe("evaluations-workflow.json");
  });
});

describe("apiErrorDetail", () => {
  it("prefers error_detail over the generic error message", () => {
    expect(
      apiErrorDetail({
        response: { data: { error_detail: "ref missing", error: "generic" } },
      }),
    ).toBe("ref missing");
  });

  it("falls back to error when error_detail is absent", () => {
    expect(
      apiErrorDetail({ response: { data: { error: "generic" } } }),
    ).toBe("generic");
  });

  it("skips a blank error_detail and uses error", () => {
    expect(
      apiErrorDetail({
        response: { data: { error_detail: "   ", error: "generic" } },
      }),
    ).toBe("generic");
  });

  it("skips a non-string error_detail and uses error", () => {
    expect(
      apiErrorDetail({
        response: { data: { error_detail: 123, error: "generic" } },
      }),
    ).toBe("generic");
  });

  it("returns the candidate untrimmed when it is a non-blank string", () => {
    expect(
      apiErrorDetail({ response: { data: { error_detail: "  keep  " } } }),
    ).toBe("  keep  ");
  });

  it("returns undefined when there is no usable detail", () => {
    expect(apiErrorDetail({})).toBeUndefined();
    expect(apiErrorDetail(undefined)).toBeUndefined();
    expect(apiErrorDetail(null)).toBeUndefined();
    expect(apiErrorDetail({ response: { data: {} } })).toBeUndefined();
  });
});

describe("catalogOptionsForKind", () => {
  it("returns an empty array for a null catalog", () => {
    expect(catalogOptionsForKind(null, "tool")).toEqual([]);
    expect(catalogOptionsForKind(null, "agent")).toEqual([]);
  });

  it("flattens and de-duplicates tools by id for kind 'tool'", () => {
    expect(catalogOptionsForKind(catalog, "tool")).toEqual([
      { id: "tool-1", label: "Tool One" },
      { id: "tool-2", label: "Tool Two" },
      { id: "tool-3", label: "Tool Three" },
    ]);
  });

  it("returns agent options for kind 'agent'", () => {
    expect(catalogOptionsForKind(catalog, "agent")).toEqual([
      { id: "agent-1", label: "Agent One" },
      { id: "agent-2", label: "Agent Two" },
    ]);
  });

  it("returns router options for kind 'router'", () => {
    expect(catalogOptionsForKind(catalog, "router")).toEqual([
      { id: "router-1", label: "Router One" },
    ]);
  });

  it("returns action-node options for any other kind (default branch)", () => {
    const expected = [
      { id: "node-1", label: "Node One" },
      { id: "node-2", label: "Node Two" },
    ];
    expect(catalogOptionsForKind(catalog, "action")).toEqual(expected);
    expect(catalogOptionsForKind(catalog, "something-else")).toEqual(expected);
  });
});

describe("buildNodeTypeIndex", () => {
  it("returns an empty object for a null catalog", () => {
    expect(buildNodeTypeIndex(null)).toEqual({});
  });

  it("indexes agent, tool, and action-node types, omitting routers and empty types", () => {
    expect(buildNodeTypeIndex(catalog)).toEqual({
      "agent-1": "agentNode",
      "agent-2": "agentNode",
      "tool-1": "toolNode",
      "tool-3": "httpToolNode",
      "node-1": "httpNode",
    });
  });
});

describe("narrowToOriginalType", () => {
  const options: BundleRefCandidate[] = [
    { id: "a", label: "A" },
    { id: "b", label: "B" },
  ];

  it("returns null when the original type is missing", () => {
    expect(narrowToOriginalType(options, null, { a: "X", b: "Y" })).toBeNull();
    expect(narrowToOriginalType(options, "", { a: "X", b: "Y" })).toBeNull();
  });

  it("returns null when no types are known", () => {
    expect(narrowToOriginalType(options, "X", {})).toBeNull();
  });

  it("narrows to options matching the original type", () => {
    expect(narrowToOriginalType(options, "X", { a: "X", b: "Y" })).toEqual([
      { id: "a", label: "A" },
    ]);
  });

  it("returns null when narrowing keeps every option (says nothing)", () => {
    expect(narrowToOriginalType(options, "X", { a: "X", b: "X" })).toBeNull();
  });

  it("returns a meaningful empty array when no option matches", () => {
    expect(narrowToOriginalType(options, "X", { a: "Y", b: "Y" })).toEqual([]);
  });

  it("keeps alwaysKeep ids regardless of their type", () => {
    expect(
      narrowToOriginalType(options, "X", { a: "Y", b: "Y" }, [
        { id: "b", label: "B" },
      ]),
    ).toEqual([{ id: "b", label: "B" }]);
  });

  it("returns null for empty options (nothing to narrow)", () => {
    expect(narrowToOriginalType([], "X", { a: "X" })).toBeNull();
  });
});

describe("nodeRefKey", () => {
  it("joins kind and ref with a colon", () => {
    expect(nodeRefKey({ ref: "n1", kind: "agent" })).toBe("agent:n1");
    expect(nodeRefKey({ ref: "n1", kind: "action" })).toBe("action:n1");
  });
});

describe("parseBundleFile", () => {
  it("throws on invalid JSON", () => {
    expect(() => parseBundleFile("{not json")).toThrow(
      "The file is not valid JSON.",
    );
  });

  it("throws on an unknown or missing kind", () => {
    expect(() => parseBundleFile(JSON.stringify({ kind: "other" }))).toThrow(
      "The file is not an evaluation bundle export.",
    );
    expect(() => parseBundleFile(JSON.stringify({ foo: 1 }))).toThrow(
      "The file is not an evaluation bundle export.",
    );
  });

  it("parses and normalizes a single bundle, filling optional collections", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_KIND,
        schema_version: 1,
        source: {},
        evaluation: { name: "My Eval" },
        dataset: { name: "My DS" },
      }),
    );
    expect(parsed.kind).toBe("single");
    if (parsed.kind !== "single") throw new Error("expected single");
    expect(parsed.bundle.notes).toEqual([]);
    expect(parsed.bundle.evaluation.techniques).toEqual([]);
    expect(parsed.bundle.dataset.cases).toEqual([]);
    expect(parsed.bundle.references).toEqual({
      nodes: {},
      llm_providers: {},
      cases: {},
    });
    expect(parsed.bundle.evaluation.name).toBe("My Eval");
  });

  it("preserves provided arrays and references on a single bundle", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_KIND,
        schema_version: 1,
        source: {},
        evaluation: { name: "E", techniques: ["exact_match"] },
        dataset: { name: "D", cases: [{ local_id: 1 }, { local_id: 2 }] },
        references: { nodes: { n1: {} }, llm_providers: {}, cases: {} },
        notes: ["a note"],
      }),
    );
    if (parsed.kind !== "single") throw new Error("expected single");
    expect(parsed.bundle.evaluation.techniques).toEqual(["exact_match"]);
    expect(parsed.bundle.dataset.cases).toHaveLength(2);
    expect(parsed.bundle.notes).toEqual(["a note"]);
    expect(parsed.bundle.references.nodes).toEqual({ n1: {} });
  });

  it("throws when a single bundle lacks an evaluation or dataset name", () => {
    expect(() =>
      parseBundleFile(
        JSON.stringify({
          kind: EVALUATION_BUNDLE_KIND,
          evaluation: {},
          dataset: { name: "D" },
        }),
      ),
    ).toThrow("The file is not an evaluation bundle export.");
    expect(() =>
      parseBundleFile(
        JSON.stringify({
          kind: EVALUATION_BUNDLE_KIND,
          evaluation: { name: "E" },
          dataset: {},
        }),
      ),
    ).toThrow("The file is not an evaluation bundle export.");
  });

  it("parses and normalizes a bundle set", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_SET_KIND,
        schema_version: 1,
        source: {},
        datasets: [{ local_id: 1, name: "DS" }],
        evaluations: [
          { evaluation: { name: "E" }, dataset_local_id: 1, references: {} },
        ],
      }),
    );
    expect(parsed.kind).toBe("set");
    if (parsed.kind !== "set") throw new Error("expected set");
    expect(parsed.bundleSet.notes).toEqual([]);
    expect(parsed.bundleSet.datasets[0].cases).toEqual([]);
    expect(parsed.bundleSet.evaluations[0].notes).toEqual([]);
    expect(parsed.bundleSet.evaluations[0].evaluation.techniques).toEqual([]);
    expect(parsed.bundleSet.evaluations[0].references).toEqual({
      nodes: {},
      llm_providers: {},
      cases: {},
    });
  });

  it("accepts a set with an empty datasets array (vacuous name check)", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_SET_KIND,
        schema_version: 1,
        source: {},
        datasets: [],
        evaluations: [{ evaluation: { name: "E" }, references: {} }],
      }),
    );
    if (parsed.kind !== "set") throw new Error("expected set");
    expect(parsed.bundleSet.datasets).toEqual([]);
  });

  it("throws on a set with no evaluations", () => {
    expect(() =>
      parseBundleFile(
        JSON.stringify({
          kind: EVALUATION_BUNDLE_SET_KIND,
          datasets: [{ local_id: 1, name: "DS" }],
          evaluations: [],
        }),
      ),
    ).toThrow("The file is not an evaluation bundle export.");
  });

  it("throws on a set with a nameless dataset or a nameless evaluation", () => {
    expect(() =>
      parseBundleFile(
        JSON.stringify({
          kind: EVALUATION_BUNDLE_SET_KIND,
          datasets: [{ local_id: 1 }],
          evaluations: [{ evaluation: { name: "E" } }],
        }),
      ),
    ).toThrow("The file is not an evaluation bundle export.");
    expect(() =>
      parseBundleFile(
        JSON.stringify({
          kind: EVALUATION_BUNDLE_SET_KIND,
          datasets: [],
          evaluations: [{ evaluation: {} }],
        }),
      ),
    ).toThrow("The file is not an evaluation bundle export.");
  });
});

describe("bundleSetCaseCount", () => {
  it("sums case counts across all datasets", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_SET_KIND,
        schema_version: 1,
        source: {},
        datasets: [
          { local_id: 1, name: "A", cases: [{ local_id: 1 }, { local_id: 2 }] },
          { local_id: 2, name: "B", cases: [{ local_id: 3 }] },
        ],
        evaluations: [
          { evaluation: { name: "E" }, dataset_local_id: 1, references: {} },
        ],
      }),
    );
    if (parsed.kind !== "set") throw new Error("expected set");
    expect(bundleSetCaseCount(parsed.bundleSet)).toBe(3);
  });

  it("is zero when there are no datasets", () => {
    const parsed = parseBundleFile(
      JSON.stringify({
        kind: EVALUATION_BUNDLE_SET_KIND,
        schema_version: 1,
        source: {},
        datasets: [],
        evaluations: [{ evaluation: { name: "E" }, references: {} }],
      }),
    );
    if (parsed.kind !== "set") throw new Error("expected set");
    expect(bundleSetCaseCount(parsed.bundleSet)).toBe(0);
  });
});

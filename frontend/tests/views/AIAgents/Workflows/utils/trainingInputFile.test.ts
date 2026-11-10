import { describe, it, expect } from "vitest";
import type { Edge, Node } from "reactflow";
import type { NodeExecutionResult } from "@/views/AIAgents/Workflows/context/WorkflowExecutionContext";
import {
  SOURCE_DATA_PATH,
  STALE_INPUT_KEY,
  newerOutput,
  resolveTrainingInputFile,
  testNodeSettingsKey,
  upstreamSourcesKey,
} from "@/views/AIAgents/Workflows/utils/trainingInputFile";
import { collectRunOutputs, resumedRunWorkflow } from "@/views/AIAgents/Workflows/utils/executionView";
import type { Workflow } from "@/interfaces/workflow.interface";

const sourceNode = (data: Record<string, unknown>): Node => ({
  id: "src",
  type: "trainDataSourceNode",
  position: { x: 0, y: 0 },
  data: { name: "Train Data Source", ...data },
});
const prepNode: Node = {
  id: "prep",
  type: "preprocessingNode",
  position: { x: 0, y: 0 },
  data: { name: "Data Preprocessing" },
};
const edge: Edge = { id: "e1", source: "src", target: "prep" };

const output = (
  data: Record<string, unknown>,
  extra: Partial<NodeExecutionResult> = {}
): NodeExecutionResult => ({
  status: "success",
  output: data,
  timestamp: 1,
  nodeType: "trainDataSourceNode",
  nodeName: "Train Data Source",
  ...extra,
});

const resolve = (
  source: Node,
  latest?: NodeExecutionResult,
  fileUrl = SOURCE_DATA_PATH,
  fillVariables: (url: string) => string = (url) => url
) =>
  resolveTrainingInputFile({
    fileUrl,
    nodeId: "prep",
    nodes: [source, prepNode],
    edges: [edge],
    getLatestOutput: (id) => (id === "src" ? latest : undefined),
    fillVariables,
  });

/** The key a run of the source records, given the source's settings at the time. */
const keyFor = (source: Node) => upstreamSourcesKey(source.id, [source, prepNode], [edge]);

const dbSource = sourceNode({ sourceType: "datasource", dataSourceId: "ds1", query: "select 1" });

describe("resolveTrainingInputFile - DP-15: never send an unfilled placeholder", () => {
  it("uses the uploaded CSV path from the source's settings before the source has run", () => {
    const result = resolve(
      sourceNode({
        sourceType: "csv",
        csvFilePath: "/data/train/sales.csv",
        csvFileId: "f-1",
        csvFileName: "sales.csv",
      })
    );
    // Path only: a file id makes analyze-csv read a temp copy that step
    // previews (python_code) can't open.
    expect(result).toEqual({ ok: true, fileUrl: "/data/train/sales.csv" });
  });

  it("asks to run the source first when only a run knows the file", () => {
    const result = resolve(dbSource);
    expect(result).toEqual({
      ok: false,
      message: "Run the Train Data Source node first, then try again.",
    });
  });

  it("does not read an Excel upload as a CSV - it needs the source's run", () => {
    const excel = sourceNode({
      sourceType: "csv",
      csvFilePath: "/data/train/sales.xlsx",
      csvFileName: "sales.xlsx",
    });
    expect(resolve(excel).ok).toBe(false);
    const key = keyFor(excel);
    expect(resolve(excel, output({ data_path: "/tmp/run.csv" }, { settingsKey: key }))).toEqual({
      ok: true,
      fileUrl: "/tmp/run.csv",
    });
  });

  it("refuses any other placeholder that can't be filled", () => {
    const result = resolve(dbSource, undefined, "{{source.other_path}}");
    expect(result.ok).toBe(false);
    if (result.ok === false) expect(result.message).toContain("{{source.other_path}}");
  });

  it("fills other placeholders from the data available to the node", () => {
    const result = resolve(dbSource, undefined, "/data/{{session.file}}", () => "/data/a.csv");
    expect(result).toEqual({ ok: true, fileUrl: "/data/a.csv" });
  });

  it("asks to connect a source when nothing feeds the node", () => {
    const result = resolveTrainingInputFile({
      fileUrl: SOURCE_DATA_PATH,
      nodeId: "prep",
      nodes: [prepNode],
      edges: [],
      getLatestOutput: () => undefined,
      fillVariables: (url) => url,
    });
    expect(result.ok).toBe(false);
  });

  it("uses a non-source upstream node's latest output", () => {
    const train: Node = { id: "train", type: "trainModelNode", position: { x: 0, y: 0 }, data: {} };
    const result = resolveTrainingInputFile({
      fileUrl: SOURCE_DATA_PATH,
      nodeId: "train",
      nodes: [prepNode, train],
      edges: [{ id: "e2", source: "prep", target: "train" }],
      getLatestOutput: (id) =>
        id === "prep" ? output({ data_path: "/tmp/prep.csv" }, { nodeType: "preprocessingNode" }) : undefined,
      fillVariables: (url) => url,
    });
    expect(result).toEqual({ ok: true, fileUrl: "/tmp/prep.csv" });
  });
});

describe("resolveTrainingInputFile - DP-16: never an old source file", () => {
  it("follows a swapped CSV even when an older run output exists", () => {
    const swapped = sourceNode({ sourceType: "csv", csvFilePath: "/data/train/new.csv", csvFileName: "new.csv" });
    const result = resolve(swapped, output({ data_path: "/tmp/old.csv" }));
    expect(result.ok && result.fileUrl).toBe("/data/train/new.csv");
  });

  it("uses the run output made from the source's current settings", () => {
    const key = keyFor(dbSource);
    expect(resolve(dbSource, output({ data_path: "/tmp/q.csv" }, { settingsKey: key }))).toEqual({
      ok: true,
      fileUrl: "/tmp/q.csv",
    });
  });

  it("ignores a run output made before the source's settings changed", () => {
    const oldKey = keyFor(sourceNode({ ...dbSource.data, query: "select 0" }));
    const result = resolve(dbSource, output({ data_path: "/tmp/old.csv" }, { settingsKey: oldKey }));
    expect(result).toEqual({
      ok: false,
      message:
        "The Train Data Source settings changed since it last ran. Run the Train Data Source node again, then try again.",
    });
  });

  it("asks to refresh an output recorded before settings were tracked", () => {
    expect(resolve(dbSource, output({ data_path: "/tmp/legacy.csv" }))).toEqual({
      ok: false,
      message: "Run the Train Data Source node again to refresh its output, then try again.",
    });
  });

  it("notices a source swapped behind a Preprocessing node", () => {
    const train: Node = { id: "train", type: "trainModelNode", position: { x: 0, y: 0 }, data: {} };
    const toTrain: Edge = { id: "e2", source: "prep", target: "train" };
    const graph = (source: Node) => ({ nodes: [source, prepNode, train], edges: [edge, toTrain] });
    const before = sourceNode({ sourceType: "csv", csvFilePath: "/data/v1.csv", csvFileName: "v1.csv" });
    const after = sourceNode({ sourceType: "csv", csvFilePath: "/data/v2.csv", csvFileName: "v2.csv" });
    const prepOutput = output(
      { data_path: "/tmp/prep_v1.csv" },
      {
        nodeType: "preprocessingNode",
        settingsKey: upstreamSourcesKey("prep", graph(before).nodes, graph(before).edges),
      }
    );
    const run = (source: Node) =>
      resolveTrainingInputFile({
        fileUrl: SOURCE_DATA_PATH,
        nodeId: "train",
        ...graph(source),
        getLatestOutput: (id) => (id === "prep" ? prepOutput : undefined),
        fillVariables: (url) => url,
      });
    expect(run(before)).toEqual({ ok: true, fileUrl: "/tmp/prep_v1.csv" });
    expect(run(after)).toEqual({
      ok: false,
      message:
        "The training data changed since the Data Preprocessing node last ran. Run the whole workflow again, or test each node from the Train Data Source down to the Data Preprocessing node again, then try again.",
    });
  });

  it("treats several edges from the same node as one input", () => {
    const csv = sourceNode({ sourceType: "csv", csvFilePath: "/data/a.csv", csvFileName: "a.csv" });
    const result = resolveTrainingInputFile({
      fileUrl: SOURCE_DATA_PATH,
      nodeId: "prep",
      nodes: [csv, prepNode],
      edges: [edge, { ...edge, id: "e1b", sourceHandle: "other" }],
      getLatestOutput: () => undefined,
      fillVariables: (url) => url,
    });
    expect(result.ok && result.fileUrl).toBe("/data/a.csv");
  });

  it("picks the newer of a Test Node and a whole-run output", () => {
    const older = output({ data_path: "/a" }, { timestamp: 1 });
    const newer = output({ data_path: "/b" }, { timestamp: 2 });
    expect(newerOutput(older, newer)).toBe(newer);
    expect(newerOutput(newer, older)).toBe(newer);
    expect(newerOutput(undefined, older)).toBe(older);
  });
});

describe("collectRunOutputs", () => {
  it("keeps completed node outputs from a whole run, tagged with the source settings", () => {
    const workflow = { nodes: [dbSource, prepNode], edges: [edge] } as unknown as Workflow;
    const response = {
      state: {
        nodeExecutionStatus: {
          src: { status: "success", type: "trainDataSourceNode", output: { data_path: "/tmp/run.csv" } },
          prep: { status: "failed", type: "preprocessingNode", output: { error: "x" } },
        },
      },
    };
    const outputs = collectRunOutputs(response, workflow);
    expect(Object.keys(outputs)).toEqual(["src"]);
    expect(outputs.src.output).toEqual({ data_path: "/tmp/run.csv" });
    expect(outputs.src.settingsKey).toBe(keyFor(dbSource));
  });

  it("never throws on a malformed response", () => {
    expect(collectRunOutputs(null)).toEqual({});
    expect(collectRunOutputs({ state: "nope" })).toEqual({});
  });
});

describe("testNodeSettingsKey - a Test Node result is only as current as its inputs", () => {
  const v1 = sourceNode({ sourceType: "csv", csvFilePath: "/data/v1.csv", csvFileName: "v1.csv" });
  const v2 = sourceNode({ sourceType: "csv", csvFilePath: "/data/v2.csv", csvFileName: "v2.csv" });
  const testOutputs = (outputs: Record<string, NodeExecutionResult>) => (id: string) => outputs[id];

  it("gets the current settings when its input was made from them", () => {
    const tested = output({ data_path: "/tmp/v2.csv" }, { settingsKey: keyFor(v2) });
    expect(testNodeSettingsKey("prep", [v2, prepNode], [edge], testOutputs({ src: tested }))).toBe(
      upstreamSourcesKey("prep", [v2, prepNode], [edge])
    );
  });

  it("is stale when its input was tested with the old file, whatever ran since", () => {
    // Tested with v1, then the source was switched to v2 (a whole run's output
    // is never read by a Test Node, so it doesn't count here).
    const tested = output({ data_path: "/tmp/v1.csv" }, { settingsKey: keyFor(v1) });
    const key = testNodeSettingsKey("prep", [v2, prepNode], [edge], testOutputs({ src: tested }));
    expect(key).toBe(STALE_INPUT_KEY);
    // ...so Analyze downstream refuses it.
    const train: Node = { id: "train", type: "trainModelNode", position: { x: 0, y: 0 }, data: {} };
    const toTrain: Edge = { id: "e2", source: "prep", target: "train" };
    const result = resolveTrainingInputFile({
      fileUrl: SOURCE_DATA_PATH,
      nodeId: "train",
      nodes: [v2, prepNode, train],
      edges: [edge, toTrain],
      getLatestOutput: (id) =>
        id === "prep" ? output({ data_path: "/tmp/prep.csv" }, { settingsKey: key }) : undefined,
      fillVariables: (url) => url,
    });
    expect(result.ok).toBe(false);
  });

  it("is left untagged when an input has no recorded output", () => {
    expect(testNodeSettingsKey("prep", [v2, prepNode], [edge], testOutputs({}))).toBeUndefined();
  });

  it("checks every input of a node with several", () => {
    const other = { ...sourceNode({ sourceType: "csv", csvFilePath: "/data/b.csv", csvFileName: "b.csv" }), id: "src2" };
    const nodes = [v2, other, prepNode];
    const edges = [edge, { id: "e3", source: "src2", target: "prep" }];
    const current = (id: string) => upstreamSourcesKey(id, nodes, edges);
    const fresh = output({}, { settingsKey: current("src") });
    const fresh2 = output({}, { settingsKey: current("src2") });
    expect(testNodeSettingsKey("prep", nodes, edges, testOutputs({ src: fresh, src2: fresh2 }))).toBe(
      current("prep")
    );
    const old2 = output({}, { settingsKey: keyFor(v1) });
    expect(testNodeSettingsKey("prep", nodes, edges, testOutputs({ src: fresh, src2: old2 }))).toBe(
      STALE_INPUT_KEY
    );
  });

  it("explains how to refresh an untagged downstream output", () => {
    const train: Node = { id: "train", type: "trainModelNode", position: { x: 0, y: 0 }, data: {} };
    const result = resolveTrainingInputFile({
      fileUrl: SOURCE_DATA_PATH,
      nodeId: "train",
      nodes: [v2, prepNode, train],
      edges: [edge, { id: "e2", source: "prep", target: "train" }],
      getLatestOutput: (id) => (id === "prep" ? output({ data_path: "/tmp/prep.csv" }) : undefined),
      fillVariables: (url) => url,
    });
    expect(result).toEqual({
      ok: false,
      message:
        "The Data Preprocessing node's output can't be matched to the current training data. Run the whole workflow again, or test each node from the Train Data Source down to the Data Preprocessing node again, then try again.",
    });
  });
});

describe("resumedRunWorkflow", () => {
  it("tags nodes that ran before the pause with the settings they ran with", () => {
    const started = { nodes: [dbSource, prepNode], edges: [edge] } as unknown as Workflow;
    const edited = sourceNode({ ...dbSource.data, query: "select 2" });
    const current = { nodes: [edited, prepNode], edges: [edge] } as unknown as Workflow;
    const tagging = resumedRunWorkflow(started, current, ["src"]);
    const response = {
      state: {
        nodeExecutionStatus: {
          prep: { status: "success", type: "preprocessingNode", output: { data_path: "/tmp/p.csv" } },
        },
      },
    };
    expect(collectRunOutputs(response, tagging).prep.settingsKey).toBe(
      upstreamSourcesKey("prep", [dbSource, prepNode], [edge])
    );
    // A node that hadn't run yet uses the settings sent with the resume
    expect(resumedRunWorkflow(started, current, []).nodes[0]).toBe(edited);
  });
});

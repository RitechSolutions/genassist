import { describe, it, expect, vi } from "vitest";

// The node registry loads config/api, which reads the API URL when it loads
vi.hoisted(() => {
  vi.stubEnv("VITE_PUBLIC_API_URL", "http://localhost/api/");
});

import { Edge, Node } from "reactflow";
import { Workflow } from "@/interfaces/workflow.interface";
import { registerAllNodeTypes } from "@/views/AIAgents/Workflows/nodeTypes";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { REFERENCE_FIELDS } from "@/views/AIAgents/Workflows/utils/workflowReferences";
import {
  FILE_OMITTED_DATA,
  graphFromWorkflowFile,
  toWorkflowFile,
} from "@/views/AIAgents/Workflows/utils/workflowFile";

const node = (id: string, type: string, data: Record<string, unknown>): Node => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data,
});

const edge: Edge = { id: "e1", source: "start", target: "src" };

const ANALYSIS = { row_count: 2, sample_data: [{ plan: "SAMPLE-ROW" }] };

const oldFile = () =>
  ({
    id: "wf-1",
    name: "Churn",
    description: "Predicts churn",
    version: "1.0",
    settings: { nodeStyle: "compact" },
    agent_id: "agent-1",
    user_id: "user-1",
    created_by: "user-1",
    updated_by: "user-2",
    updated_by_username: "editor",
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-02T00:00:00Z",
    testInput: { message: "SAMPLE-MESSAGE" },
    executionState: {
      session: { message: "SAMPLE-MESSAGE" },
      source: {},
      nodeOutputs: { src: { output: { data_path: "/data/customers.csv" } } },
      statefulState: {},
    },
    nodes: [
      {
        ...node("src", "trainDataSourceNode", {
          name: "Customers",
          sourceType: "csv",
          csvFileName: "customers.csv",
          csvFilePath: "/data/customers.csv",
          csvFileId: "file-1",
          csvFileUrl: "http://files/file-1",
          sheetName: "",
          analysisResult: ANALYSIS,
        }),
        selected: true,
        dragging: false,
        width: 320,
        height: 180,
        positionAbsolute: { x: 0, y: 0 },
      },
    ],
    edges: [{ ...edge, selected: true, className: "highlighted" }],
  }) as unknown as Workflow;

const CLEAN_GRAPH = {
  nodes: [
    node("src", "trainDataSourceNode", {
      name: "Customers",
      sourceType: "csv",
      csvFileName: "customers.csv",
      sheetName: "",
    }),
  ],
  edges: [edge],
};

describe("toWorkflowFile", () => {
  it("writes only the graph and its settings", () => {
    const file = toWorkflowFile(oldFile());
    expect(file).toEqual({
      name: "Churn",
      description: "Predicts churn",
      version: "1.0",
      settings: { nodeStyle: "compact" },
      ...CLEAN_GRAPH,
    });
    expect(Object.keys(file)).toEqual([
      "name",
      "description",
      "version",
      "settings",
      "nodes",
      "edges",
    ]);
  });
});

describe("graphFromWorkflowFile", () => {
  it("takes only cleaned nodes and edges from a file written before the cleanup", () => {
    expect(graphFromWorkflowFile(oldFile())).toEqual(CLEAN_GRAPH);
  });

  it.each([
    [
      "preprocessingNode",
      {
        fileUrl: "{{source.data_path}}",
        pythonCode: "df",
        analysisResult: ANALYSIS,
        stepAnalysisResults: { initial: ANALYSIS },
        analyzedFileUrl: "/data/customers.csv",
      },
      { fileUrl: "{{source.data_path}}", pythonCode: "df" },
    ],
    [
      "trainModelNode",
      { fileUrl: "/data/typed.csv", targetColumn: "churned", analysisResult: ANALYSIS },
      { fileUrl: "/data/typed.csv", targetColumn: "churned" },
    ],
    [
      "fileReaderNode",
      {
        fileSource: "upload",
        fileName: "report.pdf",
        filePath: "/data/report.pdf",
        fileUrl: "http://files/file-2",
        fileId: "file-2",
      },
      { fileSource: "upload" },
    ],
    [
      "openApiNode",
      {
        providerId: "llm-1",
        query: "list pets",
        originalFileName: "spec.yaml",
        serverFilePath: "/data/spec.yaml",
        serverFileUrl: "http://files/file-3",
      },
      { providerId: "llm-1", query: "list pets" },
    ],
    [
      "trainDataSourceNode",
      { sourceType: "datasource", dataSourceId: "ds-1", query: "select 1", analysisResult: ANALYSIS },
      { sourceType: "datasource", dataSourceId: "ds-1", query: "select 1" },
    ],
    [
      "mlModelInferenceNode",
      { modelId: "model-1", modelName: "Churn model", inferenceInputs: { age: "{{age}}" } },
      { modelId: "model-1", modelName: "Churn model", inferenceInputs: { age: "{{age}}" } },
    ],
    [
      "guardrailNode",
      { fileUrl: "http://files/file-4", analysisResult: ANALYSIS },
      { fileUrl: "http://files/file-4", analysisResult: ANALYSIS },
    ],
  ])("leaves %s with only its design data", (type, data, expected) => {
    const { nodes } = graphFromWorkflowFile({ nodes: [node("n1", type, data)], edges: [] });
    expect(nodes).toEqual([node("n1", type, expected)]);
  });

  it("keeps every reference id and its name copy", () => {
    const nodes = Object.entries(REFERENCE_FIELDS).map(([type, fields], i) =>
      node(
        `n${i}`,
        type,
        Object.fromEntries(
          fields.flatMap((field) => [
            [field.key, field.multiple ? ["ref-1"] : "ref-1"],
            ...(field.nameKey ? [[field.nameKey, "Kept name"]] : []),
          ])
        )
      )
    );
    expect(graphFromWorkflowFile({ nodes, edges: [] }).nodes).toEqual(nodes);
  });

  it("keeps a group and its child as they are", () => {
    const nodes: Node[] = [
      {
        id: "g1",
        type: "groupNode",
        position: { x: 10, y: 20 },
        style: { width: 400, height: 300 },
        zIndex: -1,
        data: { name: "Training" },
      },
      {
        ...node("src", "templateNode", { template: "hi" }),
        parentNode: "g1",
        extent: "parent",
        expandParent: true,
      },
    ];
    expect(graphFromWorkflowFile({ nodes, edges: [] }).nodes).toEqual(nodes);
  });

  it("loads an empty graph from a file without nodes or edges", () => {
    expect(graphFromWorkflowFile({})).toEqual({ nodes: [], edges: [] });
    expect(graphFromWorkflowFile({ nodes: null, edges: null } as unknown as Workflow)).toEqual({
      nodes: [],
      edges: [],
    });
  });

  it("rejects nodes that are not a list", () => {
    expect(() => graphFromWorkflowFile({ nodes: {} } as unknown as Workflow)).toThrow();
  });

  it("does not change the file it reads", () => {
    const file = oldFile();
    graphFromWorkflowFile(file);
    toWorkflowFile(file);
    expect(file).toEqual(oldFile());
  });
});

describe("FILE_OMITTED_DATA", () => {
  it("has an entry for every registered node type", () => {
    registerAllNodeTypes();
    const undecided = nodeRegistry
      .getAllNodeTypes()
      .map((definition) => definition.type)
      .filter((type) => !(type in FILE_OMITTED_DATA));
    expect(undecided).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";
import {
  buildVariableTree,
  type VariableNode,
} from "@/helpers/variable-input/variableTree";

const NODE_ID = "3f1a2b4c-5d6e-4f70-8a91-b2c3d4e5f607";

/** Depth-first walk, so a container always precedes the values it holds. */
function flatten(nodes: VariableNode[]): VariableNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)]);
}

function build(data: unknown, nodeNames = {}): VariableNode[] {
  return flatten(buildVariableTree(data, nodeNames));
}

describe("buildVariableTree node fields", () => {
  it("returns nothing for non-object input", () => {
    expect(build(null)).toEqual([]);
    expect(build("text")).toEqual([]);
    expect(build([1, 2])).toEqual([]);
  });

  it("emits a container before the leaves it holds", () => {
    const nodes = build({ source: { label: "ok" } });
    expect(nodes.map((n) => n.path)).toEqual(["source", "source.label"]);
    expect(nodes[0].kind).toBe("object");
    expect(nodes[1].kind).toBe("value");
  });

  it("wraps every path as an insertable reference", () => {
    const [node] = build({ answer: 42 });
    expect(node.reference).toBe("{{answer}}");
  });

  it("indexes array items with bracket notation", () => {
    const nodes = build({ items: ["a", "b"] });
    expect(nodes.map((n) => n.path)).toEqual(["items", "items[0]", "items[1]"]);
    expect(nodes[0].kind).toBe("array");
  });

  it("keeps node ids in the path but shows node names in the breadcrumb", () => {
    const nodes = build(
      { [NODE_ID]: { score: 0.9 } },
      { [NODE_ID]: { name: "Classifier", type: "llm" } }
    );
    expect(nodes[1].path).toBe(`${NODE_ID}.score`);
    expect(nodes[1].breadcrumb).toBe("Classifier.score");
  });

  it("falls back to the raw id when the node is unknown", () => {
    const [node] = build({ [NODE_ID]: 1 });
    expect(node.breadcrumb).toBe(NODE_ID);
  });

  it("previews values without dumping whole objects", () => {
    const nodes = build({
      text: "hi",
      count: 3,
      missing: null,
      list: [1],
      nested: { a: 1, b: 2 },
    });
    const preview = Object.fromEntries(nodes.map((n) => [n.path, n.preview]));

    expect(preview.text).toBe('"hi"');
    expect(preview.count).toBe("3");
    expect(preview.missing).toBe("null");
    expect(preview.list).toBe("Array[1]");
    expect(preview.nested).toBe("Object{2}");
  });

  it("truncates a long string preview", () => {
    const [node] = build({ text: "x".repeat(100) });
    expect(node.preview.endsWith('…"')).toBe(true);
    expect(node.preview.length).toBeLessThan(60);
  });

  it("stops descending past the depth cap", () => {
    // 8 levels deep, only 6 are kept
    let deep: Record<string, unknown> = { leaf: 1 };
    for (let i = 0; i < 8; i += 1) deep = { [`l${i}`]: deep };

    const deepest = Math.max(
      ...build(deep).map((n) => n.path.split(".").length)
    );
    expect(deepest).toBe(7);
  });

  it("builds a lowercased haystack covering name and raw path", () => {
    const [, node] = build(
      { [NODE_ID]: { Score: 1 } },
      { [NODE_ID]: { name: "Classifier", type: "llm" } }
    );
    expect(node.search).toBe(`classifier.score ${NODE_ID}.score`.toLowerCase());
  });
});

import { describe, expect, it } from "vitest";
import {
  buildVariableTree,
  getVisibleRows,
} from "@/helpers/variable-input/variableTree";

const DATA = {
  classifier: {
    prediction: "yes",
    scores: [0.1, 0.9],
  },
  webhook: {
    body: { prefix: "a" },
  },
};

const tree = buildVariableTree(DATA);
const paths = (rows: ReturnType<typeof getVisibleRows>) =>
  rows.map((row) => row.node.path);

describe("buildVariableTree", () => {
  it("nests children under their container", () => {
    expect(tree.map((n) => n.path)).toEqual(["classifier", "webhook"]);
    expect(tree[0].children.map((n) => n.path)).toEqual([
      "classifier.prediction",
      "classifier.scores",
    ]);
  });

  it("nests array items under the array", () => {
    const scores = tree[0].children[1];
    expect(scores.kind).toBe("array");
    expect(scores.children.map((n) => n.path)).toEqual([
      "classifier.scores[0]",
      "classifier.scores[1]",
    ]);
  });

  it("returns an empty tree for non-object data", () => {
    expect(buildVariableTree(null)).toEqual([]);
    expect(buildVariableTree("text")).toEqual([]);
  });

  it("gives leaves no children", () => {
    expect(tree[0].children[0].children).toEqual([]);
  });
});

describe("getVisibleRows", () => {
  it("shows only the roots when nothing is expanded", () => {
    expect(paths(getVisibleRows(tree, new Set()))).toEqual([
      "classifier",
      "webhook",
    ]);
  });

  it("reveals the children of an expanded branch", () => {
    const rows = getVisibleRows(tree, new Set(["classifier"]));
    expect(paths(rows)).toEqual([
      "classifier",
      "classifier.prediction",
      "classifier.scores",
      "webhook",
    ]);
  });

  it("does not expand grandchildren until their parent is opened too", () => {
    const rows = getVisibleRows(tree, new Set(["classifier.scores"]));
    expect(paths(rows)).toEqual(["classifier", "webhook"]);
  });

  it("reports depth and expandability for indentation", () => {
    const rows = getVisibleRows(tree, new Set(["classifier"]));
    expect(rows[0]).toMatchObject({ depth: 0, expandable: true, expanded: true });
    expect(rows[1]).toMatchObject({ depth: 1, expandable: false, expanded: false });
    expect(rows[2]).toMatchObject({ depth: 1, expandable: true, expanded: false });
  });

  it("auto-expands ancestors to reveal a deep match", () => {
    const rows = getVisibleRows(tree, new Set(), "prefix");
    expect(paths(rows)).toEqual([
      "webhook",
      "webhook.body",
      "webhook.body.prefix",
    ]);
    expect(rows[0].expanded).toBe(true);
  });

  it("drops branches with no match anywhere inside", () => {
    expect(paths(getVisibleRows(tree, new Set(), "prefix"))).not.toContain(
      "classifier"
    );
  });

  it("leaves a matching branch collapsed so it can be opened by hand", () => {
    const rows = getVisibleRows(tree, new Set(), "classifier");
    expect(paths(rows)).toEqual(["classifier"]);
    expect(rows[0].expanded).toBe(false);
  });

  it("expands a matched branch once it is in the expanded set", () => {
    const rows = getVisibleRows(tree, new Set(["classifier"]), "classifier");
    expect(paths(rows)).toEqual([
      "classifier",
      "classifier.prediction",
      "classifier.scores",
    ]);
  });

  it("requires every term to match, across separators", () => {
    expect(paths(getVisibleRows(tree, new Set(), "webhook.prefix"))).toEqual([
      "webhook",
      "webhook.body",
      "webhook.body.prefix",
    ]);
  });

  it("is case insensitive", () => {
    expect(paths(getVisibleRows(tree, new Set(), "PREFIX"))).toContain(
      "webhook.body.prefix"
    );
  });

  it("returns nothing when the query matches no branch", () => {
    expect(getVisibleRows(tree, new Set(), "nonexistent")).toEqual([]);
  });

  it("treats a blank query as no query", () => {
    expect(paths(getVisibleRows(tree, new Set(), "   "))).toEqual([
      "classifier",
      "webhook",
    ]);
  });
});

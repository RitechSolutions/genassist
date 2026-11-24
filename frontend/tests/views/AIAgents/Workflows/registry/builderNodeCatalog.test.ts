import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, writeFileSync } from "fs";
import { resolve } from "path";
import { registerAllNodeTypes } from "@/views/AIAgents/Workflows/nodeTypes";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";

/**
 * The Workflow Builder agent builds and validates workflows on the backend, so
 * the backend needs the same node facts the canvas uses: which node types exist,
 * their default data and their handles. This file is generated from the node
 * registry and committed; the test fails when a node definition changes without
 * the catalog being regenerated.
 *
 * Regenerate with:  UPDATE_BUILDER_CATALOG=1 npx vitest run tests/views/AIAgents/Workflows/registry/builderNodeCatalog.test.ts
 */
const CATALOG_PATH = resolve(
  __dirname,
  "../../../../../../backend/app/modules/workflow/builder/node_catalog.json",
);

const buildCatalog = () => {
  registerAllNodeTypes();
  return nodeRegistry
    .getAllNodeTypes()
    .map((definition) => ({
      type: definition.type,
      label: definition.label,
      description: definition.description,
      category: definition.category,
      dynamicHandles: Boolean(definition.getHandlers),
      defaultData: definition.defaultData,
    }))
    .sort((a, b) => a.type.localeCompare(b.type));
};

describe("workflow builder node catalog", () => {
  it("matches the node registry", () => {
    const serialized = `${JSON.stringify(buildCatalog(), null, 2)}\n`;

    if (process.env.UPDATE_BUILDER_CATALOG) {
      writeFileSync(CATALOG_PATH, serialized);
      return;
    }

    expect(
      existsSync(CATALOG_PATH),
      "node_catalog.json is missing; regenerate it (see the comment in this file)",
    ).toBe(true);
    expect(
      readFileSync(CATALOG_PATH, "utf-8"),
      "node_catalog.json is stale; regenerate it (see the comment in this file)",
    ).toBe(serialized);
  });
});

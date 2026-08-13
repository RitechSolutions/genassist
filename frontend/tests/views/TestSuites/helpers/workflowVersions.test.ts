import { describe, expect, it } from "vitest";
import {
  compareVersions,
  groupWorkflowVersions,
} from "@/views/TestSuites/helpers/workflowVersions";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";

const wf = (overrides: Partial<WorkflowMinimal>): WorkflowMinimal => ({
  id: "id",
  name: "Workflow",
  version: "1",
  ...overrides,
});

describe("compareVersions", () => {
  it("compares numerically, not lexicographically", () => {
    expect(compareVersions("10", "9")).toBeGreaterThan(0);
    expect(compareVersions("9", "10")).toBeLessThan(0);
  });

  it("compares dotted components left to right", () => {
    expect(compareVersions("1.2", "1.1")).toBeGreaterThan(0);
    expect(compareVersions("1.1", "1.2")).toBeLessThan(0);
    expect(compareVersions("2.0.1", "2.0.0")).toBeGreaterThan(0);
  });

  it("returns 0 for equal versions", () => {
    expect(compareVersions("1.2", "1.2")).toBe(0);
    expect(compareVersions("3", "3")).toBe(0);
  });

  it("treats missing trailing components as zero", () => {
    expect(compareVersions("1.0", "1")).toBe(0);
    expect(compareVersions("1", "1.0")).toBe(0);
    expect(compareVersions("1.0.1", "1")).toBeGreaterThan(0);
  });

  it("strips non-digit decoration like a leading 'v'", () => {
    expect(compareVersions("v1.2", "v1.1")).toBeGreaterThan(0);
    expect(compareVersions("v2", "v1")).toBeGreaterThan(0);
    expect(compareVersions("v1.2", "1.2")).toBe(0);
  });

  it("treats a fully non-numeric component as zero", () => {
    expect(compareVersions("abc", "def")).toBe(0);
    expect(compareVersions("abc", "1")).toBeLessThan(0);
  });

  it("returns b's diff sign so ascending sort puts the highest last", () => {
    const sorted = ["2", "1", "10"].sort(compareVersions);
    expect(sorted).toEqual(["1", "2", "10"]);
  });
});

describe("groupWorkflowVersions", () => {
  it("returns an empty array for no workflows", () => {
    expect(groupWorkflowVersions([])).toEqual([]);
  });

  it("skips workflows without an id", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "", name: "NoId", agent_id: "a1" }),
    ]);
    expect(groups).toEqual([]);
  });

  it("groups versions sharing an agent_id, newest version first", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "v1", name: "WF v1", version: "1", agent_id: "agent-1" }),
      wf({ id: "v2", name: "WF v2", version: "2", agent_id: "agent-1" }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe("agent-1");
    expect(groups[0].versions.map((v) => v.id)).toEqual(["v2", "v1"]);
  });

  it("takes the group name and activeVersionId from the active version", () => {
    const groups = groupWorkflowVersions([
      wf({
        id: "v1",
        name: "Old Name",
        version: "1",
        agent_id: "agent-1",
        is_active_version: true,
      }),
      wf({ id: "v2", name: "New Name", version: "2", agent_id: "agent-1" }),
    ]);
    expect(groups[0].name).toBe("Old Name");
    expect(groups[0].activeVersionId).toBe("v1");
    // Ordering is still by version (newest first), independent of which is active.
    expect(groups[0].versions.map((v) => v.id)).toEqual(["v2", "v1"]);
  });

  it("falls back to the newest version's name and null active id when none is active", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "v1", name: "Lower", version: "1", agent_id: "agent-1" }),
      wf({ id: "v2", name: "Newest", version: "2", agent_id: "agent-1" }),
    ]);
    expect(groups[0].name).toBe("Newest");
    expect(groups[0].activeVersionId).toBeNull();
  });

  it("groups legacy rows without an agent_id by name", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "l1", name: "Legacy", version: "1", agent_id: undefined }),
      wf({ id: "l2", name: "Legacy", version: "2", agent_id: undefined }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe("name:Legacy");
    expect(groups[0].versions.map((v) => v.id)).toEqual(["l2", "l1"]);
  });

  it("treats a null agent_id as legacy and keys by name", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "l1", name: "NullAgent", version: "1", agent_id: null }),
    ]);
    expect(groups[0].key).toBe("name:NullAgent");
  });

  it("keeps legacy rows with different names as separate groups", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "l1", name: "Alpha", version: "1", agent_id: undefined }),
      wf({ id: "l2", name: "Beta", version: "1", agent_id: undefined }),
    ]);
    expect(groups).toHaveLength(2);
  });

  it("sorts the resulting groups by name ascending", () => {
    const groups = groupWorkflowVersions([
      wf({ id: "z1", name: "Zebra", version: "1", agent_id: "b" }),
      wf({ id: "a1", name: "Alpha", version: "1", agent_id: "a" }),
    ]);
    expect(groups.map((g) => g.name)).toEqual(["Alpha", "Zebra"]);
  });
});

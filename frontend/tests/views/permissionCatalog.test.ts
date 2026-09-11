import { describe, expect, it } from "vitest";
import {
  buildPermissionAreas,
  collapsedAreasFor,
  parsePermissionName,
  resourceLabel,
  summarizeCapabilities,
  verbLabel,
} from "@/views/Roles/permissionCatalog";
import { Permission } from "@/interfaces/permission.interface";

const permission = (name: string, isAdminOnly = false): Permission => ({
  id: `id:${name}`,
  name,
  is_active: 1,
  is_admin_only: isAdminOnly,
});

// A representative slice of the real permission set, including every shape that
// does not follow "verb:resource".
const SAMPLE = [
  permission("read:conversation"),
  permission("create:in_progress_conversation"),
  permission("takeover_in_progress_conversation"),
  permission("delete:conversation:gdpr"),
  permission("read:workflow"),
  permission("execute:workflow"),
  permission("read:openai_file"),
  permission("delete:openai-file"),
  permission("read:app_settings", true),
  permission("write:app_settings", true),
];

describe("parsePermissionName", () => {
  it("splits a standard verb:resource name", () => {
    expect(parsePermissionName("read:workflow")).toEqual({
      verb: "read",
      resource: "workflow",
    });
  });

  it("maps the colon-less takeover permission onto its resource", () => {
    expect(parsePermissionName("takeover_in_progress_conversation")).toEqual({
      verb: "takeover",
      resource: "in_progress_conversation",
    });
  });

  it("keeps the trailing qualifier of a three-part name", () => {
    expect(parsePermissionName("delete:conversation:gdpr")).toEqual({
      verb: "delete",
      resource: "conversation:gdpr",
    });
  });

  it("folds the hyphenated openai-file spelling into its family", () => {
    expect(parsePermissionName("delete:openai-file").resource).toBe("openai_file");
  });
});

describe("buildPermissionAreas", () => {
  it("places every permission exactly once", () => {
    const areas = buildPermissionAreas(SAMPLE);
    const placed = areas.flatMap((area) => area.permissionIds);

    expect(placed).toHaveLength(SAMPLE.length);
    expect(new Set(placed).size).toBe(SAMPLE.length);
  });

  it("routes an unrecognised resource to Other rather than dropping it", () => {
    const areas = buildPermissionAreas([permission("read:brand_new_thing")]);

    expect(areas).toHaveLength(1);
    expect(areas[0].key).toBe("other");
    expect(areas[0].permissionIds).toEqual(["id:read:brand_new_thing"]);
  });

  it("groups the two openai_file spellings into one row", () => {
    const areas = buildPermissionAreas(SAMPLE);
    const row = areas
      .flatMap((area) => area.rows)
      .find((candidate) => candidate.key === "openai_file");

    expect(row?.entries.map((entry) => entry.name).sort()).toEqual([
      "delete:openai-file",
      "read:openai_file",
    ]);
  });

  it("orders verbs CRUD-first", () => {
    const areas = buildPermissionAreas([
      permission("delete:workflow"),
      permission("execute:workflow"),
      permission("read:workflow"),
      permission("create:workflow"),
    ]);
    const row = areas.flatMap((area) => area.rows)[0];

    expect(row.entries.map((entry) => entry.verb)).toEqual([
      "read",
      "create",
      "delete",
      "execute",
    ]);
  });

  it("marks an area admin-only only when all of its permissions are", () => {
    const areas = buildPermissionAreas(SAMPLE);
    const configuration = areas.find((area) => area.key === "configuration");
    const conversations = areas.find((area) => area.key === "conversations");

    expect(configuration?.isAdminOnly).toBe(true);
    expect(conversations?.isAdminOnly).toBe(false);
  });

  it("keeps the curated area order", () => {
    const areas = buildPermissionAreas(SAMPLE);

    expect(areas.map((area) => area.key)).toEqual([
      "conversations",
      "automation",
      "fine_tuning",
      "configuration",
    ]);
  });

  it("omits areas with no permissions", () => {
    const areas = buildPermissionAreas([permission("read:workflow")]);

    expect(areas.map((area) => area.key)).toEqual(["automation"]);
  });
});

describe("collapsedAreasFor", () => {
  const areas = buildPermissionAreas(SAMPLE);
  const allKeys = areas.map((area) => area.key);

  it("collapses every area for a new role, which has nothing selected", () => {
    expect([...collapsedAreasFor(areas, [])].sort()).toEqual([...allKeys].sort());
  });

  it("expands only the areas the role actually draws on", () => {
    const collapsed = collapsedAreasFor(areas, ["id:read:workflow"]);

    expect(collapsed.has("automation")).toBe(false);
    expect(collapsed.has("conversations")).toBe(true);
    expect(collapsed.has("fine_tuning")).toBe(true);
    expect(collapsed.has("configuration")).toBe(true);
  });

  it("expands every area holding a selection, not just the first", () => {
    const collapsed = collapsedAreasFor(areas, [
      "id:read:workflow",
      "id:read:conversation",
    ]);

    expect(collapsed.has("automation")).toBe(false);
    expect(collapsed.has("conversations")).toBe(false);
    expect(collapsed.has("fine_tuning")).toBe(true);
  });

  it("expands an area held open by a single permission among many", () => {
    const collapsed = collapsedAreasFor(areas, ["id:delete:conversation:gdpr"]);

    expect(collapsed.has("conversations")).toBe(false);
  });

  it("collapses nothing when the role holds everything", () => {
    const everyId = areas.flatMap((area) => area.permissionIds);

    expect(collapsedAreasFor(areas, everyId).size).toBe(0);
  });

  it("ignores selections that match no permission", () => {
    expect([...collapsedAreasFor(areas, ["id:gone"])].sort()).toEqual(
      [...allKeys].sort()
    );
  });
});

describe("labels", () => {
  it("uses curated labels where defined", () => {
    expect(resourceLabel("in_progress_conversation")).toBe("Live conversations");
    expect(verbLabel("read")).toBe("View");
    expect(verbLabel("takeover")).toBe("Take over");
  });

  it("humanises an unknown resource or verb instead of showing raw text", () => {
    expect(resourceLabel("brand_new_thing")).toBe("Brand new thing");
    expect(verbLabel("archive")).toBe("Archive");
  });
});

describe("summarizeCapabilities", () => {
  const areas = buildPermissionAreas(SAMPLE);

  it("returns nothing when no permission is selected", () => {
    expect(summarizeCapabilities(areas, new Set())).toEqual([]);
  });

  it("says view when only read permissions are selected", () => {
    expect(summarizeCapabilities(areas, new Set(["id:read:workflow"]))).toEqual([
      "view workflows & agents",
    ]);
  });

  it("says manage as soon as a write permission is selected", () => {
    expect(
      summarizeCapabilities(areas, new Set(["id:read:workflow", "id:execute:workflow"]))
    ).toEqual(["manage workflows & agents"]);
  });

  it("reports each area that has a selection", () => {
    expect(
      summarizeCapabilities(areas, new Set(["id:read:workflow", "id:read:conversation"]))
    ).toEqual(["view conversations", "view workflows & agents"]);
  });
});

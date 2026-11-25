import { describe, expect, it } from "vitest";
import { canSaveAgentAsTemplate, templateActionAccess } from "@/views/Templates/templateAccess";

const NONE = { use: false, publish: false, delete: false, save: false };

describe("templateActionAccess", () => {
  it("shows no action without template permissions", () => {
    expect(templateActionAccess([])).toEqual(NONE);
    expect(templateActionAccess(["read:template", "approve:template"])).toEqual(NONE);
  });

  it("shows each action only with its own permission", () => {
    expect(templateActionAccess(["install:template"])).toEqual({ ...NONE, use: true });
    expect(templateActionAccess(["publish:template"])).toEqual({ ...NONE, publish: true });
    expect(templateActionAccess(["delete:template"])).toEqual({ ...NONE, delete: true });
    expect(templateActionAccess(["create:template"])).toEqual({ ...NONE, save: true });
  });

  it("shows every action with full access", () => {
    expect(templateActionAccess(["*"])).toEqual({ use: true, publish: true, delete: true, save: true });
  });
});

describe("canSaveAgentAsTemplate", () => {
  const mine = { is_system: false, is_mine: true, workflow_id: "wf-1" };

  it("offers the user's own agents and system agents", () => {
    expect(canSaveAgentAsTemplate(mine, ["create:template"])).toBe(true);
    expect(canSaveAgentAsTemplate({ ...mine, is_system: true, is_mine: false }, ["*"])).toBe(true);
  });

  it("hides a colleague's agent, as the server refuses it", () => {
    expect(canSaveAgentAsTemplate({ ...mine, is_mine: false }, ["*"])).toBe(false);
    expect(canSaveAgentAsTemplate({ ...mine, is_mine: undefined }, ["*"])).toBe(false);
  });

  it("hides it without the create permission or a workflow", () => {
    expect(canSaveAgentAsTemplate(mine, ["read:template"])).toBe(false);
    expect(canSaveAgentAsTemplate({ ...mine, workflow_id: null }, ["*"])).toBe(false);
  });
});

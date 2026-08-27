import { describe, expect, it } from "vitest";
import type { Role } from "@/interfaces/role.interface";
import type { User } from "@/interfaces/user.interface";
import { activeSupervisedGroupIds, isSupervisorUser } from "@/views/Users/helpers/supervision";

const role = (name: string) => ({ id: `role-${name}`, name }) as Role;

const user = (overrides: Partial<User> = {}): User => ({
  username: "someone",
  email: "someone@example.test",
  is_active: 1,
  roles: [role("supervisor")],
  group_id: "own-group",
  supervised_group_ids: ["own-group", "other-group"],
  ...overrides,
});

describe("isSupervisorUser", () => {
  it("matches the role regardless of casing", () => {
    expect(isSupervisorUser(user({ roles: [role("Supervisor")] }))).toBe(true);
  });

  it("is false once the role is gone", () => {
    expect(isSupervisorUser(user({ roles: [role("operator")] }))).toBe(false);
  });
});

describe("activeSupervisedGroupIds", () => {
  it("drops stale assignments held by a non-supervisor", () => {
    expect(activeSupervisedGroupIds(user({ roles: [role("operator")] }))).toEqual([]);
  });

  it("returns a supervisor's assignments without their own group", () => {
    expect(activeSupervisedGroupIds(user())).toEqual(["other-group"]);
  });

  it("treats a missing roles list as no supervision", () => {
    expect(activeSupervisedGroupIds(user({ roles: undefined }))).toEqual([]);
  });

  it("treats missing assignments as none", () => {
    expect(activeSupervisedGroupIds(user({ supervised_group_ids: undefined }))).toEqual([]);
  });
});

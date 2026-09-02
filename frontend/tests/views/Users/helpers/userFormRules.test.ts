import { describe, it, expect } from "vitest";
import { areUserRolesRequired } from "@/views/Users/helpers/userFormRules";

describe("areUserRolesRequired", () => {
  it("always requires roles in create mode", () => {
    expect(areUserRolesRequired("create", "console")).toBe(true);
    expect(areUserRolesRequired("create", "interactive")).toBe(true);
  });

  it("exempts only console users on edit", () => {
    expect(areUserRolesRequired("edit", "console")).toBe(false);
    expect(areUserRolesRequired("edit", "interactive")).toBe(true);
  });

  it("matches the console type name exactly", () => {
    expect(areUserRolesRequired("edit", "Console")).toBe(true);
  });

  it("requires roles when the type is unknown", () => {
    expect(areUserRolesRequired("edit", undefined)).toBe(true);
  });
});

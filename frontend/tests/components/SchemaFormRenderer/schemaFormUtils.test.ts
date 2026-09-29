import { describe, expect, it } from "vitest";
import {
  getSchemaDefaults,
  isFieldVisible,
} from "@/components/SchemaFormRenderer/schemaFormUtils";
import type { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

describe("isFieldVisible", () => {
  it("is always visible when there is no conditional", () => {
    expect(isFieldVisible({}, {})).toBe(true);
    expect(isFieldVisible({}, { anything: "x" })).toBe(true);
  });

  it("is visible when the controlling field holds the matching value", () => {
    const field = { conditional: { field: "auth", value: "client_credentials" } };
    expect(isFieldVisible(field, { auth: "client_credentials" })).toBe(true);
  });

  it("is hidden when the controlling field holds a different value", () => {
    const field = { conditional: { field: "auth", value: "client_credentials" } };
    expect(isFieldVisible(field, { auth: "basic" })).toBe(false);
  });

  it("is hidden when the controlling field is absent", () => {
    const field = { conditional: { field: "auth", value: "client_credentials" } };
    expect(isFieldVisible(field, {})).toBe(false);
  });

  it("uses strict equality (number vs string)", () => {
    const field = { conditional: { field: "count", value: 1 } };
    expect(isFieldVisible(field, { count: 1 })).toBe(true);
    expect(isFieldVisible(field, { count: "1" })).toBe(false);
  });

  it("matches boolean conditional values strictly", () => {
    const field = { conditional: { field: "flag", value: true } };
    expect(isFieldVisible(field, { flag: true })).toBe(true);
    expect(isFieldVisible(field, { flag: false })).toBe(false);
  });
});

describe("getSchemaDefaults", () => {
  it("returns an empty object for no fields", () => {
    expect(getSchemaDefaults([])).toEqual({});
  });

  it("collects defined defaults, including falsy 0, false and empty string", () => {
    const fields = [
      { name: "a", default: "x" },
      { name: "b", default: 0 },
      { name: "c", default: false },
      { name: "g", default: "" },
    ] as unknown as FieldSchema[];
    expect(getSchemaDefaults(fields)).toEqual({
      a: "x",
      b: 0,
      c: false,
      g: "",
    });
  });

  it("omits fields whose default is undefined or null", () => {
    const fields = [
      { name: "a", default: "keep" },
      { name: "d" },
      { name: "e", default: null },
      { name: "f", default: undefined },
    ] as unknown as FieldSchema[];
    expect(getSchemaDefaults(fields)).toEqual({ a: "keep" });
  });
});

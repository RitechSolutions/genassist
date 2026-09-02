import { describe, expect, it } from "vitest";
import { getEmptyRequiredFields } from "@/views/AIAgents/Workflows/utils/nodeValidation";
import type { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

const schema = (over: Partial<FieldSchema>): FieldSchema =>
  ({ name: "n", label: "Name", type: "text", ...over }) as FieldSchema;

describe("getEmptyRequiredFields", () => {
  it("returns nothing when there are no schemas", () => {
    expect(getEmptyRequiredFields({}, [])).toEqual([]);
  });

  it("reports required fields that are missing", () => {
    expect(getEmptyRequiredFields({}, [schema({ required: true })])).toEqual([
      "Name",
    ]);
  });

  it("treats blank strings and empty arrays as missing", () => {
    expect(
      getEmptyRequiredFields({ n: "   " }, [schema({ required: true })])
    ).toEqual(["Name"]);
    expect(
      getEmptyRequiredFields({ n: [] }, [schema({ required: true })])
    ).toEqual(["Name"]);
  });

  it("accepts filled values", () => {
    expect(
      getEmptyRequiredFields({ n: "value" }, [schema({ required: true })])
    ).toEqual([]);
    expect(
      getEmptyRequiredFields({ n: ["a"] }, [schema({ required: true })])
    ).toEqual([]);
  });

  it("ignores non-required fields", () => {
    expect(
      getEmptyRequiredFields({}, [schema({ required: false })])
    ).toEqual([]);
  });

  it("skips conditional fields whose condition is not met", () => {
    const fields = [
      schema({
        name: "key",
        label: "Key",
        required: true,
        conditional: { field: "mode", value: "advanced" },
      }),
    ];
    expect(getEmptyRequiredFields({ mode: "basic" }, fields)).toEqual([]);
    expect(getEmptyRequiredFields({ mode: "advanced" }, fields)).toEqual([
      "Key",
    ]);
  });

  it("evaluates boolean conditionals with truthy coercion", () => {
    const fields = [
      schema({
        name: "key",
        label: "Key",
        required: true,
        conditional: { field: "enabled", value: true },
      }),
    ];
    expect(getEmptyRequiredFields({ enabled: true }, fields)).toEqual(["Key"]);
    expect(getEmptyRequiredFields({ enabled: "true" }, fields)).toEqual(["Key"]);
    expect(getEmptyRequiredFields({ enabled: 1 }, fields)).toEqual(["Key"]);
    expect(getEmptyRequiredFields({ enabled: false }, fields)).toEqual([]);
  });

  it("supports a negated boolean conditional", () => {
    const fields = [
      schema({
        name: "key",
        label: "Key",
        required: true,
        conditional: { field: "enabled", value: false },
      }),
    ];
    expect(getEmptyRequiredFields({ enabled: false }, fields)).toEqual(["Key"]);
    expect(getEmptyRequiredFields({ enabled: true }, fields)).toEqual([]);
  });

  it("reports every missing required field", () => {
    const fields = [
      schema({ name: "a", label: "A", required: true }),
      schema({ name: "b", label: "B", required: true }),
    ];
    expect(getEmptyRequiredFields({}, fields)).toEqual(["A", "B"]);
  });
});

import { describe, it, expect } from "vitest";
import {
  getHandlerPosition,
  calculateNextVersion,
  isVersionDuplicate,
  findPreviousVersion,
  maskToken,
  getNodeDimensions,
  getNodeCenter,
  extractDynamicVariables,
  extractDynamicVariablesAsRecord,
  convertSchemaToParams,
  generateSampleOutput,
  generateTemplateFromInputSchema,
  getValueFromPath,
  parseInputValue,
  valueToString,
  truncateNodeOutput,
} from "@/views/AIAgents/Workflows/utils/helpers";
import { Workflow } from "@/interfaces/workflow.interface";
import { Node } from "reactflow";
import { NodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { NodeSchema, SchemaType } from "@/views/AIAgents/Workflows/types/schemas";

const wf = (over: Partial<Workflow> = {}): Workflow =>
  ({ name: "wf", version: "1.0", ...over }) as Workflow;

const mkNode = (over: Partial<Node> = {}): Node =>
  ({ id: "n", position: { x: 0, y: 0 }, data: {}, ...over }) as Node;

const asNodeData = (o: Record<string, unknown>): NodeData => o as unknown as NodeData;

describe("getHandlerPosition", () => {
  it("distributes handles evenly for clean divisors", () => {
    expect(getHandlerPosition(0, 1)).toBe("50%");
    expect(getHandlerPosition(0, 3)).toBe("25%");
    expect(getHandlerPosition(1, 3)).toBe("50%");
    expect(getHandlerPosition(2, 3)).toBe("75%");
    expect(getHandlerPosition(0, 4)).toBe("20%");
  });

  it("follows the (index+1)*(100/(total+1)) formula for non-clean divisors", () => {
    expect(getHandlerPosition(0, 2)).toBe(`${(0 + 1) * (100 / (2 + 1))}%`);
    expect(getHandlerPosition(1, 2)).toBe(`${(1 + 1) * (100 / (2 + 1))}%`);
  });
});

describe("calculateNextVersion", () => {
  it("returns 1.0 for an empty list", () => {
    expect(calculateNextVersion([])).toBe("1.0");
  });

  it("returns 1.0 when no valid positive versions exist", () => {
    expect(calculateNextVersion([wf({ version: "abc" }), wf({ version: "0" })])).toBe(
      "1.0"
    );
    expect(calculateNextVersion([wf({ version: undefined })])).toBe("1.0");
  });

  it("adds 0.1 to the highest version, formatted to one decimal", () => {
    expect(calculateNextVersion([wf({ version: "1.0" }), wf({ version: "1.2" })])).toBe(
      "1.3"
    );
    expect(calculateNextVersion([wf({ version: "3.9" })])).toBe("4.0");
  });

  it("ignores invalid versions when computing the max", () => {
    expect(
      calculateNextVersion([wf({ version: "1.5" }), wf({ version: "nope" })])
    ).toBe("1.6");
  });
});

describe("isVersionDuplicate", () => {
  it("returns false for empty or whitespace-only versions", () => {
    expect(isVersionDuplicate([wf({ version: "1.0" })], "")).toBe(false);
    expect(isVersionDuplicate([wf({ version: "1.0" })], "   ")).toBe(false);
  });

  it("detects an existing version (trimming both sides)", () => {
    const list = [wf({ id: "a", version: "1.0" })];
    expect(isVersionDuplicate(list, "1.0")).toBe(true);
    expect(isVersionDuplicate(list, "  1.0  ")).toBe(true);
  });

  it("returns false when the version is not present", () => {
    expect(isVersionDuplicate([wf({ id: "a", version: "1.0" })], "2.0")).toBe(false);
  });

  it("excludes the given workflow id from the match", () => {
    const list = [wf({ id: "a", version: "1.0" })];
    expect(isVersionDuplicate(list, "1.0", "a")).toBe(false);
    expect(isVersionDuplicate(list, "1.0", "b")).toBe(true);
  });
});

describe("findPreviousVersion", () => {
  it("returns null when there is one or fewer workflows", () => {
    const only = wf({ id: "only", version: "1.0" });
    expect(findPreviousVersion([only], only)).toBeNull();
  });

  it("returns the highest version below the deleted one", () => {
    const a = wf({ id: "a", version: "1.0" });
    const b = wf({ id: "b", version: "2.0" });
    const c = wf({ id: "c", version: "3.0" });
    expect(findPreviousVersion([a, b, c], c)?.id).toBe("b");
    expect(findPreviousVersion([a, b, c], b)?.id).toBe("a");
  });

  it("falls back to the lowest higher version when nothing is lower", () => {
    const a = wf({ id: "a", version: "1.0" });
    const b = wf({ id: "b", version: "2.0" });
    const c = wf({ id: "c", version: "3.0" });
    expect(findPreviousVersion([a, b, c], a)?.id).toBe("b");
  });

  it("returns the most recently created workflow when no valid versions remain", () => {
    const del = wf({ id: "del", version: "2.0", created_at: "2020-01-01" });
    const older = wf({ id: "older", version: "abc", created_at: "2020-01-01" });
    const newer = wf({ id: "newer", version: "xyz", created_at: "2022-01-01" });
    expect(findPreviousVersion([del, older, newer], del)?.id).toBe("newer");
  });

  it("returns the most recent remaining workflow on an exact-version tie", () => {
    const del = wf({ id: "del", version: "2.0", created_at: "2020-01-01" });
    const same = wf({ id: "same", version: "2.0", created_at: "2021-01-01" });
    expect(findPreviousVersion([del, same], del)?.id).toBe("same");
  });
});

describe("maskToken", () => {
  it("returns empty string for a falsy token", () => {
    expect(maskToken("")).toBe("");
  });

  it("masks each character up to 20 with no ellipsis when short", () => {
    expect(maskToken("abc")).toBe("●●●");
    expect(maskToken("abcde")).toBe("●".repeat(5));
  });

  it("masks exactly 20 with no ellipsis", () => {
    expect(maskToken("a".repeat(20))).toBe("●".repeat(20));
  });

  it("caps at 20 dots and appends ellipsis when longer than 20", () => {
    expect(maskToken("a".repeat(21))).toBe("●".repeat(20) + "...");
    expect(maskToken("a".repeat(50))).toBe("●".repeat(20) + "...");
  });
});

describe("getNodeDimensions", () => {
  it("uses the node's width and height when both are present", () => {
    expect(getNodeDimensions(mkNode({ width: 300, height: 150 }))).toEqual({
      width: 300,
      height: 150,
    });
  });

  it("falls back to 400x200 when either dimension is missing or zero", () => {
    expect(getNodeDimensions(mkNode({}))).toEqual({ width: 400, height: 200 });
    expect(getNodeDimensions(mkNode({ width: 300 }))).toEqual({
      width: 400,
      height: 200,
    });
    expect(getNodeDimensions(mkNode({ width: 0, height: 100 }))).toEqual({
      width: 400,
      height: 200,
    });
  });
});

describe("getNodeCenter", () => {
  it("adds half of each dimension to the position", () => {
    expect(
      getNodeCenter({ x: 10, y: 20 }, { width: 400, height: 200 })
    ).toEqual({ x: 210, y: 120 });
    expect(getNodeCenter({ x: 0, y: 0 }, { width: 100, height: 50 })).toEqual({
      x: 50,
      y: 25,
    });
  });
});

describe("extractDynamicVariables", () => {
  it("extracts {{variable}} names without braces", () => {
    const vars = extractDynamicVariables("Hello {{name}} and {{age}}");
    expect(vars).toEqual(new Set(["name", "age"]));
  });

  it("allows dots inside {{variable}} but rejects internal spaces", () => {
    expect(extractDynamicVariables("{{a.b.c}}")).toEqual(new Set(["a.b.c"]));
    expect(extractDynamicVariables("{{ spaced }}")).toEqual(new Set());
  });

  it("extracts params.get and param.get double-quoted variable names", () => {
    expect(extractDynamicVariables('params.get("token")')).toEqual(
      new Set(["token"])
    );
    expect(extractDynamicVariables('param.get("single", "def")')).toEqual(
      new Set(["single"])
    );
  });

  it("handles escaped quotes from JSON.stringify", () => {
    expect(extractDynamicVariables('params.get(\\"secret\\", 0)')).toEqual(
      new Set(["secret"])
    );
  });

  it("does not match single-quoted params.get", () => {
    expect(extractDynamicVariables("params.get('nope')")).toEqual(new Set());
  });

  it("combines curly and params.get matches, returns empty set when none", () => {
    expect(
      extractDynamicVariables('Hi {{name}}, age params.get("age", 5)')
    ).toEqual(new Set(["name", "age"]));
    expect(extractDynamicVariables("no variables here")).toEqual(new Set());
  });
});

describe("extractDynamicVariablesAsRecord", () => {
  it("maps each variable to a required string schema", () => {
    expect(extractDynamicVariablesAsRecord("{{name}} {{age}}")).toEqual({
      name: { type: "string", required: true },
      age: { type: "string", required: true },
    });
  });

  it("returns an empty record when there are no variables", () => {
    expect(extractDynamicVariablesAsRecord("plain text")).toEqual({});
  });
});

describe("convertSchemaToParams", () => {
  it("returns an empty object for a falsy schema", () => {
    expect(convertSchemaToParams(null as unknown as Record<string, { type: string }>)).toEqual(
      {}
    );
  });

  it("preserves types and defaults required to false", () => {
    expect(
      convertSchemaToParams({
        a: { type: "number", required: true },
        b: { type: "string" },
      })
    ).toEqual({
      a: { type: "number", required: true },
      b: { type: "string", required: false },
    });
  });
});

describe("generateSampleOutput", () => {
  it("generates values per inputSchema field type", () => {
    const out = generateSampleOutput(
      asNodeData({
        inputSchema: {
          name: { type: "string" },
          count: { type: "number" },
          flag: { type: "boolean" },
          anyField: { type: "any" },
          weird: { type: "mystery" },
        },
      })
    );
    expect(out).toEqual({
      name: "sample_string_value",
      count: 42,
      flag: true,
      anyField: "sample_any_value",
      weird: "sample_value",
    });
  });

  it("generates array samples with and without items", () => {
    expect(
      generateSampleOutput(asNodeData({ inputSchema: { list: { type: "array" } } }))
    ).toEqual({ list: ["sample_array_item"] });
    expect(
      generateSampleOutput(
        asNodeData({ inputSchema: { list: { type: "array", items: { type: "number" } } } })
      )
    ).toEqual({ list: [42] });
  });

  it("generates object samples with and without properties", () => {
    expect(
      generateSampleOutput(asNodeData({ inputSchema: { obj: { type: "object" } } }))
    ).toEqual({ obj: { sample_key: "sample_value" } });
    expect(
      generateSampleOutput(
        asNodeData({ inputSchema: { obj: { type: "object", properties: { a: { type: "string" } } } } })
      )
    ).toEqual({ obj: { a: "sample_string_value" } });
  });

  it("extracts variables from a template into string samples", () => {
    expect(
      generateSampleOutput(asNodeData({ template: "Hello {{userName}}" }))
    ).toEqual({ userName: "sample_string_value" });
  });

  it("extracts variables from known text fields", () => {
    expect(
      generateSampleOutput(asNodeData({ pythonScript: 'x = params.get("token")' }))
    ).toEqual({ token: "sample_string_value" });
    expect(
      generateSampleOutput(asNodeData({ message: "Hi {{who}}" }))
    ).toEqual({ who: "sample_string_value" });
  });

  it("does not overwrite an inputSchema value with a template variable of the same name", () => {
    expect(
      generateSampleOutput(
        asNodeData({ inputSchema: { count: { type: "number" } }, template: "{{count}}" })
      )
    ).toEqual({ count: 42 });
  });
});

describe("generateTemplateFromInputSchema", () => {
  it("returns {} for null, undefined, or empty schema", () => {
    expect(generateTemplateFromInputSchema(null as unknown as NodeSchema)).toBe("{}");
    expect(generateTemplateFromInputSchema(undefined as unknown as NodeSchema)).toBe(
      "{}"
    );
    expect(generateTemplateFromInputSchema({} as NodeSchema)).toBe("{}");
  });

  it("quotes string-typed template values", () => {
    expect(
      generateTemplateFromInputSchema({ name: { type: "string" } } as NodeSchema)
    ).toBe('{"source.name":"{{direct_input.parameters.name}}"}');
  });

  it("leaves non-string template values unquoted", () => {
    expect(
      generateTemplateFromInputSchema({ count: { type: "number" } } as NodeSchema)
    ).toBe('{"source.count":{{direct_input.parameters.count}}}');
  });

  it("joins multiple entries with commas, honoring per-type quoting", () => {
    expect(
      generateTemplateFromInputSchema({
        a: { type: "string" },
        b: { type: "number" },
      } as NodeSchema)
    ).toBe(
      '{"source.a":"{{direct_input.parameters.a}}","source.b":{{direct_input.parameters.b}}}'
    );
  });
});

describe("getValueFromPath", () => {
  const obj = { a: { b: { c: 42 } }, n: null, x: 5 };

  it("returns undefined for missing object or empty path", () => {
    expect(getValueFromPath(null, "a")).toBeUndefined();
    expect(getValueFromPath(undefined, "a")).toBeUndefined();
    expect(getValueFromPath(obj, "")).toBeUndefined();
  });

  it("resolves nested dotted paths", () => {
    expect(getValueFromPath(obj, "a.b.c")).toBe(42);
    expect(getValueFromPath(obj, "a.b")).toEqual({ c: 42 });
  });

  it("returns undefined for a missing key", () => {
    expect(getValueFromPath(obj, "a.b.z")).toBeUndefined();
  });

  it("returns undefined when descending into a non-object", () => {
    expect(getValueFromPath(obj, "x.deeper")).toBeUndefined();
  });

  it("returns null when the resolved value is null", () => {
    expect(getValueFromPath(obj, "n")).toBeNull();
  });
});

describe("parseInputValue", () => {
  it("returns the raw value for empty or whitespace-only input", () => {
    expect(parseInputValue("", "number")).toBe("");
    expect(parseInputValue("   ", "number")).toBe("   ");
  });

  it("returns strings unchanged for string type", () => {
    expect(parseInputValue("hello", "string")).toBe("hello");
  });

  it("parses numbers, falling back to the original on failure", () => {
    expect(parseInputValue("42", "number")).toBe(42);
    expect(parseInputValue("3.14", "number")).toBe(3.14);
    expect(parseInputValue("12px", "number")).toBe(12);
    expect(parseInputValue("abc", "number")).toBe("abc");
  });

  it("parses booleans from multiple truthy/falsy spellings", () => {
    expect(parseInputValue("true", "boolean")).toBe(true);
    expect(parseInputValue("1", "boolean")).toBe(true);
    expect(parseInputValue("YES", "boolean")).toBe(true);
    expect(parseInputValue("false", "boolean")).toBe(false);
    expect(parseInputValue("0", "boolean")).toBe(false);
    expect(parseInputValue(" No ", "boolean")).toBe(false);
    expect(parseInputValue("maybe", "boolean")).toBe("maybe");
  });

  it("parses object and array JSON, falling back to the string on failure", () => {
    expect(parseInputValue('{"a":1}', "object")).toEqual({ a: 1 });
    expect(parseInputValue("[1,2]", "array")).toEqual([1, 2]);
    expect(parseInputValue("{bad", "object")).toBe("{bad");
  });

  it("parses 'any' as JSON first, then number, then boolean, then string", () => {
    expect(parseInputValue("42", "any")).toBe(42);
    expect(parseInputValue("true", "any")).toBe(true);
    expect(parseInputValue('{"k":1}', "any")).toEqual({ k: 1 });
    expect(parseInputValue("hello", "any")).toBe("hello");
    expect(parseInputValue("yes", "any")).toBe("yes");
  });

  it("returns the value for an unknown type (default branch)", () => {
    expect(parseInputValue("x", "mystery" as SchemaType)).toBe("x");
  });
});

describe("valueToString", () => {
  it("returns empty string for null and undefined", () => {
    expect(valueToString(null, "string")).toBe("");
    expect(valueToString(undefined, "number")).toBe("");
  });

  it("pretty-prints objects and arrays", () => {
    expect(valueToString({ a: 1 }, "object")).toBe(JSON.stringify({ a: 1 }, null, 2));
    expect(valueToString([1, 2], "array")).toBe(JSON.stringify([1, 2], null, 2));
  });

  it("stringifies booleans and other primitives", () => {
    expect(valueToString(true, "boolean")).toBe("true");
    expect(valueToString(42, "number")).toBe("42");
    expect(valueToString("hi", "string")).toBe("hi");
  });
});

describe("truncateNodeOutput", () => {
  it("truncates a top-level array to the default of 4 items", () => {
    expect(truncateNodeOutput([1, 2, 3, 4, 5, 6])).toEqual([1, 2, 3, 4]);
  });

  it("honors a custom maxItems", () => {
    expect(truncateNodeOutput([1, 2, 3, 4, 5], 2)).toEqual([1, 2]);
  });

  it("recursively truncates nested arrays", () => {
    expect(truncateNodeOutput([[1, 2, 3, 4, 5, 6]])).toEqual([[1, 2, 3, 4]]);
  });

  it("recurses through object values", () => {
    expect(truncateNodeOutput({ items: [1, 2, 3, 4, 5] })).toEqual({
      items: [1, 2, 3, 4],
    });
  });

  it("leaves primitives and null unchanged", () => {
    expect(truncateNodeOutput(5)).toBe(5);
    expect(truncateNodeOutput("x")).toBe("x");
    expect(truncateNodeOutput(null)).toBeNull();
  });
});

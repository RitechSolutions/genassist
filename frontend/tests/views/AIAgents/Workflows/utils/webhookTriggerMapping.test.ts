import { describe, it, expect } from "vitest";
import {
  buildCurlExample,
  buildEnvelope,
  buildTriggerInput,
  getPath,
  parseSamplePayload,
  sampleTriggerOutput,
} from "@/views/AIAgents/Workflows/nodeTypes/triggers/webhookTriggerMapping";

const envelope = (body: unknown, headers: Record<string, unknown> = {}) =>
  buildEnvelope(body, { headers, received_at: "2026-01-01T00:00:00Z" });

describe("getPath", () => {
  it("walks objects and arrays, matching keys case-insensitively as a fallback", () => {
    const data = { body: { items: [{ id: "a" }, { id: "b" }] }, headers: { "x-event": "e" } };
    expect(getPath(data, "body.items.1.id")).toEqual({ found: true, value: "b" });
    expect(getPath(data, "headers.X-Event")).toEqual({ found: true, value: "e" });
    expect(getPath(data, "body.items.5.id").found).toBe(false);
    expect(getPath(data, "").found).toBe(false);
  });

  it("distinguishes a null value from a missing key", () => {
    expect(getPath({ a: null }, "a")).toEqual({ found: true, value: null });
    expect(getPath({ a: null }, "b").found).toBe(false);
  });
});

describe("buildTriggerInput", () => {
  it("always carries the envelope and only sets message when mapped", () => {
    const { input, errors } = buildTriggerInput(envelope({ x: 1 }), {});
    expect(errors).toEqual([]);
    expect((input.webhook as { body: unknown }).body).toEqual({ x: 1 });
    expect("message" in input).toBe(false);
  });

  it("applies mappings, defaults and required rules like the backend", () => {
    const { input, errors } = buildTriggerInput(envelope({ order: { id: 42 } }, { "X-Source": "crm" }), {
      fieldMappings: [
        { key: "order_id", path: "body.order.id", required: true },
        { key: "priority", path: "body.priority", default: "normal" },
        { key: "source", path: "headers.x-source" },
        { key: "", path: "" },
      ],
    });
    expect(errors).toEqual([]);
    expect(input.order_id).toBe(42);
    expect(input.priority).toBe("normal");
    expect(input.source).toBe("crm");
  });

  it("reports missing required fields, reserved and invalid keys", () => {
    const { errors } = buildTriggerInput(envelope({}), {
      fieldMappings: [
        { key: "order_id", path: "body.order.id", required: true },
        { key: "webhook", path: "body.x" },
        { key: "bad key", path: "body.x" },
      ],
    });
    expect(errors).toHaveLength(3);
    expect(errors[0]).toContain("order_id");
  });

  it("stringifies a non-string message and falls back to empty", () => {
    expect(buildTriggerInput(envelope({ obj: { a: 1 } }), { messagePath: "body.obj" }).input.message).toBe('{"a":1}');
    expect(buildTriggerInput(envelope({}), { messagePath: "body.text" }).input.message).toBe("");
    expect(buildTriggerInput(envelope({}), { messagePath: "body.text", messageRequired: true }).errors).toHaveLength(1);
  });
});

describe("sample payload helpers", () => {
  it("parses JSON text and wraps garbage", () => {
    expect(parseSamplePayload('{"a": 1}')).toEqual({ a: 1 });
    expect(parseSamplePayload("  ")).toEqual({});
    expect(parseSamplePayload("nope")).toEqual({ raw: "nope" });
  });

  it("sampleTriggerOutput mirrors what the node returns in a test run", () => {
    const output = sampleTriggerOutput({
      name: "t",
      samplePayload: '{"text": "hi"}',
      messagePath: "body.text",
      fieldMappings: [{ key: "t", path: "body.text" }],
    });
    expect(output.message).toBe("hi");
    expect(output.t).toBe("hi");
    expect((output.webhook as { is_test: boolean }).is_test).toBe(true);
  });
});

describe("buildCurlExample", () => {
  it("emits a bearer POST with the compacted body", () => {
    const curl = buildCurlExample("https://h/api/webhook/execute/1?x-tenant-id=t", "POST", "bearer", '{ "a": 1 }');
    expect(curl).toContain("Authorization: Bearer <your secret>");
    expect(curl).toContain(`--data '{"a":1}'`);
  });

  it("omits the body for GET and signs for hmac", () => {
    expect(buildCurlExample("https://h/x", "GET", "bearer", "{}")).not.toContain("--data");
    const hmac = buildCurlExample("https://h/x", "POST", "hmac", "{}");
    expect(hmac).toContain("X-GenAssist-Signature");
    expect(hmac).toContain("openssl dgst -sha256 -hmac");
  });
});

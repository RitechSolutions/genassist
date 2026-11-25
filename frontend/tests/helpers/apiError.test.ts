import { describe, expect, it } from "vitest";
import { extractErrorMessage, throwIfErrorEnvelope } from "@/helpers/apiError";

describe("extractErrorMessage", () => {
  const FALLBACK = "Something went wrong";

  it("uses a plain string response body", () => {
    expect(
      extractErrorMessage({ response: { data: "boom" } }, FALLBACK)
    ).toBe("boom");
  });

  it("prefers data.error, then data.message, then data.detail", () => {
    expect(
      extractErrorMessage({ response: { data: { error: "E" } } }, FALLBACK)
    ).toBe("E");
    expect(
      extractErrorMessage({ response: { data: { message: "M" } } }, FALLBACK)
    ).toBe("M");
    expect(
      extractErrorMessage({ response: { data: { detail: "D" } } }, FALLBACK)
    ).toBe("D");
  });

  it("prefers error_detail, the AppException's case-specific text", () => {
    expect(
      extractErrorMessage(
        { response: { data: { error_detail: "Another save completed first.", error: "E" } } },
        FALLBACK
      )
    ).toBe("Another save completed first.");
  });

  it("falls through to error when error_detail is null", () => {
    expect(
      extractErrorMessage(
        { response: { data: { error_detail: null, error: "E" } } },
        FALLBACK
      )
    ).toBe("E");
  });

  it("honors precedence when several fields are present", () => {
    expect(
      extractErrorMessage(
        { response: { data: { error: "E", message: "M" } } },
        FALLBACK
      )
    ).toBe("E");
  });

  it("skips blank fields", () => {
    expect(
      extractErrorMessage(
        { response: { data: { error: "   ", message: "M" } } },
        FALLBACK
      )
    ).toBe("M");
  });

  it("reads the first msg from a FastAPI validation array", () => {
    expect(
      extractErrorMessage(
        { response: { data: { detail: [{ msg: "field required" }] } } },
        FALLBACK
      )
    ).toBe("field required");
  });

  it("reads msg from an indexed detail map", () => {
    expect(
      extractErrorMessage(
        { response: { data: { detail: { "0": { msg: "bad value" } } } } },
        FALLBACK
      )
    ).toBe("bad value");
  });

  it("names the field a validation error is about, in either detail shape", () => {
    const loc = ["body", "technique_configs", "not_contains"];

    expect(
      extractErrorMessage(
        { response: { data: { detail: [{ loc, msg: "Extra inputs are not permitted" }] } } },
        FALLBACK
      )
    ).toBe("technique_configs.not_contains: Extra inputs are not permitted");
    expect(
      extractErrorMessage(
        { response: { data: { detail: { "0": { loc, msg: "Extra inputs are not permitted" } } } } },
        FALLBACK
      )
    ).toBe("technique_configs.not_contains: Extra inputs are not permitted");
  });

  it("keeps list positions in the path and drops only the leading request part", () => {
    expect(
      extractErrorMessage(
        { response: { data: { detail: [{ loc: ["body", "case_ids", 0], msg: "bad uuid" }] } } },
        FALLBACK
      )
    ).toBe("case_ids.0: bad uuid");
    expect(
      extractErrorMessage(
        { response: { data: { detail: [{ loc: ["query", "limit"], msg: "too large" }] } } },
        FALLBACK
      )
    ).toBe("limit: too large");
  });

  it("falls back to a plain Error message", () => {
    expect(extractErrorMessage(new Error("plain failure"), FALLBACK)).toBe(
      "plain failure"
    );
  });

  it("returns the fallback when nothing usable is found", () => {
    expect(extractErrorMessage({}, FALLBACK)).toBe(FALLBACK);
    expect(extractErrorMessage(null, FALLBACK)).toBe(FALLBACK);
    expect(extractErrorMessage(undefined, FALLBACK)).toBe(FALLBACK);
    expect(
      extractErrorMessage({ response: { data: {} } }, FALLBACK)
    ).toBe(FALLBACK);
  });
});

describe("throwIfErrorEnvelope", () => {
  const thrownBy = (data: unknown) => {
    try {
      throwIfErrorEnvelope(data);
    } catch (err) {
      return err as Error & { response: { status: number; data: unknown } };
    }
    throw new Error("expected a throw");
  };

  it("throws the envelope with the server's text, status and body", () => {
    const envelope = {
      error: "The prompt check did not finish within the time budget.",
      error_code: 504,
      error_key: "PROMPT_EXECUTION_TIMEOUT",
      error_detail: null,
    };

    const thrown = thrownBy(envelope);

    expect(thrown).toBeInstanceOf(Error);
    expect(thrown.message).toBe(
      "The prompt check did not finish within the time budget."
    );
    expect(thrown.response.status).toBe(504);
    expect(thrown.response.data).toBe(envelope);
    expect(extractErrorMessage(thrown, "x")).toBe(
      "The prompt check did not finish within the time budget."
    );
  });

  it("prefers error_detail and never shows an empty message", () => {
    expect(
      thrownBy({ error: "E", error_code: 500, error_detail: "boom" }).message
    ).toBe("boom");
    expect(thrownBy({ error: "", error_code: 500 }).message).toBe(
      "Request failed with status code 500"
    );
  });

  it("passes success bodies, per-case errors and null through", () => {
    const success = { status: "success", output: "4 items" };
    const evaluation = { results: [{ error: "x" }], summary: {}, provenance: {} };
    const noCode = { error: "x" };

    expect(throwIfErrorEnvelope(success)).toBe(success);
    expect(throwIfErrorEnvelope(evaluation)).toBe(evaluation);
    expect(throwIfErrorEnvelope(null)).toBeNull();
    expect(throwIfErrorEnvelope(noCode)).toBe(noCode);
  });
});

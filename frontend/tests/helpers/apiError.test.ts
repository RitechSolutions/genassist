import { describe, expect, it } from "vitest";
import { extractErrorMessage } from "@/helpers/apiError";

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

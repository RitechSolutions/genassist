import { describe, expect, it } from "vitest";
import { isRunConflict, runStartErrorMessage } from "@/views/TestSuites/helpers/runErrors";

const httpError = (status: number, data?: unknown) => ({ response: { status, data } });

describe("runStartErrorMessage", () => {
  it("says the evaluation is already running on a 409", () => {
    expect(
      runStartErrorMessage(httpError(409, { detail: "This evaluation is already running." })),
    ).toBe("This evaluation is already running.");
  });

  it("keeps the version message for a target that is not a version", () => {
    expect(
      runStartErrorMessage(
        httpError(400, {
          error: "The target workflow is not a version of the evaluation's workflow.",
          error_key: "evaluation_target_not_a_version",
        }),
      ),
    ).toBe("That version does not belong to this workflow.");
  });

  it("asks for a workflow when the evaluation has none", () => {
    expect(
      runStartErrorMessage(httpError(400, { error_key: "evaluation_workflow_required" })),
    ).toBe("This evaluation has no workflow. Edit it and choose one.");
  });

  it("does not blame the version for any other 400", () => {
    expect(
      runStartErrorMessage(
        httpError(400, { error: "Suite has no test cases.", error_key: "suite_empty" }),
      ),
    ).toBe("Suite has no test cases.");
    expect(runStartErrorMessage(httpError(400, { detail: "Bad request body." }))).toBe(
      "Bad request body.",
    );
  });

  it("falls back to a generic message when nothing readable comes back", () => {
    expect(runStartErrorMessage(httpError(500, {}))).toBe("Couldn't start the run.");
    expect(runStartErrorMessage(undefined)).toBe("Couldn't start the run.");
  });

  it("uses a network error's own message", () => {
    expect(runStartErrorMessage({ message: "Network Error" })).toBe("Network Error");
  });
});

describe("isRunConflict", () => {
  it("is true only for a 409", () => {
    expect(isRunConflict(httpError(409))).toBe(true);
    expect(isRunConflict(httpError(400))).toBe(false);
    expect(isRunConflict(null)).toBe(false);
  });
});

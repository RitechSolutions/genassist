import { describe, expect, it } from "vitest";
import { postLoginPath } from "@/views/Login/helpers/postLoginPath";

describe("postLoginPath", () => {
  it("returns to the page the user was sent from, query included", () => {
    expect(postLoginPath({ pathname: "/reported-feedback", search: "?feedback=f1" })).toBe(
      "/reported-feedback?feedback=f1",
    );
  });

  it("keeps a plain path as it is", () => {
    expect(postLoginPath({ pathname: "/transcripts" })).toBe("/transcripts");
    expect(postLoginPath({ pathname: "/transcripts", search: "" })).toBe("/transcripts");
  });

  it("falls back to the dashboard, never onboarding", () => {
    expect(postLoginPath()).toBe("/dashboard");
    expect(postLoginPath({ pathname: "/onboarding", search: "?step=2" })).toBe("/dashboard");
  });
});

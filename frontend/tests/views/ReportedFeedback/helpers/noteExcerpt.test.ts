import { describe, expect, it } from "vitest";
import { noteExcerpt } from "@/views/ReportedFeedback/helpers/noteExcerpt";

const near = "Raised the KB lookup timeout from 8s to 20s.";
const deep = "Checked the logs with the help desk for two days, then raised the tool timeout to 20s.";

describe("noteExcerpt", () => {
  it("returns the whole note when the match is near the start", () => {
    expect(noteExcerpt(near, "timeout")).toBe(near);
  });

  it("starts 30 characters before a deep match, after an ellipsis", () => {
    expect(noteExcerpt(deep, "timeout")).toBe("…wo days, then raised the tool timeout to 20s.");
  });

  it("matches regardless of case", () => {
    expect(noteExcerpt(deep, "TIMEOUT")).toBe("…wo days, then raised the tool timeout to 20s.");
  });

  it("returns the whole note when the term isn't found", () => {
    expect(noteExcerpt(deep, "retry")).toBe(deep);
  });
});

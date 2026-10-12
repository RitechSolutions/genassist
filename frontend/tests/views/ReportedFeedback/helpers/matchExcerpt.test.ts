import { describe, expect, it } from "vitest";
import { matchExcerpt, splitMatches } from "@/views/ReportedFeedback/helpers/matchExcerpt";

const near = "Raised the KB lookup timeout from 8s to 20s.";
const deep = "Checked the logs with the help desk for two days, then raised the tool timeout to 20s.";

describe("matchExcerpt", () => {
  it("returns the whole text when there is no search", () => {
    expect(matchExcerpt(deep, "")).toBe(deep);
  });

  it("returns the whole text when the match is near the start", () => {
    expect(matchExcerpt(near, "timeout")).toBe(near);
  });

  it("starts 30 characters before a deep match, after an ellipsis", () => {
    expect(matchExcerpt(deep, "timeout")).toBe("…wo days, then raised the tool timeout to 20s.");
  });

  it("matches regardless of case", () => {
    expect(matchExcerpt(deep, "TIMEOUT")).toBe("…wo days, then raised the tool timeout to 20s.");
  });

  it("cuts at the match even when lowercasing would lengthen the text", () => {
    const turkish = "İADE İŞLEMİ İÇİN İKİ İSTEK İLETİLDİ, then raised the tool timeout to 20s.";
    expect(matchExcerpt(turkish, "timeout")).toBe("…LETİLDİ, then raised the tool timeout to 20s.");
  });

  it("returns the whole text when the term isn't found", () => {
    expect(matchExcerpt(deep, "retry")).toBe(deep);
  });
});

describe("splitMatches", () => {
  it("flags every match, whatever its case", () => {
    expect(splitMatches("Shipping, then looping", "PIN")).toEqual([
      { text: "Ship", match: false },
      { text: "pin", match: true },
      { text: "g, then loo", match: false },
      { text: "pin", match: true },
      { text: "g", match: false },
    ]);
  });

  it("treats regex characters in the search as plain text", () => {
    expect(splitMatches("We don't (yet). Ship now", "(yet).")).toEqual([
      { text: "We don't ", match: false },
      { text: "(yet).", match: true },
      { text: " Ship now", match: false },
    ]);
  });

  it("keeps the text whole when there is no search", () => {
    expect(splitMatches("Shipping", "")).toEqual([{ text: "Shipping", match: false }]);
  });
});

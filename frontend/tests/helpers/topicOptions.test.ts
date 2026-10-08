import { describe, expect, it } from "vitest";
import { subtopicsFor, withCurrentOption } from "@/helpers/topicOptions";

const OPTIONS = [
  { name: "Refund", subtopics: ["Wrong plate", "Double charge"] },
  { name: "Other", subtopics: [] },
];

describe("subtopicsFor", () => {
  it("returns the chosen topic's sub-topics", () => {
    expect(subtopicsFor(OPTIONS, "Refund")).toEqual(["Wrong plate", "Double charge"]);
  });

  it("returns none for no topic, 'all' or a topic that is not configured", () => {
    expect(subtopicsFor(OPTIONS, null)).toEqual([]);
    expect(subtopicsFor(OPTIONS, "all")).toEqual([]);
    expect(subtopicsFor(OPTIONS, "refund")).toEqual([]);
  });

  it("keeps a selected sub-topic that is no longer configured", () => {
    expect(subtopicsFor(OPTIONS, "Refund", "Wrong plate")).toEqual(["Wrong plate", "Double charge"]);
    expect(subtopicsFor(OPTIONS, "Other", "Lost ticket")).toEqual(["Lost ticket"]);
    expect(subtopicsFor(OPTIONS, "Other", "all")).toEqual([]);
  });
});

describe("withCurrentOption", () => {
  it("keeps the options as they are when the current value is configured or unset", () => {
    expect(withCurrentOption(OPTIONS, "Refund")).toBe(OPTIONS);
    expect(withCurrentOption(OPTIONS, "all")).toBe(OPTIONS);
    expect(withCurrentOption(OPTIONS, null)).toBe(OPTIONS);
    expect(withCurrentOption(OPTIONS, "")).toBe(OPTIONS);
  });

  it("appends an unlisted current value so a deep link stays selectable", () => {
    expect(withCurrentOption(OPTIONS, "Billing Questions")).toEqual([
      ...OPTIONS,
      { name: "Billing Questions", subtopics: [] },
    ]);
  });
});

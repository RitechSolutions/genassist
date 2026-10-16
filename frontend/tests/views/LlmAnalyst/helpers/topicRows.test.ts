import { describe, expect, it } from "vitest";

import {
  applySubtopicEdit,
  parseTopicRows,
  serializeTopicRows,
  topicNameError,
  type TopicRow,
} from "@/views/LlmAnalyst/helpers/topicRows";

describe("parseTopicRows", () => {
  it("reads a plain list as topics without sub-topics", () => {
    expect(parseTopicRows(["Billing", "Other"])).toEqual([
      { name: "Billing", subtopics: [] },
      { name: "Other", subtopics: [] },
    ]);
  });

  it("groups sub-topics under their topic, creating it on first sight", () => {
    expect(
      parseTopicRows([
        "Refund > Wrong plate",
        "Billing",
        "Refund",
        "Refund > Late",
      ]),
    ).toEqual([
      { name: "Refund", subtopics: ["Wrong plate", "Late"] },
      { name: "Billing", subtopics: [] },
    ]);
  });

  it("splits on the first separator only, like the backend", () => {
    expect(parseTopicRows(["A > A1 > x"])).toEqual([
      { name: "A", subtopics: ["A1 > x"] },
    ]);
  });

  it("trims and dedupes case-insensitively, keeping the first spelling", () => {
    expect(
      parseTopicRows([" refund ", "Refund", "refund > Late", "Refund > late "]),
    ).toEqual([{ name: "refund", subtopics: ["Late"] }]);
  });

  it("skips blank names, non-strings and non-lists", () => {
    expect(parseTopicRows([">", "A >", 3, null])).toEqual([
      { name: "A", subtopics: [] },
    ]);
    expect(parseTopicRows(undefined)).toEqual([]);
    expect(parseTopicRows("Billing")).toEqual([]);
  });
});

describe("serializeTopicRows", () => {
  const rows: TopicRow[] = [
    { name: " Refund ", subtopics: ["Wrong plate", "Late"] },
    { name: "  ", subtopics: ["Lost"] },
    { name: "Billing", subtopics: [] },
  ];

  it("writes each name, then its sub-topics, skipping unnamed rows", () => {
    expect(serializeTopicRows(rows)).toEqual([
      "Refund",
      "Refund > Wrong plate",
      "Refund > Late",
      "Billing",
    ]);
  });

  it("round-trips with parseTopicRows", () => {
    const stored = ["Refund", "Refund > Wrong plate", "A", "A > A1 > x"];
    expect(serializeTopicRows(parseTopicRows(stored))).toEqual(stored);
    expect(parseTopicRows(serializeTopicRows(rows))).toEqual([
      { name: "Refund", subtopics: ["Wrong plate", "Late"] },
      { name: "Billing", subtopics: [] },
    ]);
  });
});

describe("topicNameError", () => {
  const rows: TopicRow[] = [
    { name: "Refund", subtopics: [] },
    { name: "Billing", subtopics: [] },
  ];

  it("requires a name without the separator", () => {
    expect(topicNameError("  ", rows)).toBe("Name is required");
    expect(topicNameError("Refund > Late", rows)).toBe(
      "Names cannot contain >",
    );
  });

  it("refuses another row's name in any casing, but not the row's own", () => {
    expect(topicNameError(" billing ", rows)).toBe("This topic already exists");
    expect(topicNameError("billing", rows, 1)).toBeNull();
    expect(topicNameError("Payment", rows)).toBeNull();
  });

  it("refuses the filters' \"all\" value in any casing", () => {
    expect(topicNameError(" All ", rows)).toBe('"all" is reserved');
  });
});

describe("applySubtopicEdit", () => {
  it("keeps a stored sub-topic that holds the separator", () => {
    expect(applySubtopicEdit(["A1 > x"], ["A1 > x", " Late "])).toEqual([
      "A1 > x",
      "Late",
    ]);
  });

  it("refuses new chips with the separator, \"all\" or another chip's name in any casing", () => {
    expect(
      applySubtopicEdit(
        ["Refund"],
        ["Refund", "refund", "B > C", "All", "Late", "late"],
      ),
    ).toEqual(["Refund", "Late"]);
  });

  it("applies removals", () => {
    expect(applySubtopicEdit(["A1 > x", "Late"], ["Late"])).toEqual(["Late"]);
  });
});

import { describe, expect, it } from "vitest";

import type { IssueStatus } from "@/services/issueStatuses";
import {
  changedFields,
  issueStatusKeyError,
  moveStatus,
} from "@/views/Settings/helpers/issueStatusForm";

const status = (key: string, position: number, is_active = 1): IssueStatus => ({
  id: key,
  key,
  label: key,
  category: "in_progress",
  position,
  color: "blue",
  is_active,
});

describe("issueStatusKeyError", () => {
  it("accepts lower snake case keys, trimmed", () => {
    expect(issueStatusKeyError("needs_fix")).toBeNull();
    expect(issueStatusKeyError(" qa2 ")).toBeNull();
    expect(issueStatusKeyError("all_done")).toBeNull();
  });

  it.each([
    "",
    "  ",
    "Needs Fix",
    "1abc",
    "a",
    "a>b",
    "needs-fix",
    "x".repeat(51),
  ])("rejects %j", (key) => {
    expect(issueStatusKeyError(key)).not.toBeNull();
  });

  it("reserves the filter's 'all' value", () => {
    expect(issueStatusKeyError("all")).toBe('"all" is reserved');
  });
});

describe("changedFields", () => {
  const blocked = { ...status("blocked", 0), label: "Blocked" };
  const values = {
    key: "blocked",
    label: "Blocked",
    category: blocked.category,
    color: "blue",
  };

  it("is empty when nothing changed, ignoring label padding", () => {
    expect(changedFields(blocked, { ...values, label: " Blocked " })).toEqual(
      {},
    );
  });

  it("lists only the changed fields", () => {
    expect(
      changedFields(blocked, { ...values, label: "On hold ", color: "red" }),
    ).toEqual({
      label: "On hold",
      color: "red",
    });
  });
});

describe("moveStatus", () => {
  const list = [
    status("open", 0),
    status("old", 1, 0),
    status("blocked", 2),
    status("done", 3),
  ];

  it("swaps with the neighbouring active status, skipping retired ones", () => {
    expect(moveStatus(list, "blocked", -1)).toEqual([
      "blocked",
      "open",
      "done",
    ]);
    expect(moveStatus(list, "open", 1)).toEqual(["blocked", "open", "done"]);
  });

  it("follows position order, not array order", () => {
    expect(moveStatus([...list].reverse(), "done", -1)).toEqual([
      "open",
      "done",
      "blocked",
    ]);
  });

  it("returns null at either end and for a retired status", () => {
    expect(moveStatus(list, "open", -1)).toBeNull();
    expect(moveStatus(list, "done", 1)).toBeNull();
    expect(moveStatus(list, "old", 1)).toBeNull();
  });
});

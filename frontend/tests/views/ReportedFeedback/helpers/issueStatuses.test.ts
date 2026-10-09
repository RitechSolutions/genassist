import { describe, expect, it } from "vitest";
import type { IssueStatus } from "@/services/issueStatuses";
import {
  activeStatuses,
  categoryTotals,
  statusMeta,
  withCurrentStatus,
} from "@/views/ReportedFeedback/helpers/issueStatuses";

const status = (over: Partial<IssueStatus> & Pick<IssueStatus, "key">): IssueStatus => ({
  id: over.key,
  label: over.key,
  category: "todo",
  position: 0,
  color: "amber",
  is_active: 1,
  ...over,
});

const LIST: IssueStatus[] = [
  status({ key: "resolved", label: "Resolved", category: "done", position: 4, color: "emerald" }),
  status({ key: "open", label: "Open", position: 0 }),
  status({ key: "blocked", label: "Blocked", category: "in_progress", position: 2, color: "red", is_active: 0 }),
  status({ key: "in_progress", label: "In Progress", category: "in_progress", position: 1, color: "blue" }),
];

describe("activeStatuses", () => {
  it("drops retired statuses and sorts by position", () => {
    expect(activeStatuses(LIST).map((s) => s.key)).toEqual(["open", "in_progress", "resolved"]);
  });
});

describe("statusMeta", () => {
  it("uses the configured label and palette classes", () => {
    expect(statusMeta(LIST, "in_progress")).toEqual({
      label: "In Progress",
      className: "border-blue-300 bg-blue-50 text-blue-700",
      retired: false,
    });
  });

  it("marks a retired status but keeps its label", () => {
    expect(statusMeta(LIST, "blocked")).toMatchObject({ label: "Blocked", retired: true });
  });

  it("falls back to the key and neutral classes for an unknown key or colour", () => {
    expect(statusMeta(LIST, "legacy_key")).toMatchObject({
      label: "legacy_key",
      className: "border-zinc-300 bg-zinc-100 text-zinc-600",
      retired: true,
    });
    expect(statusMeta([status({ key: "x", color: "magenta" })], "x").className).toBe(
      "border-zinc-300 bg-zinc-100 text-zinc-600",
    );
  });
});

describe("withCurrentStatus", () => {
  it("lists active keys only when the current one is active or unset", () => {
    expect(withCurrentStatus(LIST, "open")).toEqual(["open", "in_progress", "resolved"]);
    expect(withCurrentStatus(LIST, "all")).toEqual(["open", "in_progress", "resolved"]);
    expect(withCurrentStatus(LIST, null)).toEqual(["open", "in_progress", "resolved"]);
  });

  it("keeps a retired or unknown current key selectable", () => {
    expect(withCurrentStatus(LIST, "blocked")).toEqual(["open", "in_progress", "resolved", "blocked"]);
    expect(withCurrentStatus(LIST, "nope")).toEqual(["open", "in_progress", "resolved", "nope"]);
  });

  it("lists retired keys after the active ones when asked, without repeating the current key", () => {
    const keys = ["open", "in_progress", "resolved", "blocked"];
    expect(withCurrentStatus(LIST, "all", { includeRetired: true })).toEqual(keys);
    expect(withCurrentStatus(LIST, "blocked", { includeRetired: true })).toEqual(keys);
    expect(withCurrentStatus(LIST, "nope", { includeRetired: true })).toEqual([...keys, "nope"]);
  });
});

describe("categoryTotals", () => {
  it("sums counts by category, retired statuses included, unknown keys ignored", () => {
    const summary = {
      total: 10,
      by_status: { open: 2, in_progress: 1, blocked: 3, resolved: 4, legacy_key: 9 },
    };
    expect(categoryTotals(summary, LIST)).toEqual({ todo: 2, in_progress: 4, done: 4 });
  });
});

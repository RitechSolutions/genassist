import { parseISO } from "date-fns";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  draftToPatch,
  formatDateOnly,
  isDraftDirty,
  toDateOnly,
  toDraft,
} from "@/views/ReportedFeedback/helpers/triageDraft";

const saved = { fix_version: "2.3", target_rollout_date: "2026-10-20" };
const empty = { fix_version: null, target_rollout_date: null };

describe("draftToPatch", () => {
  it("is empty and clean for an untouched draft", () => {
    expect(draftToPatch(saved, toDraft(saved))).toEqual({});
    expect(isDraftDirty(empty, toDraft(empty))).toBe(false);
  });

  it("ignores whitespace-only edits to the version", () => {
    expect(draftToPatch(saved, { ...toDraft(saved), fix_version: " 2.3 " })).toEqual({});
    expect(draftToPatch(empty, { ...toDraft(empty), fix_version: "   " })).toEqual({});
  });

  it("sends only the changed field, trimmed", () => {
    expect(draftToPatch(saved, { ...toDraft(saved), fix_version: " 2.4 " })).toEqual({
      fix_version: "2.4",
    });
    expect(draftToPatch(saved, { ...toDraft(saved), target_rollout_date: "2026-11-01" })).toEqual({
      target_rollout_date: "2026-11-01",
    });
  });

  it("sends null for cleared fields", () => {
    const patch = draftToPatch(saved, { fix_version: "", target_rollout_date: null });
    expect(patch).toEqual({ fix_version: null, target_rollout_date: null });
    expect(isDraftDirty(saved, { fix_version: "", target_rollout_date: null })).toBe(true);
  });
});

describe("date-only values", () => {
  // West of UTC, reading "2026-10-20" as UTC midnight would show the 19th.
  const originalTz = process.env.TZ;
  beforeAll(() => {
    process.env.TZ = "America/Los_Angeles";
  });
  afterAll(() => {
    if (originalTz === undefined) delete process.env.TZ;
    else process.env.TZ = originalTz;
  });

  it("shows the picked day whatever the time zone", () => {
    expect(formatDateOnly("2026-10-20")).toBe("20 Oct 2026");
  });

  it("round-trips through the calendar's Date", () => {
    expect(toDateOnly(parseISO("2026-10-20"))).toBe("2026-10-20");
    expect(toDateOnly(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});

import { describe, expect, it } from "vitest";
import type { ReportedFeedbackItem } from "@/services/reportedFeedback";
import { applyIssuePatch, pickPatchedFields } from "@/views/ReportedFeedback/helpers/issuePatch";

const item = (feedback_id: string, over: Partial<ReportedFeedbackItem> = {}): ReportedFeedbackItem => ({
  feedback_id,
  message_id: `m-${feedback_id}`,
  conversation_id: "c1",
  agent_id: null,
  workflow_name: null,
  text: "Hello",
  speaker: "agent",
  comment: "Wrong answer",
  rating: null,
  status: "open",
  reported_by: null,
  reported_at: "2026-10-01T10:00:00Z",
  conversation_topic: null,
  conversation_subtopic: null,
  conversation_date: null,
  fix_version: null,
  target_rollout_date: null,
  ...over,
});

describe("applyIssuePatch", () => {
  it("updates one row and keeps the other rows' identity", () => {
    const rows = [item("a"), item("b")];
    const next = applyIssuePatch(rows, "b", { status: "resolved" });

    expect(next).not.toBe(rows);
    expect(next[0]).toBe(rows[0]);
    expect(next[1]).toEqual({ ...rows[1], status: "resolved" });
    expect(rows[1].status).toBe("open");
  });
});

describe("pickPatchedFields", () => {
  it("captures the current values of exactly the patched keys, nulls included", () => {
    const issue = item("a", { status: "in_progress", fix_version: "2.3" });
    expect(pickPatchedFields(issue, { fix_version: null, target_rollout_date: "2026-11-01" })).toEqual({
      fix_version: "2.3",
      target_rollout_date: null,
    });
    expect(pickPatchedFields(issue, { status: "resolved" })).toEqual({ status: "in_progress" });
  });
});

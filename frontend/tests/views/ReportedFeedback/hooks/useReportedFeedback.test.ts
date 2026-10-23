import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/config/api", () => ({ apiRequest: vi.fn() }));

import { MutationObserver, QueryClient, QueryObserver } from "@tanstack/react-query";
import { apiRequest } from "@/config/api";
import type {
  IssuePatch,
  MessageIssueRow,
  ReportedFeedbackItem,
  ReportedFeedbackResult,
} from "@/services/reportedFeedback";
import {
  cacheIssue,
  issuePatchMutation,
  issueQuery,
} from "@/views/ReportedFeedback/hooks/useReportedFeedback";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

const LIST_KEY = ["reported-feedback", "list", { skip: 0 }];
const SUMMARY_KEY = ["reported-feedback", "summary", {}];

const item = (over: Partial<ReportedFeedbackItem> = {}): ReportedFeedbackItem => ({
  feedback_id: "f1",
  message_id: "m1",
  conversation_id: "c1",
  agent_id: null,
  agent_name: null,
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
  matched_note: null,
  ...over,
});

const saved = (over: Partial<MessageIssueRow>): MessageIssueRow => ({
  id: "i1",
  message_feedback_id: "f1",
  status: "open",
  fix_version: null,
  target_rollout_date: null,
  resolved_by: null,
  resolved_at: null,
  updated_at: null,
  ...over,
});

const page = (items: ReportedFeedbackItem[]): ReportedFeedbackResult => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  total_pages: 1,
});

const setup = () => {
  const client = new QueryClient();
  client.setQueryData(LIST_KEY, page([item()]));
  client.setQueryData(SUMMARY_KEY, { total: 1, by_status: { open: 1 } });
  return {
    client,
    save: (patch: IssuePatch) =>
      new MutationObserver(client, issuePatchMutation(client)).mutate({ issue: item(), patch }),
    listed: () => client.getQueryData<ReportedFeedbackResult>(LIST_KEY)?.items[0],
    countsStale: () => client.getQueryState(SUMMARY_KEY)?.isInvalidated,
  };
};

describe("issuePatchMutation", () => {
  it("shows the saved status in the cached list and refreshes the counts", async () => {
    const { save, listed, countsStale } = setup();
    mockApiRequest.mockResolvedValue(saved({ status: "resolved" }) as never);

    await save({ status: "resolved" });

    expect(listed()?.status).toBe("resolved");
    expect(countsStale()).toBe(true);
  });

  it("leaves the counts alone after a triage-only save", async () => {
    const { save, listed, countsStale } = setup();
    mockApiRequest.mockResolvedValue(saved({ fix_version: "2.4.1" }) as never);

    await save({ fix_version: "2.4.1" });

    expect(listed()?.fix_version).toBe("2.4.1");
    expect(countsStale()).toBe(false);
  });

  it("refreshes the report's history after a save", async () => {
    const { client, save } = setup();
    const historyKey = (feedbackId: string) => ["reported-feedback", "history", feedbackId];
    client.setQueryData(historyKey("f1"), []);
    client.setQueryData(historyKey("f2"), []);
    mockApiRequest.mockResolvedValue(saved({ fix_version: "2.4.1" }) as never);

    await save({ fix_version: "2.4.1" });

    expect(client.getQueryState(historyKey("f1"))?.isInvalidated).toBe(true);
    expect(client.getQueryState(historyKey("f2"))?.isInvalidated).toBe(false);
  });

  it("shows a save in the open report", async () => {
    const { client, save } = setup();
    cacheIssue(client, item());
    mockApiRequest.mockResolvedValue(saved({ status: "resolved" }) as never);

    await save({ status: "resolved" });

    expect(client.getQueryData(issueQuery("f1").queryKey)?.items[0].status).toBe("resolved");
  });

  it("puts the patched status back when the save fails", async () => {
    const { save, listed } = setup();
    mockApiRequest.mockRejectedValue(new Error("Network down"));

    await expect(save({ status: "resolved" })).rejects.toThrow("Network down");

    expect(listed()?.status).toBe("open");
  });

  it("refetches a list page whose first load the save interrupted", async () => {
    const client = new QueryClient();
    const loaded = page([item({ status: "resolved" })]);
    const queryFn = vi
      .fn()
      .mockReturnValueOnce(new Promise(() => {}))
      .mockResolvedValueOnce(loaded);
    const observer = new QueryObserver(client, { queryKey: LIST_KEY, queryFn });
    const unsubscribe = observer.subscribe(() => {});
    mockApiRequest.mockResolvedValue(saved({ status: "resolved" }) as never);

    await new MutationObserver(client, issuePatchMutation(client)).mutate({
      issue: item(),
      patch: { status: "resolved" },
    });

    await vi.waitFor(() => expect(observer.getCurrentResult().data).toEqual(loaded));
    expect(queryFn).toHaveBeenCalledTimes(2);
    unsubscribe();
  });
});

describe("issueQuery", () => {
  it("shows the cached row at once and then the server's copy", async () => {
    const client = new QueryClient();
    cacheIssue(client, item({ status: "open" }));
    mockApiRequest.mockResolvedValue(page([item({ status: "resolved" })]) as never);

    const observer = new QueryObserver(client, issueQuery("f1"));
    const unsubscribe = observer.subscribe(() => {});

    expect(observer.getCurrentResult().data?.status).toBe("open");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=1&feedback_id=f1");
    await vi.waitFor(() => expect(observer.getCurrentResult().data?.status).toBe("resolved"));
    unsubscribe();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import {
  addIssueNote,
  EMPTY_SUMMARY,
  fetchIssueNotes,
  fetchReportedFeedback,
  fetchReportedFeedbackSummary,
  updateFeedbackIssue,
} from "@/services/reportedFeedback";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

const EMPTY_RESULT = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
};

describe("fetchReportedFeedback", () => {
  it("uses only limit=20 with default params (skip omitted)", async () => {
    const resp = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
    mockApiRequest.mockResolvedValue(resp as never);
    const result = await fetchReportedFeedback();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
    expect(result).toBe(resp);
  });

  it("appends all provided params in order", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({
      skip: 10,
      limit: 50,
      status: "open",
      from_date: "2025-01-01",
      to_date: "2025-02-01",
      workflow_id: "w1",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/issues?skip=10&limit=50&status=open&from_date=2025-01-01&to_date=2025-02-01&workflow_id=w1"
    );
  });

  it("appends topic and subtopic after the existing params", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({
      status: "open",
      workflow_id: "w1",
      topic: "Payment issue",
      subtopic: "Declined payment",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/issues?limit=20&status=open&workflow_id=w1&topic=Payment+issue&subtopic=Declined+payment"
    );
  });

  it("omits the status param when status is 'all'", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ status: "all" });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
  });

  it("clamps limit to the backend max of 100", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ limit: 500 });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=100");
  });

  it("falls back to limit=20 when limit is not positive", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ limit: 0 });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
  });

  it("returns the EMPTY_RESULT fallback when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchReportedFeedback()).toEqual(EMPTY_RESULT);
  });
});

describe("fetchReportedFeedbackSummary", () => {
  it("GETs the bare summary path when no filter is set", async () => {
    const summary = { total: 3, by_status: { open: 3 } };
    mockApiRequest.mockResolvedValue(summary as never);
    expect(await fetchReportedFeedbackSummary()).toBe(summary);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues/summary");
  });

  it("sends only the filters that are set", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_SUMMARY as never);
    await fetchReportedFeedbackSummary({
      from_date: "2026-10-01",
      to_date: "2026-10-06 23:59:59",
      topic: "",
      subtopic: "Wrong plate",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/issues/summary?from_date=2026-10-01&to_date=2026-10-06+23%3A59%3A59&subtopic=Wrong+plate"
    );
  });

  it("falls back to the empty summary when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchReportedFeedbackSummary()).toEqual({ total: 0, by_status: {} });
  });
});

describe("updateFeedbackIssue", () => {
  it("PATCHes the issue with explicit nulls kept so they clear the fields", async () => {
    const row = { message_feedback_id: "f1", status: "open", fix_version: null };
    mockApiRequest.mockResolvedValue(row as never);
    const result = await updateFeedbackIssue("f1", {
      fix_version: null,
      target_rollout_date: null,
    });
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "conversations/issues/f1", {
      fix_version: null,
      target_rollout_date: null,
    });
    expect(result).toBe(row);
  });

  it("throws when apiRequest resolves null (403)", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateFeedbackIssue("f1", { status: "resolved" })).rejects.toThrow();
  });
});

describe("issue notes", () => {
  it("GETs the notes of one issue", async () => {
    const notes = [{ id: "n1", body: "Fixed in 2.3" }];
    mockApiRequest.mockResolvedValue(notes as never);
    expect(await fetchIssueNotes("f1")).toBe(notes);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues/f1/notes");
  });

  it("returns [] when the notes request resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchIssueNotes("f1")).toEqual([]);
  });

  it("POSTs the note body and returns the created entry", async () => {
    const note = { id: "n2", body: "Escalated" };
    mockApiRequest.mockResolvedValue(note as never);
    expect(await addIssueNote("f1", "Escalated")).toBe(note);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "conversations/issues/f1/notes", {
      body: "Escalated",
    });
  });

  it("throws when adding a note resolves null (403)", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(addIssueNote("f1", "x")).rejects.toThrow();
  });
});

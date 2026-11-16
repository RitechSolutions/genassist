import { describe, it, expect } from "vitest";

import {
  INDEXING_FOLLOW_LIMIT_MS,
  INDEXING_REFRESH_MS,
  indexingRefreshInterval,
  isIndexedOnSave,
  isIndexingStatus,
  isSyncErrorStatus,
  knowledgeBaseStatusLabel,
  syncStatusBadgeVariant,
} from "@/views/KnowledgeBase/utils/syncStatus";

describe("knowledge base status", () => {
  it.each([
    ["indexing", "Indexing", "outline"],
    ["success", "Ready", "success"],
    ["success_with_warnings", "Ready with warnings", "secondary"],
    ["error", "Failed", "destructive"],
    ["failed", "Failed", "destructive"],
    ["paused", "paused", "outline"],
  ])("shows %s as %s", (status, label, variant) => {
    expect(knowledgeBaseStatusLabel(status)).toBe(label);
    expect(syncStatusBadgeVariant(status)).toBe(variant);
  });

  it("tells a failed and an indexing knowledge base apart from a ready one", () => {
    expect(isSyncErrorStatus("error")).toBe(true);
    expect(isSyncErrorStatus("success")).toBe(false);
    expect(isSyncErrorStatus(null)).toBe(false);
    expect(isIndexingStatus("indexing")).toBe(true);
    expect(isIndexingStatus("success")).toBe(false);
    expect(isIndexingStatus(undefined)).toBe(false);
  });

  it("knows which types are indexed when they are saved", () => {
    expect(["text", "file", "url"].map(isIndexedOnSave)).toEqual([true, true, true]);
    expect(["s3", "zendesk", "salesforce", undefined].map(isIndexedOnSave)).toEqual([false, false, false, false]);
  });
});

describe("list refresh while a knowledge base is indexing", () => {
  const NOW = Date.parse("2026-01-05T09:10:00Z");
  const startedAgo = (ms: number) => new Date(NOW - ms).toISOString();
  const indexing = (overrides = {}) => ({
    type: "file",
    last_sync_status: "indexing",
    last_synced: startedAgo(60_000),
    ...overrides,
  });

  it("refreshes while a row started indexing recently", () => {
    const rows = [{ type: "text", last_sync_status: "success", last_synced: startedAgo(60_000) }, indexing()];
    expect(indexingRefreshInterval(rows, NOW)).toBe(INDEXING_REFRESH_MS);
  });

  it.each([
    ["no rows are loaded", undefined],
    ["nothing is indexing", [{ type: "text", last_sync_status: "success" }, { type: "file", last_sync_status: "error" }]],
    ["the row has been indexing for too long", [indexing({ last_synced: startedAgo(INDEXING_FOLLOW_LIMIT_MS) })]],
    ["the start time is missing or unreadable", [indexing({ last_synced: null }), indexing({ last_synced: "soon" })]],
    ["the row is a synced type", [indexing({ type: "zendesk" }), indexing({ type: "s3" })]],
  ])("does not refresh when %s", (_case, rows) => {
    expect(indexingRefreshInterval(rows, NOW)).toBe(false);
  });

  it("still refreshes just before the limit", () => {
    expect(indexingRefreshInterval([indexing({ last_synced: startedAgo(INDEXING_FOLLOW_LIMIT_MS - 1) })], NOW)).toBe(
      INDEXING_REFRESH_MS,
    );
  });
});

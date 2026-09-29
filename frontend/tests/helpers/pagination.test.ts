import { describe, expect, it } from "vitest";
import {
  getPageList,
  getPageItems,
  getPaginationMeta,
  normalizeTranscriptList,
} from "@/helpers/pagination";

describe("getPageList", () => {
  it("returns a 1-based sequence of every page", () => {
    expect(getPageList(2, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(getPageList(1, 1)).toEqual([1]);
  });
});

describe("getPageItems", () => {
  it("lists all pages when they fit without ellipses", () => {
    expect(getPageItems(1, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(getPageItems(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("adds a trailing ellipsis near the start", () => {
    expect(getPageItems(1, 10)).toEqual([1, 2, "ellipsis", 10]);
  });

  it("adds a leading ellipsis near the end", () => {
    expect(getPageItems(10, 10)).toEqual([1, "ellipsis", 9, 10]);
  });

  it("adds ellipses on both sides in the middle", () => {
    expect(getPageItems(5, 10)).toEqual([
      1,
      "ellipsis",
      4,
      5,
      6,
      "ellipsis",
      10,
    ]);
  });

  it("clamps out-of-range current pages", () => {
    expect(getPageItems(0, 3)).toEqual([1, 2, 3]);
    expect(getPageItems(99, 3)).toEqual([1, 2, 3]);
  });
});

describe("getPaginationMeta", () => {
  it("computes indices for a mid-list page", () => {
    expect(getPaginationMeta(25, 10, 1)).toEqual({
      total: 25,
      pageSize: 10,
      currentPage: 1,
      totalPages: 3,
      safePage: 1,
      startIndex: 0,
      endIndex: 10,
    });
  });

  it("caps the end index at the total on the last page", () => {
    const meta = getPaginationMeta(25, 10, 3);
    expect(meta.startIndex).toBe(20);
    expect(meta.endIndex).toBe(25);
    expect(meta.safePage).toBe(3);
  });

  it("keeps the raw current page but clamps safePage", () => {
    const meta = getPaginationMeta(25, 10, 99);
    expect(meta.currentPage).toBe(99);
    expect(meta.safePage).toBe(3);
  });

  it("handles an empty list", () => {
    expect(getPaginationMeta(0, 10, 1)).toEqual({
      total: 0,
      pageSize: 10,
      currentPage: 1,
      totalPages: 1,
      safePage: 1,
      startIndex: 0,
      endIndex: 0,
    });
  });

  it("normalizes invalid totals, page sizes and current pages", () => {
    const meta = getPaginationMeta(-5, 0, 0);
    expect(meta.total).toBe(0);
    expect(meta.pageSize).toBe(1);
    expect(meta.currentPage).toBe(1);
  });
});

describe("normalizeTranscriptList", () => {
  const a = { id: "a" } as never;
  const b = { id: "b" } as never;

  it("returns an empty result for falsy payloads", () => {
    expect(normalizeTranscriptList(null)).toEqual({ items: [], total: 0 });
    expect(normalizeTranscriptList(undefined)).toEqual({ items: [], total: 0 });
  });

  it("treats a top-level array as the item list", () => {
    expect(normalizeTranscriptList([a, b])).toEqual({ items: [a, b], total: 2 });
  });

  it("reads items and total from an envelope object", () => {
    expect(normalizeTranscriptList({ items: [a], total: 5 })).toEqual({
      items: [a],
      total: 5,
    });
  });

  it("supports alternative item and total keys", () => {
    expect(normalizeTranscriptList({ data: [a, b] })).toEqual({
      items: [a, b],
      total: 2,
    });
    expect(normalizeTranscriptList({ recordings: [a], count: 7 })).toEqual({
      items: [a],
      total: 7,
    });
    expect(
      normalizeTranscriptList({ conversations: [a, b], total_items: 9 })
    ).toEqual({ items: [a, b], total: 9 });
  });

  it("wraps a bare object as a single item", () => {
    const single = { foo: 1 };
    expect(normalizeTranscriptList(single)).toEqual({
      items: [single],
      total: 1,
    });
  });

  it("returns empty for non-object primitives", () => {
    expect(normalizeTranscriptList("x")).toEqual({ items: [], total: 0 });
  });
});

import { BackendTranscript } from "@/interfaces/transcript.interface";
import { FetchTranscriptsResult } from "@/services/transcripts";

export function getPageList(currentPage: number, totalPages: number): number[] {
  return Array.from({ length: totalPages }, (_, i) => i + 1);
}

export type PageItem = number | "ellipsis";

export function getPageItems(
  currentPage: number,
  totalPages: number,
  siblingCount = 1
): PageItem[] {
  const safeTotal = Math.max(1, totalPages);
  const safeCurrent = Math.min(Math.max(1, currentPage || 1), safeTotal);

  const totalNumbers = siblingCount * 2 + 3; // current, first, last, siblings
  const totalBlocks = totalNumbers + 2; // add two ellipsis

  if (safeTotal <= totalBlocks) {
    return Array.from({ length: safeTotal }, (_, i) => i + 1);
  }

  const leftSibling = Math.max(safeCurrent - siblingCount, 1);
  const rightSibling = Math.min(safeCurrent + siblingCount, safeTotal);
  const showLeftEllipsis = leftSibling > 2;
  const showRightEllipsis = rightSibling < safeTotal - 1;

  const items: PageItem[] = [1];

  if (showLeftEllipsis) {
    items.push("ellipsis");
  } else {
    for (let page = 2; page < leftSibling; page++) {
      items.push(page);
    }
  }

  for (let page = leftSibling; page <= rightSibling; page++) {
    if (page !== 1 && page !== safeTotal) {
      items.push(page);
    }
  }

  if (showRightEllipsis) {
    items.push("ellipsis");
  } else {
    for (let page = rightSibling + 1; page < safeTotal; page++) {
      items.push(page);
    }
  }

  if (safeTotal > 1) {
    items.push(safeTotal);
  }

  return items;
}

export type PaginationMeta = {
  total: number;
  pageSize: number;
  currentPage: number;
  totalPages: number;
  safePage: number;
  startIndex: number;
  endIndex: number;
};

export function getPaginationMeta(
  total: number,
  pageSize: number,
  currentPage: number
): PaginationMeta {
  const normalizedTotal = Math.max(0, total);
  const normalizedPageSize = Math.max(1, pageSize);
  const totalPages = Math.max(
    1,
    Math.ceil(normalizedTotal / normalizedPageSize)
  );
  const safeCurrentPage = Math.max(1, currentPage || 1);
  const safePage = Math.min(safeCurrentPage, totalPages);

  const startIndex =
    normalizedTotal === 0 ? 0 : (safePage - 1) * normalizedPageSize;
  const endIndex =
    normalizedTotal === 0
      ? 0
      : Math.min(startIndex + normalizedPageSize, normalizedTotal);

  return {
    total: normalizedTotal,
    pageSize: normalizedPageSize,
    currentPage: safeCurrentPage,
    totalPages,
    safePage,
    startIndex,
    endIndex,
  };
}

export const normalizeTranscriptList = (payload: unknown): FetchTranscriptsResult => {
  if (!payload) return { items: [], total: 0 };

  if (Array.isArray(payload)) {
    const items = payload as BackendTranscript[];
    return { items, total: items.length };
  }

  if (typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    const candidates = [
      obj.items,
      obj.data,
      obj.recordings,
      (obj as { conversations?: unknown[] }).conversations,
    ];
    const items = candidates.find(Array.isArray) as BackendTranscript[] | undefined;

    const rawTotal = [
      obj.total,
      (obj as { count?: unknown }).count,
      (obj as { total_items?: unknown }).total_items,
      (obj as { total_records?: unknown }).total_records,
      (obj as { totalCount?: unknown }).totalCount,
    ].find((v) => typeof v === "number") as number | undefined;

    const normalizedItems = items ?? [payload as BackendTranscript];
    return {
      items: normalizedItems,
      total: typeof rawTotal === "number" && Number.isFinite(rawTotal)
        ? rawTotal
        : normalizedItems.length,
    };
  }

  return { items: [], total: 0 };
};

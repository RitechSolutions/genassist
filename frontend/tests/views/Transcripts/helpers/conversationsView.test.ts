import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CONVERSATIONS_VIEW_STORAGE_KEY,
  readConversationsViewMode,
} from "@/views/Transcripts/helpers/conversationsView";

const stubStorage = (getItem: () => string | null) => {
  vi.stubGlobal("localStorage", { getItem } as unknown as Storage);
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readConversationsViewMode", () => {
  it("prefers an explicit view param over the stored preference", () => {
    stubStorage(() => "split");
    expect(readConversationsViewMode(new URLSearchParams("view=list"))).toBe("list");

    stubStorage(() => "list");
    expect(readConversationsViewMode(new URLSearchParams("view=split"))).toBe("split");
  });

  it("falls back to the stored preference when the URL says nothing", () => {
    stubStorage((key?: string) => (key === CONVERSATIONS_VIEW_STORAGE_KEY ? "split" : null));
    expect(readConversationsViewMode(new URLSearchParams())).toBe("split");
  });

  it("defaults to the list view for unknown, missing and unreadable values", () => {
    stubStorage(() => null);
    expect(readConversationsViewMode(new URLSearchParams("view=grid"))).toBe("list");
    expect(readConversationsViewMode(new URLSearchParams())).toBe("list");

    stubStorage(() => {
      throw new Error("blocked");
    });
    expect(readConversationsViewMode(new URLSearchParams())).toBe("list");
  });
});

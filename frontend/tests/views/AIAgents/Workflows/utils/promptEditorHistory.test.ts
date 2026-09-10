import { describe, expect, it } from "vitest";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import {
  draftUnchangedSince,
  isCurrentDraft,
  resolveSelectedVersion,
} from "@/views/AIAgents/Workflows/utils/promptEditorHistory";

const version = (id: string, content = "text"): PromptVersion =>
  ({ id, content, version_number: 1 }) as PromptVersion;

const OWN = [version("v2", "newest"), version("v1")];
const LEGACY = [version("legacy-1")];

describe("resolveSelectedVersion", () => {
  it("finds the selection in the node's own history", () => {
    expect(resolveSelectedVersion(OWN, LEGACY, "v1")?.id).toBe("v1");
  });

  it("finds the selection in the legacy history", () => {
    expect(resolveSelectedVersion(OWN, LEGACY, "legacy-1")?.id).toBe("legacy-1");
  });

  it("falls back to the newest row when the selection is gone", () => {
    expect(resolveSelectedVersion(OWN, LEGACY, "deleted")?.id).toBe("v2");
    expect(resolveSelectedVersion(OWN, LEGACY, null)?.id).toBe("v2");
  });

  it("resolves to nothing when the node has no versions", () => {
    expect(resolveSelectedVersion([], [], null)).toBeNull();
    expect(resolveSelectedVersion([], LEGACY, "missing")).toBeNull();
  });
});

describe("isCurrentDraft", () => {
  it("compares the stored content with the draft verbatim", () => {
    expect(isCurrentDraft(version("v1", "abc"), "abc")).toBe(true);
    expect(isCurrentDraft(version("v1", "abc"), "abc ")).toBe(false);
  });
});

describe("draftUnchangedSince", () => {
  it("detects a draft that moved while a request was in flight", () => {
    expect(draftUnchangedSince("before", "before")).toBe(true);
    expect(draftUnchangedSince("before", "after")).toBe(false);
  });
});

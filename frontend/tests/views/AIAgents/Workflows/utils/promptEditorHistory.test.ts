import { describe, expect, it } from "vitest";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import {
  diffSides,
  draftUnchangedSince,
  findPromptVersion,
  isCurrentDraft,
  type HistoryEntry,
} from "@/views/AIAgents/Workflows/utils/promptEditorHistory";

const version = (
  id: string,
  content = "text",
  versionNumber = 1,
): PromptVersion => ({ id, content, version_number: versionNumber }) as PromptVersion;

const entry = (version: PromptVersion, isLegacy = false): HistoryEntry => ({
  version,
  isLegacy,
});

const OWN = [version("v2", "newest"), version("v1")];
const LEGACY = [version("legacy-1")];

describe("findPromptVersion", () => {
  it("finds the selection in the node's own history", () => {
    expect(findPromptVersion(OWN, LEGACY, "v1")).toEqual({
      version: OWN[1],
      isLegacy: false,
    });
  });

  it("finds the selection in the legacy history", () => {
    expect(findPromptVersion(OWN, LEGACY, "legacy-1")).toEqual({
      version: LEGACY[0],
      isLegacy: true,
    });
  });

  it("resolves to nothing when the selection is gone or absent", () => {
    expect(findPromptVersion(OWN, LEGACY, "deleted")).toBeNull();
    expect(findPromptVersion(OWN, LEGACY, null)).toBeNull();
    expect(findPromptVersion([], [], "v1")).toBeNull();
  });
});

describe("diffSides", () => {
  const DRAFT = "draft text";
  const ownV2 = entry(version("o2", "own two", 2));
  const ownV3 = entry(version("o3", "own three", 3));
  const ownV5 = entry(version("o5", "own five", 5));
  const legacyV1 = entry(version("l1", "legacy one", 1), true);
  const legacyV2 = entry(version("l2", "legacy two", 2), true);

  const bothDirections = (a: HistoryEntry, b: HistoryEntry) => [
    diffSides(a, b, DRAFT),
    diffSides(b, a, DRAFT),
  ];

  it("treats legacy rows as older than the node's own history", () => {
    for (const sides of bothDirections(ownV3, legacyV1)) {
      expect(sides).toEqual({
        before: "legacy one",
        after: "own three",
        label: "v1 · Legacy → v3",
      });
    }
  });

  it("orders rows of one history by version number", () => {
    for (const sides of bothDirections(ownV2, ownV5)) {
      expect(sides.label).toBe("v2 → v5");
    }
    for (const sides of bothDirections(legacyV1, legacyV2)) {
      expect(sides.label).toBe("v1 · Legacy → v2 · Legacy");
    }
  });

  it("puts the draft on the newer side", () => {
    expect(diffSides(ownV3, "draft", DRAFT)).toEqual({
      before: "own three",
      after: DRAFT,
      label: "v3 → Current draft",
    });
    expect(diffSides(legacyV1, "draft", DRAFT).label).toBe(
      "v1 · Legacy → Current draft",
    );
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

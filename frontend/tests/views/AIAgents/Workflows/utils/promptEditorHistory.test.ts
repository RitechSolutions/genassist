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

  it("treats legacy rows as older than the node's own history", () => {
    const previewOwn = diffSides(ownV3, legacyV1, DRAFT);
    expect(previewOwn.before).toEqual({
      content: "legacy one",
      label: "v1 · Legacy",
      isPreview: false,
    });
    expect(previewOwn.after).toEqual({
      content: "own three",
      label: "v3",
      isPreview: true,
    });

    const previewLegacy = diffSides(legacyV1, ownV3, DRAFT);
    expect(previewLegacy.before).toEqual({
      content: "legacy one",
      label: "v1 · Legacy",
      isPreview: true,
    });
    expect(previewLegacy.after).toEqual({
      content: "own three",
      label: "v3",
      isPreview: false,
    });
  });

  it("orders rows of one history by version number", () => {
    const previewNewer = diffSides(ownV5, ownV2, DRAFT);
    expect(previewNewer.before).toEqual({
      content: "own two",
      label: "v2",
      isPreview: false,
    });
    expect(previewNewer.after).toEqual({
      content: "own five",
      label: "v5",
      isPreview: true,
    });

    const previewOlder = diffSides(ownV2, ownV5, DRAFT);
    expect(previewOlder.before.label).toBe("v2");
    expect(previewOlder.before.isPreview).toBe(true);
    expect(previewOlder.after.label).toBe("v5");
    expect(previewOlder.after.isPreview).toBe(false);
  });

  it("orders two legacy rows by version number", () => {
    const sides = diffSides(legacyV2, legacyV1, DRAFT);
    expect(sides.before.label).toBe("v1 · Legacy");
    expect(sides.after.label).toBe("v2 · Legacy");
    expect(sides.after.isPreview).toBe(true);
  });

  it("puts the draft on the newer side", () => {
    expect(diffSides(ownV3, "draft", DRAFT)).toEqual({
      before: { content: "own three", label: "v3", isPreview: true },
      after: { content: DRAFT, label: "Current draft", isPreview: false },
    });
    expect(diffSides(legacyV1, "draft", DRAFT).before.label).toBe(
      "v1 · Legacy",
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

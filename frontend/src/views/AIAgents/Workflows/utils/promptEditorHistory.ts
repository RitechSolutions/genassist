import type { PromptVersion } from "@/interfaces/promptEditor.interface";

/** History row plus its list. Legacy rows share numbering */
export interface HistoryEntry {
  version: PromptVersion;
  isLegacy: boolean;
}

/** Lookup across both histories. Null = nothing selected (no newest-row fallback) */
export const findPromptVersion = (
  versions: readonly PromptVersion[],
  legacyVersions: readonly PromptVersion[],
  id: string | null,
): HistoryEntry | null => {
  if (!id) return null;
  const own = versions.find((v) => v.id === id);
  if (own) return { version: own, isLegacy: false };
  const legacy = legacyVersions.find((v) => v.id === id);
  return legacy ? { version: legacy, isLegacy: true } : null;
};

/** The previewed row is one endpoint; the other is another row or the draft */
export type DiffTarget = HistoryEntry | "draft";

/** One endpoint of the diff. `isPreview` marks the sidebar-selected row */
export interface DiffEndpoint {
  content: string;
  label: string;
  isPreview: boolean;
}

/** Chronologically ordered endpoints: `before` is always the older one */
export interface DiffSides {
  before: DiffEndpoint;
  after: DiffEndpoint;
}

// Product ordering (not DB constraint): legacy → node history → draft
const rankOf = (target: DiffTarget): number =>
  target === "draft" ? 2 : target.isLegacy ? 0 : 1;

const labelOf = (target: DiffTarget): string =>
  target === "draft"
    ? "Current draft"
    : `v${target.version.version_number}${target.isLegacy ? " · Legacy" : ""}`;

const contentOf = (target: DiffTarget, draft: string): string =>
  target === "draft" ? draft : target.version.content;

/**
 * Orders endpoints oldest-first for chronological diff.
 * Within a history, lower version = older (backend guarantees monotonic numbers)
 */
export const diffSides = (
  previewed: HistoryEntry,
  target: DiffTarget,
  draft: string,
): DiffSides => {
  const previewedIsOlder =
    target === "draft" ||
    (rankOf(previewed) !== rankOf(target)
      ? rankOf(previewed) < rankOf(target)
      : previewed.version.version_number <= target.version.version_number);

  const older: DiffTarget = previewedIsOlder ? previewed : target;
  const newer: DiffTarget = previewedIsOlder ? target : previewed;

  return {
    before: {
      content: contentOf(older, draft),
      label: labelOf(older),
      isPreview: previewedIsOlder,
    },
    after: {
      content: contentOf(newer, draft),
      label: labelOf(newer),
      isPreview: !previewedIsOlder,
    },
  };
};

export const isCurrentDraft = (version: PromptVersion, draft: string): boolean =>
  version.content === draft;

export interface DraftStatus {
  saved: boolean;
  label: string;
}

const newestOf = (versions: readonly PromptVersion[]): PromptVersion | null =>
  versions.reduce<PromptVersion | null>(
    (newest, v) =>
      newest && newest.version_number >= v.version_number ? newest : v,
    null,
  );

export const draftStatusOf = (
  draft: string,
  versions: readonly PromptVersion[],
): DraftStatus => {
  const match = newestOf(versions.filter((v) => isCurrentDraft(v, draft)));
  if (match) return { saved: true, label: `Matches v${match.version_number}` };
  const newest = newestOf(versions);
  return newest
    ? { saved: false, label: `Changed since v${newest.version_number}` }
    : { saved: false, label: "No saved version" };
};

import type { PromptVersion } from "@/interfaces/promptEditor.interface";

/**
 * Selected row, falls back to newest version. Derived, not stored
 * so deleted selections auto-resolve to the newest remaining row
 */
export const resolveSelectedVersion = (
  versions: readonly PromptVersion[],
  legacyVersions: readonly PromptVersion[],
  selectedId: string | null,
): PromptVersion | null => {
  if (selectedId) {
    const found =
      versions.find((v) => v.id === selectedId) ??
      legacyVersions.find((v) => v.id === selectedId);
    if (found) return found;
  }
  return versions[0] ?? null;
};

export const isCurrentDraft = (version: PromptVersion, draft: string): boolean =>
  version.content === draft;

/** Checks if the draft changed since async action was submitted */
export const draftUnchangedSince = (
  draftAtSubmit: string,
  currentDraft: string,
): boolean => draftAtSubmit === currentDraft;

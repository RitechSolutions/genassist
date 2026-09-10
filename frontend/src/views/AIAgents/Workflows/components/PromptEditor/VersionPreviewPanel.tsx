import React, { useId, useState } from "react";
import { AlertCircle, ArrowRight, Copy, Undo2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import FieldChangeRow from "../diff/FieldChangeRow";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import {
  diffSides,
  findPromptVersion,
  type DiffEndpoint,
  type HistoryEntry,
} from "../../utils/promptEditorHistory";

const PROMPT_MIN_SIMILARITY = 0.15;

// Sentinels for non-version choices (Radix Select has no empty-string value)
const DRAFT_TARGET = "__draft__";
const NO_TARGET = "__none__";

// The previewed row keeps its "Preview" role on whichever side chronology puts it
const roleOf = (endpoint: DiffEndpoint, position: "older" | "newer"): string =>
  endpoint.isPreview
    ? `Preview · ${position}`
    : position === "older"
      ? "Base · older"
      : "Target · newer";

const EndpointChip: React.FC<{
  endpoint: DiffEndpoint;
  position: "older" | "newer";
}> = ({ endpoint, position }) => (
  <span className="inline-flex min-w-0 items-center gap-1.5 rounded border border-border bg-muted/50 px-1.5 py-0.5">
    <span className="truncate font-mono text-[11px] font-medium">
      {endpoint.label}
    </span>
    <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
      {roleOf(endpoint, position)}
    </span>
  </span>
);

interface VersionPreviewPanelProps {
  version: PromptVersion;
  isLegacy: boolean;
  versions: readonly PromptVersion[];
  legacyVersions: readonly PromptVersion[];
  draft: string;
  isCurrentDraft: boolean;
  canEdit: boolean;
  canUndo: boolean;
  nodeMissing: boolean;
  historyReady: boolean;
  onApply: () => void;
  onUndo: () => void;
  onCopy: () => void;
  isCopying: boolean;
  copyError: string | null;
}

export const VersionPreviewPanel: React.FC<VersionPreviewPanelProps> = ({
  version,
  isLegacy,
  versions,
  legacyVersions,
  draft,
  isCurrentDraft,
  canEdit,
  canUndo,
  nodeMissing,
  historyReady,
  onApply,
  onUndo,
  onCopy,
  isCopying,
  copyError,
}) => {
  const compareId = useId();
  const [compareTargetId, setCompareTargetId] = useState(NO_TARGET);

  const canCopyToHistory = isLegacy && canEdit && !nodeMissing && historyReady;

  const previewed: HistoryEntry = { version, isLegacy };
  // A target deleted while selected stays stored but resolves to nothing, so no diff renders
  const targetEntry =
    compareTargetId === DRAFT_TARGET || compareTargetId === NO_TARGET
      ? null
      : findPromptVersion(versions, legacyVersions, compareTargetId);
  const comparison =
    compareTargetId === DRAFT_TARGET
      ? diffSides(previewed, "draft", draft)
      : targetEntry
        ? diffSides(previewed, targetEntry, draft)
        : null;
  const selectValue =
    compareTargetId === DRAFT_TARGET
      ? DRAFT_TARGET
      : targetEntry
        ? targetEntry.version.id
        : NO_TARGET;

  return (
    <div className="rounded-md border bg-card mb-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {comparison ? (
            <>
              <EndpointChip endpoint={comparison.before} position="older" />
              <ArrowRight
                className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
              <EndpointChip endpoint={comparison.after} position="newer" />
            </>
          ) : (
            <>
              <span className="text-sm font-medium">
                v{version.version_number}
              </span>
              {version.label && (
                <span className="text-xs text-muted-foreground truncate">
                  {version.label}
                </span>
              )}
              {isCurrentDraft && (
                <Badge variant="success" className="text-[9px] px-1.5">
                  Current draft
                </Badge>
              )}
              {isLegacy && (
                <Badge variant="outline" className="text-[9px] px-1.5">
                  Legacy
                </Badge>
              )}
            </>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span
            id={`${compareId}-label`}
            className="text-xs text-muted-foreground"
          >
            Compare with
          </span>
          <Select value={selectValue} onValueChange={setCompareTargetId}>
            <SelectTrigger
              id={`${compareId}-trigger`}
              className="h-9 w-auto max-w-56 text-xs"
              aria-labelledby={`${compareId}-label ${compareId}-trigger`}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DRAFT_TARGET}>Current draft</SelectItem>
              {versions
                .filter((v) => v.id !== version.id)
                .map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version_number}
                  </SelectItem>
                ))}
              {legacyVersions
                .filter((v) => v.id !== version.id)
                .map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version_number} · Legacy
                  </SelectItem>
                ))}
              <SelectItem value={NO_TARGET}>No comparison</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Fixed height so toggling the comparison on and off doesn't shift the panel */}
      <div className="h-48 overflow-y-auto">
        {comparison ? (
          comparison.before.content === comparison.after.content ? (
            <div className="flex min-h-full items-center justify-center px-3 py-2 text-xs italic text-muted-foreground">
              No differences
            </div>
          ) : (
            <FieldChangeRow
              variant="embedded"
              change={{
                key: `${comparison.before.label} → ${comparison.after.label}`,
                before: comparison.before.content,
                after: comparison.after.content,
              }}
              minSimilarity={PROMPT_MIN_SIMILARITY}
            />
          )
        ) : (
          <pre className="min-h-full whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs text-muted-foreground">
            {version.content}
          </pre>
        )}
      </div>

      {copyError && (
        <div className="px-3 pb-2">
          <div className="flex items-start gap-2 text-destructive text-xs bg-destructive/10 border border-destructive/20 rounded-md px-2 py-1">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" />
            <span>{copyError}</span>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t px-3 py-2">
        <Button type="button" size="sm" onClick={onApply} disabled={isCurrentDraft}>
          Apply to draft
        </Button>
        {canUndo && (
          <Button type="button" size="sm" variant="ghost" onClick={onUndo}>
            <Undo2 className="h-3.5 w-3.5 mr-2" />
            Undo
          </Button>
        )}
        {canCopyToHistory && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onCopy}
            disabled={isCopying}
          >
            <Copy className="h-3.5 w-3.5 mr-2" />
            {isCopying ? "Copying…" : "Copy into this history"}
          </Button>
        )}
      </div>
    </div>
  );
};

import React, { useState } from "react";
import { AlertCircle, ChevronDown, ChevronRight, History, Link2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import type {
  LegacyPromptHistory,
  PromptVersion,
} from "@/interfaces/promptEditor.interface";
import { formatFeedbackDate } from "@/helpers/utils";
import type { HistoryState } from "../../utils/promptEditorGates";

interface VersionsSidebarProps {
  versions: PromptVersion[];
  legacy: LegacyPromptHistory | null;
  selectedVersionId: string | null;
  onSelect: (versionId: string) => void;
  canEditPrompt: boolean;
  currentGoldSuiteId: string | null;
  onLinkLegacyDataset: () => void;
  linkPending: boolean;
  linkError: string | null;
  status: HistoryState["status"];
}

interface VersionRowProps {
  version: PromptVersion;
  isSelected: boolean;
  onSelect: (versionId: string) => void;
}

const VersionRow: React.FC<VersionRowProps> = ({ version, isSelected, onSelect }) => (
  <div
    className={cn(
      "w-full rounded-md border px-3 py-2 transition-colors",
      "hover:bg-muted/40 focus:outline-none focus:ring-2 focus:ring-ring",
      isSelected
        ? "bg-blue-50 border-blue-200 dark:bg-blue-500/15 dark:border-blue-500/30"
        : "bg-card",
    )}
    aria-current={isSelected ? "true" : "false"}
    role="button"
    tabIndex={0}
    onClick={() => onSelect(version.id)}
    onKeyDown={(e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onSelect(version.id);
      }
    }}
  >
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium">v{version.version_number}</span>
        <div className="text-xs text-muted-foreground truncate">
          {version.label || formatFeedbackDate(version.created_at)}
        </div>
      </div>
      <div className="text-xs text-muted-foreground shrink-0">
        {formatFeedbackDate(version.created_at)}
      </div>
    </div>
  </div>
);

export const VersionsSidebar: React.FC<VersionsSidebarProps> = ({
  versions,
  legacy,
  selectedVersionId,
  onSelect,
  canEditPrompt,
  currentGoldSuiteId,
  onLinkLegacyDataset,
  linkPending,
  linkError,
  status,
}) => {
  const [isLegacyOpen, setIsLegacyOpen] = useState(false);

  if (status !== "ready") {
    // Unreadable history ≠ empty
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        {status === "pending" ? "Loading history…" : "History unavailable"}
      </div>
    );
  }

  const canLinkLegacyDataset =
    !!legacy?.gold_suite_id && !currentGoldSuiteId && canEditPrompt;

  return (
    <div className="space-y-3">
      {versions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2 text-center">
          <History className="h-7 w-7" />
          <div className="text-sm font-medium">No versions yet</div>
          <div className="text-xs">
            Save a version from the Editor to start tracking changes.
          </div>
        </div>
      ) : (
        <div className="space-y-1 p-1">
          {versions.map((version) => (
            <VersionRow
              key={version.id}
              version={version}
              isSelected={selectedVersionId === version.id}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}

      {legacy && (
        <div className="border-t pt-2">
          <button
            type="button"
            onClick={() => setIsLegacyOpen((open) => !open)}
            className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            aria-expanded={isLegacyOpen}
          >
            {isLegacyOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            Older shared history
            <Badge variant="outline" className="ml-auto text-[9px] px-1.5">
              {legacy.versions.length}
            </Badge>
          </button>

          {isLegacyOpen && (
            <div className="mt-2 space-y-1 p-1">
              {legacy.versions.map((version) => (
                <VersionRow
                  key={version.id}
                  version={version}
                  isSelected={selectedVersionId === version.id}
                  onSelect={onSelect}
                />
              ))}
              {canLinkLegacyDataset && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full mt-2"
                  onClick={onLinkLegacyDataset}
                  disabled={linkPending}
                >
                  <Link2 className="h-3.5 w-3.5 mr-2" />
                  {linkPending ? "Linking…" : "Link this dataset"}
                </Button>
              )}
              {linkError && (
                <div className="flex items-start gap-2 text-destructive text-xs bg-destructive/10 border border-destructive/20 rounded-md px-2 py-1 mt-2">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" />
                  <span>{linkError}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

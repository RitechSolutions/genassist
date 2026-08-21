import React, { useMemo, useState } from "react";
import { Check, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { groupWorkflowVersions } from "../helpers/workflowVersions";

interface WorkflowVersionPickerProps {
  workflows: WorkflowMinimal[];
  selectedWorkflowId: string;
  onSelect: (workflowId: string) => void;
  /** Rendered above the workflows, e.g. "Use dataset's default workflow". */
  leadingOption?: React.ReactNode;
  emptyMessage?: string;
}

/** Workflows as collapsible groups, each listing its versions with the live one
 * marked. Shared by the evaluation wizard and the import dialog so both agree
 * on what "current" means. */
export const WorkflowVersionPicker: React.FC<WorkflowVersionPickerProps> = ({
  workflows,
  selectedWorkflowId,
  onSelect,
  leadingOption,
  emptyMessage = "No workflows available.",
}) => {
  const groups = useMemo(() => groupWorkflowVersions(workflows), [workflows]);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  return (
    <div className="rounded-lg border p-2 space-y-0.5">
      {leadingOption}

      {groups.length === 0 && !leadingOption && (
        <p className="px-2.5 py-2 text-sm text-muted-foreground">{emptyMessage}</p>
      )}

      {groups.map((group) => {
        const isExpanded = expandedKey === group.key;
        const selectedInGroup = group.versions.find(
          (workflow) => workflow.id === selectedWorkflowId,
        );
        // Opening a group selects what a plain run would execute: the live
        // version, or the newest when the workflow has no active pointer.
        const defaultForGroup = group.activeVersionId ?? group.versions[0].id;
        return (
          <div key={group.key}>
            <button
              type="button"
              onClick={() => {
                if (isExpanded) {
                  setExpandedKey(null);
                  return;
                }
                setExpandedKey(group.key);
                // Only default the selection when this group has none —
                // re-opening a group must not discard a chosen version.
                if (!selectedInGroup) onSelect(defaultForGroup);
              }}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors",
                selectedInGroup ? "bg-primary/10" : "hover:bg-muted",
              )}
            >
              <ChevronRight
                className={cn(
                  "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                  isExpanded && "rotate-90",
                )}
              />
              <span
                className={cn(
                  "truncate text-sm font-semibold",
                  selectedInGroup ? "text-primary" : "text-foreground",
                )}
              >
                {group.name}
              </span>
              {!isExpanded && selectedInGroup && (
                <span className="ml-auto shrink-0 text-xs font-medium text-primary">
                  v{selectedInGroup.version}
                </span>
              )}
            </button>

            {isExpanded && (
              <div className="relative py-0.5 pl-[30px]">
                <div className="absolute bottom-0 left-[18px] top-0 w-px bg-border" />
                {group.versions.map((workflow) => {
                  const selected = selectedWorkflowId === workflow.id;
                  return (
                    <button
                      key={workflow.id}
                      type="button"
                      onClick={() => onSelect(workflow.id)}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-2.5 py-[6px] text-sm transition-colors",
                        selected
                          ? "bg-primary/10 font-semibold text-primary"
                          : "font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <span className="truncate">v{workflow.version}</span>
                      {workflow.id === group.activeVersionId && (
                        <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                          Current
                        </span>
                      )}
                      {/* A version's own name tells two apart after a rename. */}
                      {workflow.name !== group.workflowName && (
                        <span className="truncate text-xs text-muted-foreground">
                          {workflow.name}
                        </span>
                      )}
                      {selected && <Check className="ml-auto h-4 w-4 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

import React from "react";
import { AlertTriangle, Download, Loader2, MoreVertical, Pencil, Play, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/dropdown-menu";
import { cn } from "@/helpers/utils";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import type { ConversationCounts } from "@/interfaces/testSuite.interface";
import { EntityTitle } from "./EntityTitle";
import { VerdictTally } from "./resultsParts";
import { accuracyColorClass } from "../helpers/evaluationMetrics";
import { leftOutNote, parseChecks } from "../helpers/checks";

/** Name, result and actions as three columns on wide screens, so the results line up down the list. */
const RESULT_COLUMNS = "xl:grid xl:grid-cols-[minmax(0,1fr)_minmax(0,20rem)_minmax(0,1fr)] xl:items-center xl:gap-4";

interface EvaluationListRowProps {
  evaluation: TestEvaluationConfig;
  avgAccuracy: number | null;
  /** The last run's verdict by conversation, read before the avg score when it has one. */
  conversations?: ConversationCounts | null;
  isRunning: boolean;
  lastRunStatus?: string;
  /** e.g. "12 of 40 turns done" while the last run is going. */
  progressText?: string | null;
  /** Lines the name up with its workflow's title above it. */
  indent?: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onExport: () => void;
  onDelete: () => void;
  onRun: (e: React.MouseEvent) => void;
}

export const EvaluationListRow: React.FC<EvaluationListRowProps> = ({
  evaluation,
  avgAccuracy,
  conversations,
  isRunning,
  lastRunStatus,
  progressText,
  indent = false,
  onOpen,
  onEdit,
  onExport,
  onDelete,
  onRun,
}) => {
  // The last run's result, as a centred column or on its own line under the name.
  const result = (align: "center" | "start") => {
    const line = cn("flex flex-wrap items-center gap-x-2 gap-y-1 text-xs", align === "center" && "justify-center");
    const label = <span className="text-muted-foreground">Last run</span>;
    const running = (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 dark:text-blue-400">
        <Loader2 className="h-3 w-3 animate-spin" />
        {lastRunStatus === "queued" ? "Queued" : progressText ? `Running… ${progressText}` : "Running…"}
      </span>
    );
    if (align === "start") {
      // Under the name, a status stands on its own.
      if (isRunning) return running;
      if (lastRunStatus === "failed")
        return <div className="text-xs font-medium text-red-600 dark:text-red-400">Last run failed</div>;
    } else {
      // A status sits where the counts would, in a box as wide as their three slots, so it lines up with them.
      const status = (content: React.ReactNode) => (
        <div className={line}>
          {label}
          <span className="inline-flex w-[14.25em] items-center">{content}</span>
        </div>
      );
      // Said from where "Last run" starts; the line keeps its width, so it stays where the others are.
      const sentence = (text: string, className: string) => (
        <div className={line}>
          <span className="relative">
            <span className="invisible">Last run</span>
            <span className={cn("absolute left-0 top-0 whitespace-nowrap", className)}>{text}</span>
          </span>
          <span className="w-[14.25em]" />
        </div>
      );
      if (isRunning) return status(running);
      if (lastRunStatus === "failed") return sentence("Last run failed", "font-medium text-red-600 dark:text-red-400");
      if (!conversations && avgAccuracy === null) return sentence("Not run yet", "text-muted-foreground");
    }
    if (conversations) {
      return (
        <div className={line}>
          {label}
          <VerdictTally
            counts={conversations}
            className="font-medium"
            iconClassName="h-3.5 w-3.5"
            // Rows in other sections cannot be seen from here, so every slot is kept.
            slots={align === "center" ? ["passed", "failed", "not_evaluated"] : undefined}
          />
        </div>
      );
    }
    // Runs from before conversations were counted only have the older score.
    if (avgAccuracy !== null) {
      return (
        <div className={line} title="Avg score: the average of each method's pass rate.">
          {label}
          <span className={cn("font-medium", accuracyColorClass(avgAccuracy))}>
            {Math.round(avgAccuracy * 100)}% avg score
          </span>
        </div>
      );
    }
    return <div className="text-xs text-muted-foreground">Not run yet</div>;
  };

  const actions = (
    // Its buttons, and the menu they open, act on their own instead of opening the row.
    <div className="flex shrink-0 items-center justify-end gap-1" onClick={(event) => event.stopPropagation()}>
      <Button size="sm" disabled={isRunning} onClick={onRun}>
        <Play className="h-3.5 w-3.5 mr-1" />
        {isRunning ? "Running…" : "Run"}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`More actions for ${evaluation.name}`}>
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            disabled={isRunning}
            onSelect={onEdit}
            title={isRunning ? "Can't edit while this evaluation is running" : undefined}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={isRunning}
            onSelect={onDelete}
            className="text-red-600 focus:text-red-600 dark:text-red-400 dark:focus:text-red-400"
            title={isRunning ? "Can't delete while this evaluation is running" : undefined}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );

  // Older settings no check could take, said until the evaluation is saved in the editor.
  const leftOut = leftOutNote(parseChecks(evaluation.technique_configs?.checks).olderMethods).length > 0;

  return (
    // Anywhere on the row opens it; the name is the way in for keyboards and screen readers, its click reaching the row.
    <div
      onClick={onOpen}
      className={cn(
        "flex cursor-pointer items-center gap-3 px-4 py-4 transition-colors hover:bg-muted",
        RESULT_COLUMNS,
      )}
    >
      <button type="button" className={cn("min-w-0 flex-1 text-left", indent && "pl-7")}>
        <EntityTitle>{evaluation.name}</EntityTitle>
        <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{evaluation.description || "No description"}</p>
        {leftOut && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Some older settings could not become checks. Open it to see which.
          </p>
        )}
        {/* Read out with the name; on wide screens it shows in the middle column instead. */}
        <div className="mt-2 xl:sr-only">{result("start")}</div>
      </button>
      <div aria-hidden="true" className="hidden min-w-0 justify-center self-stretch xl:flex xl:items-center">
        {result("center")}
      </div>
      {actions}
    </div>
  );
};

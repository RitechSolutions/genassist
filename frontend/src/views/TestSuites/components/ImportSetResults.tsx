import React from "react";
import { AlertTriangle, CheckCircle2, MinusCircle } from "lucide-react";

import {
  EvaluationSetImportResult,
  EvaluationSetItemResult,
} from "@/interfaces/evalBundle.interface";

interface ImportSetResultsProps {
  result: EvaluationSetImportResult;
}

const statusIcon = (status: string) => {
  if (status === "imported") {
    return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />;
  }
  if (status === "skipped") {
    return <MinusCircle className="h-4 w-4 shrink-0 text-muted-foreground" />;
  }
  return <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />;
};

const itemNotes = (item: EvaluationSetItemResult): string[] => {
  const notes: string[] = [];
  if (item.detail) notes.push(item.detail);
  if (item.reused_dataset) notes.push("Reused the existing dataset.");
  if (item.dropped_rules.length > 0) {
    notes.push(
      `${item.dropped_rules.length} rule${
        item.dropped_rules.length !== 1 ? "s" : ""
      } dropped.`,
    );
  }
  return [...notes, ...item.warnings];
};

/** Per-evaluation outcome of a bundle set import. */
export const ImportSetResults: React.FC<ImportSetResultsProps> = ({ result }) => {
  const summary = [
    `${result.imported} imported`,
    result.skipped > 0 ? `${result.skipped} skipped` : null,
    result.failed > 0 ? `${result.failed} failed` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium">{summary}</p>
      <div className="rounded-lg border">
        <div className="max-h-72 divide-y divide-border overflow-y-auto">
          {result.results.map((item, index) => (
            <div key={`${item.name}-${index}`} className="flex items-start gap-3 px-4 py-2.5">
              <span className="mt-0.5">{statusIcon(item.status)}</span>
              <div className="min-w-0 flex-1 text-sm">
                <div className="truncate font-medium">{item.name}</div>
                {itemNotes(item).map((note) => (
                  <div key={note} className="text-xs text-muted-foreground">
                    {note}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

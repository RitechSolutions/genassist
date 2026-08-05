import React from "react";
import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/badge";
import { Checkbox } from "@/components/checkbox";
import { EvaluationSetImportPreview } from "@/interfaces/evalBundle.interface";
import { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";
import { ImportMappingTable } from "./ImportMappingTable";

interface ImportSetReviewProps {
  preview: EvaluationSetImportPreview;
  sourceWorkflowName?: string | null;
  catalog: EvaluationToolCatalog | null;
  catalogUnavailable: boolean;
  picks: Record<string, string>;
  onPick: (pickKey: string, targetId: string) => void;
  selected: Set<number>;
  onToggleItem: (index: number) => void;
  unresolvedCount: number;
  /** Per evaluation, whether dropping the unmatched references would leave it
   * nothing to grade. Positionally aligned with `preview.evaluations`. */
  noMatchingChecks: boolean[];
  dropUnresolved: boolean;
  onDropUnresolvedChange: (checked: boolean) => void;
}

/** Review step for a bundle set: pick which evaluations to import and map the
 * shared references once for all of them. */
export const ImportSetReview: React.FC<ImportSetReviewProps> = ({
  preview,
  sourceWorkflowName,
  catalog,
  catalogUnavailable,
  picks,
  onPick,
  selected,
  onToggleItem,
  unresolvedCount,
  noMatchingChecks,
  dropUnresolved,
  onDropUnresolvedChange,
}) => {
  const looksLikeWrongWorkflow =
    preview.node_refs.length > 0 &&
    preview.node_refs.every((nodeRef) => nodeRef.status !== "resolved");
  const reusedDatasets = preview.datasets.filter((dataset) =>
    Boolean(dataset.existing_dataset),
  );

  return (
    <div className="space-y-4">
      <div className="rounded-lg border">
        <div className="border-b bg-muted/40 px-4 py-2 text-xs font-medium text-muted-foreground">
          {selected.size} of {preview.evaluations.length} evaluation
          {preview.evaluations.length !== 1 ? "s" : ""} selected
        </div>
        <div className="max-h-56 divide-y divide-border overflow-y-auto">
          {preview.evaluations.map((item, index) => (
            <label
              key={`${item.name}-${index}`}
              className="flex cursor-pointer items-start gap-3 px-4 py-2.5 text-sm hover:bg-muted/30"
            >
              <Checkbox
                checked={selected.has(index)}
                onCheckedChange={() => onToggleItem(index)}
                className="mt-0.5"
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{item.name}</span>
                  {item.already_exists && (
                    <Badge variant="secondary" className="shrink-0">
                      Already here
                    </Badge>
                  )}
                  {noMatchingChecks[index] && (
                    <Badge
                      variant="outline"
                      className="shrink-0 text-amber-700 dark:text-amber-300"
                    >
                      No matching checks
                    </Badge>
                  )}
                </span>
                <span className="block text-xs text-muted-foreground">
                  Dataset "{item.dataset_name}" · {item.case_count} case
                  {item.case_count !== 1 ? "s" : ""}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      {reusedDatasets.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {reusedDatasets.map((dataset) => dataset.name).join(", ")}{" "}
          {reusedDatasets.length !== 1 ? "already exist" : "already exists"} here
          and will be reused instead of duplicated.
        </p>
      )}

      {looksLikeWrongWorkflow && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-3">
          <div className="flex items-start gap-2 text-sm text-amber-900 dark:text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p>No references match this workflow.</p>
              <p className="mt-0.5 text-xs text-amber-800 dark:text-amber-300">
                {sourceWorkflowName ? `Exported from "${sourceWorkflowName}". ` : ""}
                Go back to change the target, or import without the unmatched
                checks.
              </p>
            </div>
          </div>
        </div>
      )}

      {preview.node_refs.length > 0 && (
        <ImportMappingTable
          nodeRefs={preview.node_refs}
          catalog={catalog}
          catalogUnavailable={catalogUnavailable}
          picks={picks}
          onPick={onPick}
        />
      )}

      {preview.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-3 space-y-1">
          {preview.warnings.map((warning) => (
            <div
              key={warning}
              className="flex items-start gap-2 text-xs text-amber-800 dark:text-amber-300"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              {warning}
            </div>
          ))}
        </div>
      )}

      {unresolvedCount > 0 && (
        <label className="flex items-start gap-2 text-sm">
          <Checkbox
            checked={dropUnresolved}
            onCheckedChange={(checked) => onDropUnresolvedChange(checked === true)}
            className="mt-0.5"
          />
          <span>
            Drop the checks that use the {unresolvedCount} reference
            {unresolvedCount !== 1 ? "s" : ""} I haven't matched. An evaluation
            left with no checks at all is not imported and is reported instead.
          </span>
        </label>
      )}
    </div>
  );
};

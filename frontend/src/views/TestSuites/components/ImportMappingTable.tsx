import React, { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { BundleNodeResolution } from "@/interfaces/evalBundle.interface";
import { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";
import {
  buildNodeTypeIndex,
  catalogOptionsForKind,
  narrowToOriginalType,
  nodeRefKey,
} from "../helpers/evalBundle";

const KIND_LABELS: Record<string, string> = {
  tool: "Tool",
  agent: "Agent",
  router: "Router",
  action: "Node",
};

// Plural nouns for the "this workflow has none of these" message.
const KIND_PLURALS: Record<string, string> = {
  tool: "tools",
  agent: "agents",
  router: "routers",
  action: "nodes",
};

interface ImportMappingTableProps {
  nodeRefs: BundleNodeResolution[];
  catalog: EvaluationToolCatalog | null;
  /** The target workflow's nodes could not be loaded, so manual picks are impossible. */
  catalogUnavailable?: boolean;
  /** Manual picks keyed by nodeRefKey (kind + ref, since a ref can appear under two kinds). */
  picks: Record<string, string>;
  onPick: (pickKey: string, targetId: string) => void;
}

/** One row per reference the bundle's checks point at, with a manual pick for
 * anything that did not resolve against the target workflow. */
const countLabels = (labels: string[]): Map<string, number> => {
  const counts = new Map<string, number>();
  for (const label of labels) counts.set(label, (counts.get(label) ?? 0) + 1);
  return counts;
};

/** A label shared by several nodes (a workflow can hold many "Set State" nodes)
 * makes entries indistinguishable — append a short id to those. */
const disambiguate = (label: string, id: string, counts: Map<string, number>) =>
  (counts.get(label) ?? 0) > 1 ? `${label} (${id.slice(0, 6)})` : label;

const buildDisplayNames = (
  nodeRefs: BundleNodeResolution[],
): Record<string, string> => {
  const counts = countLabels(nodeRefs.map((r) => r.label || r.ref));
  const names: Record<string, string> = {};
  for (const nodeRef of nodeRefs) {
    const label = nodeRef.label || nodeRef.ref;
    names[nodeRefKey(nodeRef)] = disambiguate(label, nodeRef.ref, counts);
  }
  return names;
};

export const ImportMappingTable: React.FC<ImportMappingTableProps> = ({
  nodeRefs,
  catalog,
  catalogUnavailable = false,
  picks,
  onPick,
}) => {
  const displayNames = buildDisplayNames(nodeRefs);
  const typeById = buildNodeTypeIndex(catalog);
  const hasUnresolved = nodeRefs.some((nodeRef) => nodeRef.status !== "resolved");
  // Rows where the user asked to see every node, not just same-type ones.
  const [showAllFor, setShowAllFor] = useState<Set<string>>(new Set());
  const allowAll = (key: string) =>
    setShowAllFor((current) => new Set(current).add(key));
  return (
  <div className="space-y-2">
  {catalogUnavailable && hasUnresolved && (
    <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
      Couldn't load this workflow's nodes, so references can't be mapped by hand
      right now. Retry, or import without the unmatched checks.
    </p>
  )}
  <div className="rounded-lg border overflow-hidden">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted text-left text-xs font-medium text-muted-foreground">
          <th className="px-4 py-2 font-medium">Reference</th>
          <th className="px-4 py-2 font-medium">Kind</th>
          <th className="px-4 py-2 font-medium">Target</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {nodeRefs.map((nodeRef) => {
          const isResolved = nodeRef.status === "resolved";
          // A note means the name matched but something about it needs a human
          // decision (a differing node type), so offer the whole catalog rather
          // than only the suspicious candidate.
          const needsReview = Boolean(nodeRef.note);
          const isAmbiguous = nodeRef.status === "ambiguous";
          const rowKey = nodeRefKey(nodeRef);
          const allOptions =
            isAmbiguous && !needsReview
              ? nodeRef.candidates
              : catalogOptionsForKind(catalog, nodeRef.kind);
          // Offer only nodes that could play the same role as the original;
          // picking among every node in the graph is not a decision anyone can
          // make well. The full list stays one click away.
          // A "needs review" row asks the user to confirm one specific candidate,
          // so that candidate must survive narrowing. Only that row: for an
          // ambiguous row the options ARE the candidates, and keeping them all
          // would disable narrowing entirely.
          const sameType = showAllFor.has(rowKey)
            ? null
            : narrowToOriginalType(
                allOptions,
                nodeRef.original_type,
                typeById,
                needsReview ? nodeRef.candidates : [],
              );
          const options = sameType ?? allOptions;
          const hiddenCount = sameType ? allOptions.length - sameType.length : 0;
          // Nodes of this kind exist, but none of the original's type.
          const noSuitableType = options.length === 0 && allOptions.length > 0;
          const optionCounts = countLabels(options.map((o) => o.label));
          return (
            <tr key={`${nodeRef.kind}:${nodeRef.ref}`}>
              <td className="px-4 py-2">
                <span className="font-medium">{displayNames[rowKey]}</span>
                {nodeRef.original_type && !isResolved && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    was a {nodeRef.original_type}
                  </p>
                )}
                {nodeRef.note && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{nodeRef.note}</p>
                )}
              </td>
              <td className="px-4 py-2">
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  {KIND_LABELS[nodeRef.kind] ?? nodeRef.kind}
                </Badge>
              </td>
              <td className="px-4 py-2">
                {isResolved ? (
                  <span className="flex items-center gap-1.5 text-green-700 dark:text-green-400">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    {nodeRef.resolved_label || nodeRef.resolved_id}
                  </span>
                ) : options.length > 0 ? (
                  <>
                  <Select
                    value={picks[rowKey] ?? ""}
                    onValueChange={(value) => onPick(rowKey, value)}
                  >
                    <SelectTrigger className="h-8 w-full max-w-64">
                      <SelectValue
                        placeholder={
                          needsReview
                            ? "Confirm or pick the right node"
                            : isAmbiguous
                              ? "Several matches — choose one"
                              : "No match — choose manually"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {options.map((option) => (
                        <SelectItem key={option.id} value={option.id}>
                          {disambiguate(option.label, option.id, optionCounts)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {hiddenCount > 0 && (
                    <button
                      type="button"
                      onClick={() => allowAll(rowKey)}
                      className="mt-1 text-xs text-muted-foreground underline hover:text-foreground"
                    >
                      Showing same-type nodes only — show all {allOptions.length}
                    </button>
                  )}
                  </>
                ) : noSuitableType ? (
                  <div className="space-y-1">
                    <span className="flex items-center gap-1.5 text-amber-700 dark:text-amber-400">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                      No {nodeRef.original_type} in this workflow
                    </span>
                    <button
                      type="button"
                      onClick={() => allowAll(rowKey)}
                      className="text-xs text-muted-foreground underline hover:text-foreground"
                    >
                      Choose from all {allOptions.length} anyway
                    </button>
                  </div>
                ) : (
                  <span className="flex items-center gap-1.5 text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    This workflow has no {KIND_PLURALS[nodeRef.kind] ?? "matches"} to
                    map to
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
  </div>
  );
};

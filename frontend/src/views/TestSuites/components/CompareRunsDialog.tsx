import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Loader2,
  Minus,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { listResultsForRun } from "@/services/testSuites";
import { getToolRuleResults } from "@/services/testEvaluations";
import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";
import { cn } from "@/helpers/utils";
import { methodLabel } from "../helpers/methodLabels";
import { CaseStatus, caseStatusFor, isTurnScope } from "../helpers/runResults";

interface CompareRunsDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** All runs of the evaluation, newest first. */
  runs: TestRun[];
}

type CaseChange = "regression" | "improvement" | "unchanged" | "other";

interface CaseComparison {
  caseId: string;
  baseline: CaseStatus | null;
  candidate: CaseStatus | null;
  change: CaseChange;
}

interface RunData {
  results: TestResult[];
  ruleResults: TestToolRuleResult[];
}

/** Summary metric shape stored per technique on a run. */
type TechniqueSummary = { accuracy?: number };

const RUN_TOTALS_KEY = "_totals";

const runLabel = (run: TestRun): string => {
  const version = run.workflow_version ? ` · v${run.workflow_version}` : "";
  const date = run.created_at
    ? ` · ${new Date(run.created_at).toLocaleString()}`
    : "";
  return `Run #${run.id?.slice(-4)}${version}${date}`;
};

const classifyChange = (
  baseline: CaseStatus | null,
  candidate: CaseStatus | null,
): CaseChange => {
  if (baseline === "passed" && candidate === "failed") return "regression";
  if (baseline === "failed" && candidate === "passed") return "improvement";
  if (baseline === candidate) return "unchanged";
  return "other";
};

const CHANGE_ORDER: Record<CaseChange, number> = {
  regression: 0,
  improvement: 1,
  other: 2,
  unchanged: 3,
};

const StatusIcon: React.FC<{ status: CaseStatus | null }> = ({ status }) => {
  if (status === "passed") {
    return <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />;
  }
  if (status === "failed") {
    return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
  }
  if (status === "not_scored") {
    return <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
  }
  return <Minus className="h-4 w-4 text-muted-foreground/50" />;
};

const ChangeBadge: React.FC<{ change: CaseChange }> = ({ change }) => {
  if (change === "regression") {
    return (
      <Badge className="bg-red-50 text-red-700 border border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30">
        <ArrowDownRight className="mr-1 h-3 w-3" />
        Regression
      </Badge>
    );
  }
  if (change === "improvement") {
    return (
      <Badge className="bg-green-50 text-green-700 border border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30">
        <ArrowUpRight className="mr-1 h-3 w-3" />
        Improved
      </Badge>
    );
  }
  return null;
};

const TechniqueDelta: React.FC<{
  technique: string;
  baseline: number | null;
  candidate: number | null;
}> = ({ technique, baseline, candidate }) => {
  const hasBoth = baseline !== null && candidate !== null;
  const delta = hasBoth ? candidate - baseline : null;
  const deltaClass =
    delta === null || Math.abs(delta) < 0.005
      ? "text-muted-foreground"
      : delta > 0
        ? "text-green-600 dark:text-green-400"
        : "text-red-600 dark:text-red-400";
  const percent = (value: number | null) =>
    value === null ? "–" : `${Math.round(value * 100)}%`;

  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="truncate text-muted-foreground">{methodLabel(technique)}</span>
      <span className="shrink-0 tabular-nums">
        {percent(baseline)} → {percent(candidate)}{" "}
        {delta !== null && (
          <span className={cn("font-medium", deltaClass)}>
            ({delta > 0 ? "+" : ""}
            {Math.round(delta * 100)}%)
          </span>
        )}
      </span>
    </div>
  );
};

export const CompareRunsDialog: React.FC<CompareRunsDialogProps> = ({
  isOpen,
  onOpenChange,
  runs,
}) => {
  const [baselineRunId, setBaselineRunId] = useState<string>("");
  const [candidateRunId, setCandidateRunId] = useState<string>("");
  const [dataByRunId, setDataByRunId] = useState<Record<string, RunData>>({});
  const [isLoading, setIsLoading] = useState(false);

  // Only finished runs have stable results worth comparing.
  const comparableRuns = useMemo(
    () => runs.filter((run) => run.id && (run.status === "completed" || run.status === "failed")),
    [runs],
  );

  // Default to the two most recent finished runs: newest as candidate.
  useEffect(() => {
    if (!isOpen) return;
    setCandidateRunId(comparableRuns[0]?.id ?? "");
    setBaselineRunId(comparableRuns[1]?.id ?? "");
  }, [isOpen, comparableRuns]);

  useEffect(() => {
    const idsToLoad = [baselineRunId, candidateRunId].filter(
      (id) => id && !dataByRunId[id],
    );
    if (!isOpen || idsToLoad.length === 0) return;
    let isStale = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const loaded = await Promise.all(
          idsToLoad.map(async (runId) => {
            const [results, ruleResults] = await Promise.all([
              listResultsForRun(runId),
              getToolRuleResults(runId).catch(() => []),
            ]);
            return [runId, { results: results ?? [], ruleResults: ruleResults ?? [] }] as const;
          }),
        );
        if (isStale) return;
        setDataByRunId((prev) => ({ ...prev, ...Object.fromEntries(loaded) }));
      } finally {
        if (!isStale) setIsLoading(false);
      }
    };
    void load();
    return () => {
      isStale = true;
    };
  }, [isOpen, baselineRunId, candidateRunId, dataByRunId]);

  const statusByCase = (runId: string): Map<string, CaseStatus> => {
    const data = dataByRunId[runId];
    const map = new Map<string, CaseStatus>();
    if (!data) return map;
    const rulesByCase = new Map<string, TestToolRuleResult[]>();
    for (const ruleResult of data.ruleResults) {
      if (isTurnScope(ruleResult.scope) && ruleResult.case_id) {
        const existing = rulesByCase.get(ruleResult.case_id) ?? [];
        existing.push(ruleResult);
        rulesByCase.set(ruleResult.case_id, existing);
      }
    }
    for (const result of data.results) {
      if (!result.case_id) continue;
      map.set(result.case_id, caseStatusFor(result, rulesByCase.get(result.case_id) ?? []));
    }
    return map;
  };

  const comparisons: CaseComparison[] = useMemo(() => {
    if (!baselineRunId || !candidateRunId) return [];
    const baselineStatuses = statusByCase(baselineRunId);
    const candidateStatuses = statusByCase(candidateRunId);
    const caseIds = new Set([...baselineStatuses.keys(), ...candidateStatuses.keys()]);
    const rows = [...caseIds].map((caseId) => {
      const baseline = baselineStatuses.get(caseId) ?? null;
      const candidate = candidateStatuses.get(caseId) ?? null;
      return { caseId, baseline, candidate, change: classifyChange(baseline, candidate) };
    });
    return rows.sort((a, b) => CHANGE_ORDER[a.change] - CHANGE_ORDER[b.change]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baselineRunId, candidateRunId, dataByRunId]);

  const regressionCount = comparisons.filter((c) => c.change === "regression").length;
  const improvementCount = comparisons.filter((c) => c.change === "improvement").length;

  const baselineRun = comparableRuns.find((run) => run.id === baselineRunId);
  const candidateRun = comparableRuns.find((run) => run.id === candidateRunId);

  // Per-technique accuracy across both runs, keyed by technique.
  const techniqueRows = useMemo(() => {
    const accuracyOf = (run: TestRun | undefined, technique: string): number | null => {
      const summary = run?.summary_metrics?.[technique] as TechniqueSummary | undefined;
      return typeof summary?.accuracy === "number" ? summary.accuracy : null;
    };
    const techniques = new Set<string>();
    [baselineRun, candidateRun].forEach((run) => {
      Object.keys(run?.summary_metrics ?? {})
        .filter((key) => key !== RUN_TOTALS_KEY)
        .forEach((key) => techniques.add(key));
    });
    return [...techniques].map((technique) => ({
      technique,
      baseline: accuracyOf(baselineRun, technique),
      candidate: accuracyOf(candidateRun, technique),
    }));
  }, [baselineRun, candidateRun]);

  const verdict =
    regressionCount > 0
      ? `${regressionCount} regression${regressionCount !== 1 ? "s" : ""}`
      : "No regressions";

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] w-[95vw] max-w-3xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b px-5 py-3">
          <DialogTitle>Compare Runs</DialogTitle>
        </DialogHeader>

        <div className="shrink-0 space-y-3 border-b px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">Baseline</div>
              <Select value={baselineRunId} onValueChange={setBaselineRunId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a run" />
                </SelectTrigger>
                <SelectContent>
                  {comparableRuns.map((run) => (
                    <SelectItem key={run.id} value={run.id!}>
                      {runLabel(run)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">Candidate</div>
              <Select value={candidateRunId} onValueChange={setCandidateRunId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a run" />
                </SelectTrigger>
                <SelectContent>
                  {comparableRuns.map((run) => (
                    <SelectItem key={run.id} value={run.id!}>
                      {runLabel(run)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {baselineRun && candidateRun && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant="outline"
                  className={cn(
                    regressionCount > 0
                      ? "border-red-200 text-red-700 dark:border-red-500/30 dark:text-red-400"
                      : "border-green-200 text-green-700 dark:border-green-500/30 dark:text-green-400",
                  )}
                >
                  {verdict}
                </Badge>
                {improvementCount > 0 && (
                  <Badge variant="outline" className="border-green-200 text-green-700 dark:border-green-500/30 dark:text-green-400">
                    {improvementCount} improved
                  </Badge>
                )}
              </div>
              {techniqueRows.length > 0 && (
                <div className="space-y-1 rounded border p-3">
                  {techniqueRows.map((row) => (
                    <TechniqueDelta
                      key={row.technique}
                      technique={row.technique}
                      baseline={row.baseline}
                      candidate={row.candidate}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading results…
            </div>
          ) : !baselineRunId || !candidateRunId ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Choose two finished runs to compare.
            </div>
          ) : comparisons.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              These runs share no scored test cases.
            </div>
          ) : (
            <div className="divide-y divide-border">
              <div className="flex items-center gap-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                <span className="flex-1">Case</span>
                <span className="w-16 text-center">Baseline</span>
                <span className="w-16 text-center">Candidate</span>
                <span className="w-28" />
              </div>
              {comparisons.map((row) => (
                <div key={row.caseId} className="flex items-center gap-3 py-2">
                  <span className="flex-1 truncate text-sm">
                    Case #{row.caseId.slice(-4)}
                  </span>
                  <span className="flex w-16 justify-center">
                    <StatusIcon status={row.baseline} />
                  </span>
                  <span className="flex w-16 justify-center">
                    <StatusIcon status={row.candidate} />
                  </span>
                  <span className="flex w-28 justify-end">
                    <ChangeBadge change={row.change} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

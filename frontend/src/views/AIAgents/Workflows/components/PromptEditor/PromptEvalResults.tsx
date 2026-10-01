import React from "react";
import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/badge";
import type {
  PromptEvalCaseResult,
  PromptEvalResponse,
} from "@/interfaces/promptEditor.interface";
import { methodLabel } from "@/views/TestSuites/helpers/methodLabels";
import {
  ISOLATION_NOTE,
  LEAKAGE_NOTE,
  STALE_NOTE,
  caseStatusLabel,
  formatAvgScore,
  joinPairedRuns,
  metricOutcomeLabel,
  metricOutcomeOf,
  snapshotHeader,
  summaryLine,
  type MetricOutcome,
  type ProviderFallback,
} from "../../utils/promptEditorResults";

/** Only a verdict is coloured. A case that never ran is neutral, never a red score */
const caseTone = (result: PromptEvalCaseResult): string => {
  if (result.status !== "scored") return "border-border bg-muted/40";
  if (result.verdict === "passed")
    return "border-green-200 bg-green-50 dark:border-green-500/30 dark:bg-green-500/15";
  if (result.verdict === "failed")
    return "border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/15";
  return "border-border bg-muted/40";
};

const CaseIcon: React.FC<{ result: PromptEvalCaseResult }> = ({ result }) => {
  if (result.status !== "scored")
    return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
  if (result.verdict === "passed")
    return <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />;
  if (result.verdict === "failed")
    return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
  return <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
};

const METRIC_TONE: Record<MetricOutcome, string> = {
  passed: "text-green-700 dark:text-green-400",
  failed: "text-red-700 dark:text-red-400",
  error: "text-amber-700 dark:text-amber-400",
  not_evaluated: "text-amber-700 dark:text-amber-400",
  not_applicable: "text-muted-foreground",
};

const AMBER_BANNER =
  "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/15 " +
  "border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2 text-sm";

const Field: React.FC<{ label: string; value: string; suffix?: string }> = ({
  label,
  value,
  suffix,
}) => (
  <div>
    <p className="font-medium text-muted-foreground">{label}</p>
    <p className="line-clamp-3 whitespace-pre-wrap">
      {value}
      {suffix && <span className="text-muted-foreground">{suffix}</span>}
    </p>
  </div>
);

const CaseCard: React.FC<{ result: PromptEvalCaseResult }> = ({ result }) => {
  const metrics = Object.entries(result.metrics ?? {});
  return (
    <div className={`border rounded p-3 text-sm ${caseTone(result)}`}>
      <div className="flex items-center gap-2 mb-2">
        <CaseIcon result={result} />
        <span className="font-medium">{caseStatusLabel(result)}</span>
        {result.case_score !== null && (
          <span className="text-xs text-muted-foreground">
            {formatAvgScore(result.case_score)}
          </span>
        )}
      </div>
      {result.error && (
        <p className="text-xs text-muted-foreground mb-2">{result.error}</p>
      )}
      {metrics.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-2">
          {metrics.map(([technique, metric]) => (
            <span key={technique} className="flex items-baseline gap-1">
              <span className="font-medium">{methodLabel(technique)}</span>
              <span className={METRIC_TONE[metricOutcomeOf(metric)]}>
                {metricOutcomeLabel(metric)}
              </span>
            </span>
          ))}
        </div>
      )}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Field label="Input" value={result.input} />
        <Field label="Expected" value={result.expected} />
        <Field
          label="Actual"
          value={result.actual}
          suffix={result.actual_truncated ? " […shortened by the editor]" : undefined}
        />
      </div>
    </div>
  );
};

const Comparison: React.FC<{
  baseline: PromptEvalResponse;
  suggestion: PromptEvalResponse;
}> = ({ baseline, suggestion }) => {
  const joined = joinPairedRuns(baseline, suggestion);
  return (
    <div className="border-t pt-3 space-y-2">
      <p className="text-sm font-medium">
        {joined.improved} improved · {joined.regressed} regressed ·{" "}
        {joined.unchanged} unchanged
      </p>
      <p className="text-xs text-muted-foreground">
        {joined.compared} of {joined.rows.length} cases could be compared.
      </p>
      <div className="space-y-1 max-h-40 overflow-y-auto text-xs">
        {joined.rows.map((row) => (
          <div key={row.caseId} className="flex items-center gap-2">
            <span className="text-muted-foreground truncate flex-1">
              {row.baseline?.input ?? row.suggestion?.input ?? row.caseId}
            </span>
            <span>{row.baseline ? caseStatusLabel(row.baseline) : "—"}</span>
            <span className="text-muted-foreground">→</span>
            <span>{row.suggestion ? caseStatusLabel(row.suggestion) : "—"}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{LEAKAGE_NOTE}</p>
    </div>
  );
};

interface PromptEvalResultsProps {
  results: PromptEvalResponse;
  title?: string;
  /** The run no longer describes the current inputs. It stays on screen regardless */
  stale: boolean;
  /** Names the provider when the run itself carries no model fields */
  providerFallback?: ProviderFallback;
  /** Present for a paired hold-out run: the same cases under the current prompt */
  comparison?: { baseline: PromptEvalResponse };
  leaky?: boolean;
}

export const PromptEvalResults: React.FC<PromptEvalResultsProps> = ({
  results,
  title,
  stale,
  providerFallback,
  comparison,
  leaky,
}) => (
  <div className="space-y-3">
    <div className="flex flex-wrap items-center gap-3">
      {title && <p className="text-sm font-medium">{title}</p>}
      <Badge variant="secondary">{summaryLine(results.summary)}</Badge>
      <Badge variant="secondary">
        Avg Score: {formatAvgScore(results.summary.avg_score)}
      </Badge>
    </div>

    {stale && <div className={AMBER_BANNER}>{STALE_NOTE}</div>}

    <p className="text-xs text-muted-foreground">
      {snapshotHeader(results.provenance, providerFallback)}
    </p>
    <p className="text-xs text-muted-foreground">{ISOLATION_NOTE}</p>
    {leaky && !comparison && (
      <p className="text-xs text-muted-foreground">{LEAKAGE_NOTE}</p>
    )}

    {comparison && (
      <Comparison baseline={comparison.baseline} suggestion={results} />
    )}

    <div className="space-y-2 max-h-60 overflow-y-auto">
      {results.results.map((result, index) => (
        <CaseCard key={result.case_id || index} result={result} />
      ))}
    </div>
  </div>
);

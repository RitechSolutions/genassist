import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import JsonViewer from "@/components/JsonViewer";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { ChevronLeft, Play, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import {
  getTestRun,
  getTestRunsBatch,
  listTestCases,
  listResultsForRun,
  listTestSuites,
  startTestRun,
} from "@/services/testSuites";
import { getWorkflowsMinimal } from "@/services/workflows";
import {
  getTestEvaluationById,
  appendRunToEvaluation,
  getToolRuleResults,
} from "@/services/testEvaluations";
import { TestResult, TestRun, TestSuite } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/resizable";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/skeleton";
import { Progress } from "@/components/progress";
import { PaginationBar } from "@/components/PaginationBar";
import { cn } from "@/helpers/utils";
import { ToolUsageResults } from "../components/ToolUsageResults";
import { ToolUsageResultCard } from "../components/ToolUsageResultCard";

type ResultFilter = "all" | "passed" | "failed" | "not_scored";

const UNASSIGNED = "unassigned";
const RUNS_PAGE_SIZE = 6;

/** Execution counts the backend stores alongside the per-technique metrics. */
const RUN_TOTALS_KEY = "_totals";
// Tool Usage has its own dedicated, readable section, so it is left out of the
// generic per-technique summary grid to avoid a confusing "Avg Score" card.
const TOOL_USED_TECHNIQUE = "tool_used";

interface RunTotals {
  cases: number;
  executed: number;
  scored: number;
  scoring_failed: number;
  execution_failed: number;
  skipped: number;
}

const getMetricSourceLabel = (
  technique: string,
  config: Record<string, unknown> | undefined
): string | null => {
  switch (technique) {
    case "exact_match":
    case "contains":
    case "json_match":
      return "Expected Output";
    case "not_contains": {
      const hasPhrases = Array.isArray(config?.phrases) ? (config.phrases as unknown[]).length > 0 : Boolean(config?.text);
      return hasPhrases ? "Configured forbidden phrases" : "Forbidden phrases";
    }
    case "field_equals":
      return config?.expected !== undefined ? "Configured expected value" : "Expected Output";
    case "nli_eval": {
      const evidenceField = config?.evidence_field as string | undefined;
      return evidenceField ? `Run data: ${evidenceField}` : "Expected Output (evidence)";
    }
    case "provenance_eval": {
      const contextField = config?.context_field as string | undefined;
      return contextField ? `Run data: ${contextField}` : "Expected Output (context)";
    }
    case "llm_judge": {
      const sourceField = config?.source_field as string | undefined;
      return sourceField ? `Run data: ${sourceField}` : "Rubric only (no source)";
    }
    default:
      return null;
  }
};

// True only when the metric actually grades against the test case's expected output.
// The configurable metrics fall back to expected output unless a config override
// points them elsewhere (an inline expected value, or an evidence/context field).
const usesExpectedOutput = (
  technique: string,
  config: Record<string, unknown> | undefined
): boolean => {
  switch (technique) {
    case "exact_match":
    case "contains":
    case "json_match":
      return true;
    case "field_equals":
      return config?.expected === undefined;
    case "nli_eval":
      return !config?.evidence_field;
    case "provenance_eval":
      return !config?.context_field;
    default:
      return false;
  }
};

const hasMetrics = (result: TestResult): boolean =>
  !!result.metrics && Object.keys(result.metrics).length > 0;

// No metrics means no score, whatever the stored status claims.
const isResultNotScored = (result: TestResult): boolean =>
  !hasMetrics(result) || (!!result.status && result.status !== "scored");

const isResultPassed = (result: TestResult): boolean =>
  hasMetrics(result) &&
  !isResultNotScored(result) &&
  Object.values(result.metrics!).every((m) => m.passed);

const isResultFailed = (result: TestResult): boolean =>
  !isResultPassed(result) && !isResultNotScored(result);

const notScoredLabel = (result: TestResult): string => {
  if (result.status === "skipped") return "Skipped";
  if (result.status === "scoring_failed") return "Scoring failed";
  if (result.status === "execution_failed") return "Execution failed";
  return "Not scored";
};

const accuracyTextClass = (acc: number): string =>
  acc >= 0.9
    ? "text-green-600 dark:text-green-400"
    : acc >= 0.7
      ? "text-amber-600 dark:text-amber-400"
      : "text-red-600 dark:text-red-400";

// "completed" is the happy path and adds no signal, so it is not badged — only
// in-progress and failure states show.
const RunStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  if (status === "completed") return null;
  const inProgress = status === "queued" || status === "running";
  return (
    <Badge variant="outline" className="flex items-center gap-1 shrink-0">
      {inProgress && <Loader2 className="h-3 w-3 animate-spin" />}
      {status}
    </Badge>
  );
};

const EvaluationDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isRunDetailsOpen, setIsRunDetailsOpen] = useState(false);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [resultsByRun, setResultsByRun] = useState<Record<string, TestResult[]>>({});
  const [toolResultsByRun, setToolResultsByRun] = useState<Record<string, TestToolRuleResult[]>>({});
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [workflowName, setWorkflowName] = useState<string>("Dataset default");
  const [expectedOutputByCaseId, setExpectedOutputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [inputByCaseId, setInputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [resultFilter, setResultFilter] = useState<ResultFilter>("all");
  const [isLoadingRuns, setIsLoadingRuns] = useState(true);
  const [runsPage, setRunsPage] = useState(1);

  const [evaluation, setEvaluation] = useState<
    Awaited<ReturnType<typeof getTestEvaluationById>>
  >(undefined);

  useEffect(() => {
    if (!evaluationId) return;
    setRunsPage(1);
    getTestEvaluationById(evaluationId).then(setEvaluation);
  }, [evaluationId]);

  useEffect(() => {
    const loadContext = async () => {
      if (!evaluation) return;
      const [suites, workflows] = await Promise.all([
        listTestSuites(),
        getWorkflowsMinimal(),
      ]);
      const suiteData = (suites ?? []).find((item) => item.id === evaluation.suite_id);
      setSuite(suiteData ?? null);
      const workflowData = (workflows ?? []).find(
        (item: WorkflowMinimal) => item.id === evaluation.workflow_id,
      );
      setWorkflowName(workflowData?.name ?? "Dataset default");
    };
    loadContext();
  }, [evaluation]);

  useEffect(() => {
    const loadExpectedOutputs = async () => {
      if (!evaluation?.suite_id) {
        setExpectedOutputByCaseId({});
        return;
      }
      const cases = await listTestCases(evaluation.suite_id);
      const expectedMapping: Record<string, Record<string, unknown> | undefined> = {};
      const inputMapping: Record<string, Record<string, unknown> | undefined> = {};
      (cases ?? []).forEach((testCase) => {
        if (testCase.id) {
          expectedMapping[testCase.id] = testCase.expected_output;
          inputMapping[testCase.id] = testCase.input_data;
        }
      });
      setExpectedOutputByCaseId(expectedMapping);
      setInputByCaseId(inputMapping);
    };
    loadExpectedOutputs();
  }, [evaluation?.suite_id]);

  useEffect(() => {
    const loadRuns = async () => {
      setIsLoadingRuns(true);
      try {
        if (!evaluation?.run_ids?.length) {
          setRuns([]);
          return;
        }
        const runData = await getTestRunsBatch(evaluation.run_ids);
        setRuns(
          (runData ?? [])
            .filter(Boolean)
            .sort(
              (a, b) =>
                new Date(b?.created_at ?? 0).getTime() -
                new Date(a?.created_at ?? 0).getTime(),
            ) as TestRun[],
        );
      } finally {
        setIsLoadingRuns(false);
      }
    };
    loadRuns();
  }, [evaluation]);

  useEffect(() => {
    const loadSelectedRunResults = async () => {
      if (!selectedRunId) return;
      setSelectedCaseId(null);
      setResultFilter("all");
      setIsLoadingResults(true);
      try {
        const [data, toolRows] = await Promise.all([
          listResultsForRun(selectedRunId),
          getToolRuleResults(selectedRunId).catch(() => []),
        ]);
        setResultsByRun((prev) => ({ ...prev, [selectedRunId]: data ?? [] }));
        setToolResultsByRun((prev) => ({ ...prev, [selectedRunId]: toolRows ?? [] }));
      } finally {
        setIsLoadingResults(false);
      }
    };
    loadSelectedRunResults();
  }, [selectedRunId]);

  const handleRunEvaluation = async () => {
    if (!evaluation || !evaluationId) return;
    setIsRunning(true);
    try {
      // Memory threads are generated per conversation by the backend at run time.
      const runMetadata = evaluation.input_metadata ?? undefined;
      const created = await startTestRun(evaluation.suite_id, {
        techniques: evaluation.techniques,
        technique_configs: evaluation.technique_configs,
        workflow_id: evaluation.workflow_id,
        input_metadata: runMetadata,
      });
      if (created?.id) {
        await appendRunToEvaluation(evaluationId, created.id);
        setRuns((prev) => [created, ...prev]);
        setRunsPage(1); // jump back to the first page so the new run is visible

        // Poll every 10 seconds until the run reaches a terminal state.
        const pollInterval = setInterval(async () => {
          const updated = await getTestRun(created.id);
          if (!updated) return;
          setRuns((prev) =>
            prev.map((r) => (r.id === updated.id ? (updated as TestRun) : r))
          );
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollInterval);
            setIsRunning(false);
            const [results, toolRows] = await Promise.all([
              listResultsForRun(created.id),
              getToolRuleResults(created.id).catch(() => []),
            ]);
            setResultsByRun((prev) => ({ ...prev, [created.id]: results ?? [] }));
            setToolResultsByRun((prev) => ({ ...prev, [created.id]: toolRows ?? [] }));
          }
        }, 10_000);
        // Return early — setIsRunning(false) is handled by the interval above.
        return;
      }
    } catch {
      // fall through to finally
    }
    setIsRunning(false);
  };

  const openRun = (runId: string | undefined) => {
    if (!runId) return;
    setSelectedRunId(runId);
    setIsRunDetailsOpen(true);
  };

  const selectedRun = runs.find((run) => run.id === selectedRunId);
  const selectedRunResults = selectedRunId ? resultsByRun[selectedRunId] ?? [] : [];
  const selectedRunToolResults = selectedRunId ? toolResultsByRun[selectedRunId] ?? [] : [];

  // Turn-level tool results are shown inside the matching test-case detail; conversation
  // results stay in the run-level Tool Usage section.
  const toolResultsByCaseId = useMemo(() => {
    const rows = selectedRunId ? toolResultsByRun[selectedRunId] ?? [] : [];
    const map = new Map<string, TestToolRuleResult[]>();
    for (const toolResult of rows) {
      const isTurnScope =
        toolResult.scope === "every_turn" || toolResult.scope === "specific_turn";
      if (isTurnScope && toolResult.case_id) {
        const existing = map.get(toolResult.case_id) ?? [];
        existing.push(toolResult);
        map.set(toolResult.case_id, existing);
      }
    }
    return map;
  }, [selectedRunId, toolResultsByRun]);

  // A case's displayed status must reflect its turn-level Tool Usage results too: a
  // tool failure fails the case, and a tool pass can score an otherwise-unscored case.
  const caseTools = (result: TestResult): TestToolRuleResult[] =>
    result.case_id ? toolResultsByCaseId.get(result.case_id) ?? [] : [];

  const casePassed = (result: TestResult): boolean => {
    const tools = caseTools(result);
    const toolFailed = tools.some((t) => t.status === "failed");
    const toolPassed = tools.some((t) => t.status === "passed");
    if (toolFailed) return false;
    return isResultPassed(result) || (isResultNotScored(result) && toolPassed);
  };

  const caseFailed = (result: TestResult): boolean => {
    const toolFailed = caseTools(result).some((t) => t.status === "failed");
    return toolFailed || (!casePassed(result) && isResultFailed(result));
  };

  const caseNotScored = (result: TestResult): boolean =>
    !casePassed(result) && !caseFailed(result);

  const filterResults = () => {
    if (resultFilter === "passed") return selectedRunResults.filter(casePassed);
    if (resultFilter === "not_scored") return selectedRunResults.filter(caseNotScored);
    if (resultFilter === "failed") return selectedRunResults.filter(caseFailed);
    return selectedRunResults;
  };

  const filteredResults = filterResults();
  // Keep a case selected in the right column; fall back to the first in the current filter.
  const activeCase =
    filteredResults.find((r) => r.id === selectedCaseId) ?? filteredResults[0] ?? null;

  const passedCount = selectedRunResults.filter(casePassed).length;
  const failedCount = selectedRunResults.filter(caseFailed).length;
  const notScoredCount = selectedRunResults.filter(caseNotScored).length;

  const runTotals = (selectedRun?.summary_metrics as Record<string, unknown> | undefined)?.[
    RUN_TOTALS_KEY
  ] as RunTotals | undefined;

  const runAvgAccuracy = (run: TestRun): number | null => {
    const summaryMetrics = run.summary_metrics as Record<string, { accuracy?: number }> | undefined;
    const scored = Object.values(summaryMetrics ?? {}).filter((m) => typeof m.accuracy === "number");
    if (!scored.length) return null;
    return scored.reduce((sum, m, _, arr) => sum + (m.accuracy ?? 0) / arr.length, 0);
  };

  // Client-side pagination for the runs list (runs are all loaded up front).
  const runsTotalPages = Math.max(1, Math.ceil(runs.length / RUNS_PAGE_SIZE));
  const runsSafePage = Math.min(runsPage, runsTotalPages);
  const pagedRuns = runs.slice(
    (runsSafePage - 1) * RUNS_PAGE_SIZE,
    runsSafePage * RUNS_PAGE_SIZE,
  );

  // Runs are sorted newest-first, so the most recent is the summary for the header.
  const lastRun = runs[0];
  const lastRunAvg = lastRun ? runAvgAccuracy(lastRun) : null;
  const lastRunTotals = (lastRun?.summary_metrics as Record<string, unknown> | undefined)?.[
    RUN_TOTALS_KEY
  ] as RunTotals | undefined;

  if (!evaluation) {
    return (
      <PageLayout>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/tests/evaluations")}
            className="shrink-0"
            aria-label="Back to evaluations"
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">Evaluation not found</h1>
        </div>
      </PageLayout>
    );
  }

  const renderCaseDetail = (result: TestResult) => {
    const passed = casePassed(result);
    const notScored = caseNotScored(result);
    const gradedTechniques = Object.keys(result.metrics ?? {});
    const caseExpectedOutput = result.case_id ? expectedOutputByCaseId[result.case_id] : undefined;
    // Show Expected Output only when a graded metric actually uses it, so process-only
    // checks never imply they were graded against it.
    const showExpectedOutput =
      gradedTechniques.length === 0 ||
      gradedTechniques.some((tech) =>
        usesExpectedOutput(
          tech,
          evaluation?.technique_configs?.[tech] as Record<string, unknown> | undefined,
        ),
      );
    const caseToolRows = result.case_id ? toolResultsByCaseId.get(result.case_id) ?? [] : [];

    return (
      <>
        <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
          <div className="flex items-center gap-2 min-w-0">
            {notScored ? (
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            ) : passed ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            )}
            <span className="text-sm font-semibold">Case #{result.case_id?.slice(-4)}</span>
            {notScored && (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700">
                {notScoredLabel(result)}
              </span>
            )}
          </div>
          {result.metrics && (
            <div className="flex flex-wrap justify-end gap-1">
              {Object.entries(result.metrics).map(([tech, metricValue]) => (
                <span
                  key={tech}
                  className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-[10px]",
                    metricValue.passed
                      ? "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400"
                      : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400",
                  )}
                >
                  <span className="mr-1 font-semibold">{tech}</span>
                  {typeof metricValue.score === "number" && (
                    <span>
                      {metricValue.score <= 1
                        ? `${Math.round(metricValue.score * 100)}%`
                        : metricValue.score.toFixed(2)}
                    </span>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {/* Metric comments + grading source */}
          {result.metrics && (
            <div className="space-y-1">
              {Object.entries(result.metrics).map(([tech, metricValue]) => {
                const sourceLabel = getMetricSourceLabel(
                  tech,
                  evaluation?.technique_configs?.[tech],
                );
                if (!metricValue.comment && !sourceLabel) return null;
                return (
                  <div key={`${result.id}-${tech}-comment`} className="text-xs">
                    <span className="font-semibold text-muted-foreground">{tech}:</span>{" "}
                    {metricValue.comment && (
                      <span className="text-muted-foreground">{metricValue.comment}</span>
                    )}
                    {sourceLabel && (
                      <span className="text-muted-foreground">
                        {metricValue.comment ? " — " : ""}checked against: {sourceLabel}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Turn-level Tool Usage for this case */}
          {caseToolRows.length > 0 && (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">Tool Usage</div>
              <div className="space-y-2">
                {caseToolRows.map((toolResult) => (
                  <ToolUsageResultCard key={toolResult.id} result={toolResult} />
                ))}
              </div>
            </div>
          )}

          {/* Input / Expected comparison, side by side */}
          <div
            className={cn(
              "grid grid-cols-1 gap-4",
              showExpectedOutput && "lg:grid-cols-2",
            )}
          >
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-500"></span>
                Input
              </div>
              <div className="rounded border bg-card p-2 text-xs dark:bg-zinc-900">
                <JsonViewer
                  data={
                    ((result.case_id && (inputByCaseId[result.case_id] as unknown)) ??
                      {}) as unknown as never
                  }
                />
              </div>
            </div>
            {showExpectedOutput && (
              <div>
                <div className="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span>
                  Expected Output
                </div>
                <div className="rounded border bg-card p-2 text-xs dark:bg-zinc-900">
                  <JsonViewer data={(caseExpectedOutput ?? {}) as unknown as never} />
                </div>
              </div>
            )}
          </div>

          {/* Actual Output — full width, styled like Execution Trace */}
          <div>
            <div className="mb-1 text-xs font-medium text-muted-foreground">Actual Output</div>
            <div className="rounded border bg-card p-2 text-xs dark:bg-zinc-900">
              {result.actual_output &&
              "value" in result.actual_output &&
              Object.keys(result.actual_output).length === 1 ? (
                <div className="whitespace-pre-wrap">{String(result.actual_output.value)}</div>
              ) : (
                <JsonViewer data={(result.actual_output ?? {}) as unknown as never} />
              )}
            </div>
          </div>

          {result.execution_trace && Object.keys(result.execution_trace).length > 0 && (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">Execution Trace</div>
              <div className="rounded border bg-card p-2 text-xs dark:bg-zinc-900">
                <JsonViewer data={(result.execution_trace ?? {}) as unknown as never} />
              </div>
            </div>
          )}

          {result.error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-400">
              <div className="mb-1 font-medium">Error</div>
              {result.error}
            </div>
          )}
        </div>
      </>
    );
  };

  return (
    <PageLayout>
      {/* Header: back arrow + evaluation name + Run */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() =>
            navigate(`/tests/evaluations/workflows/${evaluation.workflow_id ?? UNASSIGNED}`)
          }
          className="shrink-0"
          aria-label="Back"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold tracking-tight animate-fade-down">
            {evaluation.name}
          </h1>
          {evaluation.description && (
            <p className="truncate text-sm text-muted-foreground">{evaluation.description}</p>
          )}
        </div>
        <Button
          onClick={handleRunEvaluation}
          disabled={isRunning}
          className="shrink-0"
          aria-label="Run evaluation"
        >
          {isRunning ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Play className="mr-2 h-4 w-4" />
          )}
          {isRunning ? "Running..." : "Run"}
        </Button>
      </div>

      {/* Configuration + Last Run summary */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Configuration */}
        <div className="rounded-lg border bg-card p-4 dark:bg-zinc-900">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Dataset
              </div>
              <div className="mt-0.5 truncate text-sm font-medium">
                {suite?.name ?? evaluation.suite_id}
              </div>
            </div>
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Workflow
              </div>
              <div className="mt-0.5 truncate text-sm font-medium">{workflowName}</div>
            </div>
            <div className="sm:col-span-2">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Metrics
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {evaluation.techniques.map((technique) => (
                  <Badge key={technique} variant="secondary">
                    {technique}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Last Run Details */}
        <div className="rounded-lg border bg-card p-4 dark:bg-zinc-900">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Last Run
            </div>
            {lastRun && (
              <button
                type="button"
                onClick={() => openRun(lastRun.id)}
                className="text-xs font-medium text-primary hover:underline"
              >
                View details
              </button>
            )}
          </div>
          {isLoadingRuns ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-2 w-40" />
            </div>
          ) : !lastRun ? (
            <div className="text-sm text-muted-foreground">No runs yet.</div>
          ) : (
            <div className="space-y-2">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">Run #{lastRun.id?.slice(-4)}</span>
                  <RunStatusBadge status={lastRun.status} />
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {new Date(lastRun.created_at ?? "").toLocaleString()}
                </div>
              </div>
              {lastRunAvg !== null ? (
                <div className="flex items-center gap-2">
                  <Progress
                    value={lastRunAvg * 100}
                    className={cn(
                      "h-2 w-40",
                      lastRunAvg >= 0.9
                        ? "[&>div]:bg-green-600"
                        : lastRunAvg >= 0.7
                          ? "[&>div]:bg-amber-600"
                          : "[&>div]:bg-red-600",
                    )}
                  />
                  <span className={cn("text-sm font-semibold", accuracyTextClass(lastRunAvg))}>
                    {Math.round(lastRunAvg * 100)}%
                  </span>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {lastRun.status === "completed" ? "No score" : "Not scored yet"}
                </div>
              )}
              {lastRunTotals && (
                <div className="text-xs text-muted-foreground">
                  {lastRunTotals.scored} of {lastRunTotals.cases} records scored
                  {lastRunTotals.execution_failed > 0 &&
                    ` · ${lastRunTotals.execution_failed} failed to execute`}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Runs as cards */}
      <div className="rounded-lg border bg-card p-4 dark:bg-zinc-900">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Previous Executions</h2>
          <Badge variant="secondary" className="text-xs">
            {runs.length} run{runs.length !== 1 ? "s" : ""}
          </Badge>
        </div>

        {isLoadingRuns ? (
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2 rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="h-3 w-32" />
                <div className="flex gap-1">
                  <Skeleton className="h-5 w-20 rounded-full" />
                  <Skeleton className="h-5 w-20 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <Play className="mb-2 h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No runs yet</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Click "Run" to execute your first run.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {pagedRuns.map((run) => {
              const avgAccuracy = runAvgAccuracy(run);
              const summaryMetrics = run.summary_metrics as
                | Record<string, { accuracy?: number }>
                | undefined;
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => openRun(run.id)}
                  className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Run #{run.id?.slice(-4)}</span>
                      {avgAccuracy !== null && (
                        <div className="flex items-center gap-1">
                          <Progress
                            value={avgAccuracy * 100}
                            className={cn(
                              "h-1.5 w-16",
                              avgAccuracy >= 0.9
                                ? "[&>div]:bg-success"
                                : avgAccuracy >= 0.7
                                  ? "[&>div]:bg-warning"
                                  : "[&>div]:bg-destructive",
                            )}
                          />
                          <span className={cn("text-xs font-medium", accuracyTextClass(avgAccuracy))}>
                            {Math.round(avgAccuracy * 100)}%
                          </span>
                        </div>
                      )}
                      {avgAccuracy === null && run.status === "completed" && (
                        <span className="text-xs text-muted-foreground">No score</span>
                      )}
                    </div>
                    <RunStatusBadge status={run.status} />
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {new Date(run.created_at ?? "").toLocaleString()}
                  </div>
                  {summaryMetrics && (
                    <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                      {Object.entries(summaryMetrics)
                        .filter(([tech]) => tech !== RUN_TOTALS_KEY)
                        .map(([tech, summary]) => {
                          const acc = typeof summary.accuracy === "number" ? summary.accuracy : null;
                          let colorClasses = "bg-muted text-muted-foreground border border-border";
                          if (acc !== null) {
                            if (acc >= 0.9) {
                              colorClasses =
                                "bg-green-50 text-green-700 border border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30";
                            } else if (acc >= 0.7) {
                              colorClasses =
                                "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/15 dark:text-amber-400 dark:border-amber-500/30";
                            } else {
                              colorClasses =
                                "bg-red-50 text-red-700 border border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30";
                            }
                          }
                          return (
                            <span
                              key={tech}
                              className={`inline-flex items-center rounded-full px-2 py-0.5 ${colorClasses}`}
                            >
                              <span className="mr-1 font-semibold">{tech}</span>
                              {acc !== null && <span>{Math.round(acc * 100)}%</span>}
                            </span>
                          );
                        })}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {!isLoadingRuns && runs.length > RUNS_PAGE_SIZE && (
          <PaginationBar
            total={runs.length}
            currentPage={runsSafePage}
            pageSize={RUNS_PAGE_SIZE}
            pageItemCount={pagedRuns.length}
            onPageChange={setRunsPage}
          />
        )}
      </div>

      {/* Run Details — big dialog with columns (Test Workflow style) */}
      <Dialog
        open={isRunDetailsOpen && !!selectedRun}
        onOpenChange={(open) => {
          setIsRunDetailsOpen(open);
          if (!open) setResultFilter("all");
        }}
      >
        <DialogContent className="flex h-[90vh] max-h-[90vh] w-[95vw] max-w-[1400px] flex-col gap-0 overflow-hidden p-0">
          <DialogHeader className="shrink-0 border-b px-5 py-3">
            <div className="flex items-center justify-between gap-3">
              <DialogTitle>Run Details #{selectedRun?.id?.slice(-4)}</DialogTitle>
              {selectedRun && <RunStatusBadge status={selectedRun.status} />}
            </div>
            {selectedRun?.created_at && (
              <p className="text-xs text-muted-foreground">
                {new Date(selectedRun.created_at).toLocaleString()}
              </p>
            )}
          </DialogHeader>

          {/* Evaluation Summary */}
          <div className="shrink-0 border-b px-5 py-4">
            <div className="mb-3 text-sm font-medium">Evaluation Summary</div>
            {runTotals && runTotals.scored < runTotals.cases && (
              <div className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-400">
                Scores cover {runTotals.scored} of {runTotals.cases} records
                {runTotals.execution_failed > 0 &&
                  ` · ${runTotals.execution_failed} failed to execute`}
                {runTotals.scoring_failed > 0 &&
                  ` · ${runTotals.scoring_failed} ran but failed scoring`}
                {runTotals.skipped > 0 && ` · ${runTotals.skipped} skipped`}
              </div>
            )}
            {selectedRun?.summary_metrics ? (
              <div className="grid max-h-[200px] grid-cols-1 gap-3 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Object.entries(
                  selectedRun.summary_metrics as Record<
                    string,
                    { accuracy?: number; avg_score?: number; cases?: number }
                  >,
                )
                  .filter(([tech]) => tech !== RUN_TOTALS_KEY && tech !== TOOL_USED_TECHNIQUE)
                  .map(([tech, summary]) => {
                    const acc = typeof summary.accuracy === "number" ? summary.accuracy : null;
                    return (
                      <div key={tech} className="rounded-lg border bg-card p-3 dark:bg-zinc-900">
                        <div className="mb-2 text-xs font-medium text-muted-foreground">{tech}</div>
                        {acc !== null && (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <span className={cn("text-lg font-semibold", accuracyTextClass(acc))}>
                                {Math.round(acc * 100)}%
                              </span>
                              {typeof summary.cases === "number" && (
                                <span className="text-xs text-muted-foreground">
                                  {summary.cases} cases
                                </span>
                              )}
                            </div>
                            <Progress
                              value={acc * 100}
                              className={cn(
                                "h-2",
                                acc >= 0.9
                                  ? "[&>div]:bg-success"
                                  : acc >= 0.7
                                    ? "[&>div]:bg-warning"
                                    : "[&>div]:bg-destructive",
                              )}
                            />
                          </div>
                        )}
                        {typeof summary.avg_score === "number" && (
                          <div className="mt-1 text-sm">
                            Avg Score:{" "}
                            <span className="font-medium">{summary.avg_score.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No metrics available</div>
            )}
          </div>

          {/* Columns: results list | selected case detail */}
          <div className="min-h-0 flex-1">
            <ResizablePanelGroup
              direction="horizontal"
              autoSaveId="run-details-v1"
              className="h-full"
            >
              <ResizablePanel defaultSize={40} minSize={28} maxSize={55}>
                <div className="flex h-full flex-col overflow-hidden">
                  <div className="shrink-0 border-b px-3 py-2.5">
                    <Tabs value={resultFilter} onValueChange={(v) => setResultFilter(v as ResultFilter)}>
                      <TabsList className="h-8">
                        <TabsTrigger value="all" className="px-2.5 py-1 text-xs">
                          All ({selectedRunResults.length})
                        </TabsTrigger>
                        <TabsTrigger value="passed" className="px-2.5 py-1 text-xs">
                          <CheckCircle2 className="mr-1 h-3 w-3 text-green-600 dark:text-green-400" />
                          {passedCount}
                        </TabsTrigger>
                        <TabsTrigger value="failed" className="px-2.5 py-1 text-xs">
                          <XCircle className="mr-1 h-3 w-3 text-red-600 dark:text-red-400" />
                          {failedCount}
                        </TabsTrigger>
                        <TabsTrigger value="not_scored" className="px-2.5 py-1 text-xs">
                          <AlertCircle className="mr-1 h-3 w-3 text-amber-600" />
                          {notScoredCount}
                        </TabsTrigger>
                      </TabsList>
                    </Tabs>
                  </div>
                  <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                    {selectedRunToolResults.length > 0 && <ToolUsageResults results={selectedRunToolResults} />}

                    {isLoadingResults ? (
                      [1, 2, 3, 4].map((i) => (
                        <div key={i} className="rounded-md border p-3">
                          <Skeleton className="h-4 w-24" />
                          <Skeleton className="mt-2 h-3 w-40" />
                        </div>
                      ))
                    ) : filteredResults.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-8 text-center">
                        <AlertCircle className="mb-2 h-8 w-8 text-muted-foreground/40" />
                        <p className="text-sm text-muted-foreground">
                          {resultFilter === "all"
                            ? "No test results available yet."
                            : resultFilter === "passed"
                              ? "No passed test cases."
                              : resultFilter === "not_scored"
                                ? "No unscored test cases."
                                : "No failed test cases."}
                        </p>
                      </div>
                    ) : (
                      filteredResults.map((result) => {
                        const passed = casePassed(result);
                        const notScored = caseNotScored(result);
                        const isActive = activeCase?.id === result.id;
                        return (
                          <button
                            key={result.id}
                            type="button"
                            onClick={() => setSelectedCaseId(result.id ?? null)}
                            className={cn(
                              "w-full rounded-md border p-2.5 text-left transition-colors",
                              isActive ? "bg-primary/5 ring-1 ring-primary" : "hover:bg-muted",
                            )}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                {notScored ? (
                                  <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                                ) : passed ? (
                                  <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
                                ) : (
                                  <XCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
                                )}
                                <span className="truncate text-sm font-medium">
                                  Case #{result.case_id?.slice(-4)}
                                </span>
                              </div>
                            </div>
                            {result.metrics && (
                              <div className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">
                                {Object.entries(result.metrics)
                                  .filter(([, m]) => m.comment)
                                  .map(([tech, m]) => `${tech}: ${m.comment}`)
                                  .join(" | ") || notScoredLabel(result)}
                              </div>
                            )}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle withHandle />

              <ResizablePanel defaultSize={60} minSize={45}>
                <div className="flex h-full flex-col overflow-hidden">
                  {activeCase ? (
                    renderCaseDetail(activeCase)
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                      <AlertCircle className="mb-3 h-10 w-10 text-muted-foreground/30" />
                      <p className="text-sm text-muted-foreground">
                        {isLoadingResults ? "Loading results…" : "Select a case to see its details."}
                      </p>
                    </div>
                  )}
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
};

export default EvaluationDetailPage;

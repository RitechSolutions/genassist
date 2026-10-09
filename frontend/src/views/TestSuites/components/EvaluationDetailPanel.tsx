import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import JsonViewer from "@/components/JsonViewer";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  ChevronLeft,
  GitBranch,
  GitCompareArrows,
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import {
  getTestRunsBatch,
  listTestCases,
  listResultsForRun,
  listTestSuites,
} from "@/services/testSuites";
import { getWorkflowsMinimal } from "@/services/workflows";
import {
  getTestEvaluationById,
  getToolRuleResults,
  runTestEvaluation,
} from "@/services/testEvaluations";
import { TestCase, TestResult, TestRun, TestSuite } from "@/interfaces/testSuite.interface";
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
import { TooltipProvider } from "@/components/RadixTooltip";
import { TooltipButton } from "@/components/tooltip-button";
import { cn } from "@/helpers/utils";
import { RuleResults } from "./RuleResults";
import { RuleResultCard } from "./RuleResultCard";
import { RunAgainstVersionDialog } from "./RunAgainstVersionDialog";
import { CompareRunsDialog } from "./CompareRunsDialog";
import { MetricRuleBreakdown } from "./MetricRuleBreakdown";
import { methodLabel } from "../helpers/methodLabels";
import {
  NOT_EVALUATED,
  caseStatusFor,
  groupByTechnique,
  isRuleTechnique,
  isRunInProgress,
  isTurnScope,
  notScoredLabel,
  runAvgAccuracy,
  runFailureText,
  runProgressText,
  runStatusLabel,
  techniqueAccuracy,
  techniqueSummaries,
  turnsPassed,
} from "../helpers/runResults";
import { checkedAgainstLine, metricSourceLabel, usesExpectedOutput } from "../helpers/metricSources";
import { isRunConflict, runStartErrorMessage } from "../helpers/runErrors";
import { caseLabel, indexConversations } from "../helpers/datasetConversations";

type ResultFilter = "all" | "passed" | "failed" | "not_scored";

const RUNS_PAGE_SIZE = 6;
const RUNNING_POLL_MS = 5000;
const NO_RUNS: TestRun[] = [];
const NO_RUN_IDS: string[] = [];
const AVG_SCORE_HINT = "Avg score: the average of each method's pass rate";

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

export interface EvaluationDetailPanelProps {
  /** Evaluation to show. */
  evaluationId: string;
  /** Return to the list. In-tab callers swap views; the route wrapper navigates. */
  onBack: () => void;
  /** Accessible label for the back button (e.g. "Evaluations"). */
  backLabel?: string;
  /**
   * Called with the evaluation's own workflow id once it loads (null when it uses
   * the dataset default). Lets the standalone route send "back" to the right
   * workflow page; the in-tab caller ignores it.
   */
  onWorkflowResolved?: (workflowId: string | null) => void;
}

const accuracyTextClass = (acc: number): string =>
  acc >= 0.9
    ? "text-green-600 dark:text-green-400"
    : acc >= 0.7
      ? "text-amber-600 dark:text-amber-400"
      : "text-red-600 dark:text-red-400";

const accuracyBarClass = (acc: number): string =>
  acc >= 0.9 ? "[&>div]:bg-green-600" : acc >= 0.7 ? "[&>div]:bg-amber-600" : "[&>div]:bg-red-600";

// "completed" is the happy path and adds no signal, so it is not badged — only
// in-progress and failure states show.
const RunStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  if (status === "completed") return null;
  const inProgress = status === "queued" || status === "running";
  return (
    <Badge variant="outline" className="flex items-center gap-1 shrink-0">
      {inProgress && <Loader2 className="h-3 w-3 animate-spin" />}
      {runStatusLabel(status)}
    </Badge>
  );
};

/**
 * A single evaluation's detail — configuration, last run, previous executions,
 * run comparison and the run-details dialog. Extracted from EvaluationDetailPage
 * so the standalone `/tests` route and the workflow builder's Evaluations tab
 * share one implementation. Renders content only (no page chrome); callers wrap
 * it in PageLayout or the tab's scroll container.
 */
export const EvaluationDetailPanel: React.FC<EvaluationDetailPanelProps> = ({
  evaluationId,
  onBack,
  backLabel = "Back",
  onWorkflowResolved,
}) => {
  const queryClient = useQueryClient();
  const [isStarting, setIsStarting] = useState(false);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isRunDetailsOpen, setIsRunDetailsOpen] = useState(false);
  const [resultsByRun, setResultsByRun] = useState<Record<string, TestResult[]>>({});
  const [ruleResultsByRun, setRuleResultsByRun] = useState<Record<string, TestToolRuleResult[]>>({});
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [workflowName, setWorkflowName] = useState<string>("Dataset default");
  const [workflowAgentId, setWorkflowAgentId] = useState<string | null>(null);
  const [isVersionDialogOpen, setIsVersionDialogOpen] = useState(false);
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [expectedOutputByCaseId, setExpectedOutputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [inputByCaseId, setInputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [suiteCases, setSuiteCases] = useState<TestCase[]>([]);
  const [resultFilter, setResultFilter] = useState<ResultFilter>("all");
  const [runsPage, setRunsPage] = useState(1);

  const [evaluation, setEvaluation] = useState<
    Awaited<ReturnType<typeof getTestEvaluationById>>
  >(undefined);

  useEffect(() => {
    if (!evaluationId) return;
    setRunsPage(1);
    // A failed load ends the loading state instead of leaving skeletons up.
    getTestEvaluationById(evaluationId)
      .then(setEvaluation)
      .catch(() => setEvaluation(null));
  }, [evaluationId]);

  // Keyed on fields, so a run_ids change after Run does not refetch the context.
  const evaluationLoaded = Boolean(evaluation);
  const evaluationSuiteId = evaluation?.suite_id;
  const evaluationWorkflowId = evaluation?.workflow_id ?? null;

  // Report the evaluation's own workflow id so the standalone route can send
  // "back" to the correct workflow page (null → the dataset-default / unassigned).
  useEffect(() => {
    if (evaluationLoaded) onWorkflowResolved?.(evaluationWorkflowId);
  }, [evaluationLoaded, evaluationWorkflowId, onWorkflowResolved]);

  useEffect(() => {
    const loadContext = async () => {
      if (!evaluationLoaded) return;
      const [suites, workflows] = await Promise.all([
        listTestSuites(),
        getWorkflowsMinimal(),
      ]);
      const suiteData = (suites ?? []).find((item) => item.id === evaluationSuiteId);
      setSuite(suiteData ?? null);
      const workflowData = (workflows ?? []).find(
        (item: WorkflowMinimal) => item.id === evaluationWorkflowId,
      );
      setWorkflowName(
        workflowData?.agent_name || workflowData?.name || "Dataset default",
      );
      setWorkflowAgentId(workflowData?.agent_id ?? null);
    };
    loadContext();
  }, [evaluationLoaded, evaluationSuiteId, evaluationWorkflowId]);

  useEffect(() => {
    const loadExpectedOutputs = async () => {
      if (!evaluation?.suite_id) {
        setExpectedOutputByCaseId({});
        setSuiteCases([]);
        return;
      }
      const cases = await listTestCases(evaluation.suite_id);
      setSuiteCases(cases ?? []);
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

  const runIds = evaluation?.run_ids ?? NO_RUN_IDS;
  const runsQueryKey = (ids: string[]) => ["evaluation-runs", evaluationId, ids];

  // Polls while any run is queued or running, so a page opened mid-run still updates.
  const { data: runsData, isLoading: isRunsQueryLoading } = useQuery({
    queryKey: runsQueryKey(runIds),
    queryFn: async () =>
      ((await getTestRunsBatch(runIds)) ?? [])
        .filter(Boolean)
        .sort(
          (a, b) =>
            new Date(b?.created_at ?? 0).getTime() - new Date(a?.created_at ?? 0).getTime(),
        ),
    enabled: runIds.length > 0,
    staleTime: 0,
    // Keeps the list while a new run id changes the key, never another evaluation's runs.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === evaluationId ? previous : undefined,
    refetchInterval: (query) =>
      (query.state.data ?? []).some(isRunInProgress) ? RUNNING_POLL_MS : false,
  });
  const runs = runIds.length > 0 ? runsData ?? NO_RUNS : NO_RUNS;
  const isRunning = isStarting || runs.some(isRunInProgress);
  // Still loading until the evaluation says which runs it has.
  const isLoadingRuns = evaluation === undefined || (runIds.length > 0 && isRunsQueryLoading);

  // A finished run's results never change, so each is fetched once and shared.
  const finishedRunLoads = useRef(new Map<string, Promise<void>>());
  // The newest load per run; an older, slower response must not overwrite it.
  const latestRunLoad = useRef(new Map<string, number>());

  const loadRunResults = useCallback((runId: string, finished: boolean): Promise<void> => {
    const pending = finished ? finishedRunLoads.current.get(runId) : undefined;
    if (pending) return pending;
    const ticket = (latestRunLoad.current.get(runId) ?? 0) + 1;
    latestRunLoad.current.set(runId, ticket);
    const load = (async () => {
      const [data, ruleRows] = await Promise.all([
        listResultsForRun(runId),
        getToolRuleResults(runId).catch(() => []),
      ]);
      if (latestRunLoad.current.get(runId) !== ticket) return;
      setResultsByRun((prev) => ({ ...prev, [runId]: data ?? [] }));
      setRuleResultsByRun((prev) => ({ ...prev, [runId]: ruleRows ?? [] }));
    })();
    if (finished) {
      finishedRunLoads.current.set(runId, load);
      // A failed load may be retried.
      load.catch(() => finishedRunLoads.current.delete(runId));
    }
    return load;
  }, []);

  // Opening another run's details starts from the top.
  useEffect(() => {
    setSelectedCaseId(null);
    setResultFilter("all");
  }, [selectedRunId]);

  // Reloads when the selected run's status changes, so details opened mid-run fill in.
  const selectedRunStatus = runs.find((run) => run.id === selectedRunId)?.status;
  useEffect(() => {
    if (!selectedRunId) return;
    let cancelled = false;
    setIsLoadingResults(true);
    const finished = selectedRunStatus === "completed" || selectedRunStatus === "failed";
    loadRunResults(selectedRunId, finished).finally(() => {
      if (!cancelled) setIsLoadingResults(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedRunId, selectedRunStatus, loadRunResults]);

  // Runs are sorted newest-first, so the most recent is the summary for the header.
  const lastRun = runs[0];
  const lastRunId = lastRun?.id;
  const lastRunStatus = lastRun?.status;

  // The Last Run card counts turns passed, so it loads the run's results once it completes.
  useEffect(() => {
    if (!lastRunId || lastRunStatus !== "completed") return;
    // A failed load falls back to "No score" instead of a skeleton that never resolves.
    loadRunResults(lastRunId, true).catch(() =>
      setResultsByRun((prev) => ({ ...prev, [lastRunId]: prev[lastRunId] ?? [] })),
    );
  }, [lastRunId, lastRunStatus, loadRunResults]);

  const conversationIndex = useMemo(() => indexConversations(suiteCases), [suiteCases]);

  const handleRunEvaluation = async (targetWorkflowId?: string) => {
    if (!evaluation || !evaluationId) return;
    setIsStarting(true);
    try {
      const created = await runTestEvaluation(evaluationId, targetWorkflowId);
      if (created?.id) {
        // Show the new run at once; the runs query polls it until it finishes.
        const nextRunIds = [created.id, ...runIds];
        queryClient.setQueryData(runsQueryKey(nextRunIds), [created, ...runs]);
        setEvaluation((prev) => (prev ? { ...prev, run_ids: nextRunIds } : prev));
        setRunsPage(1); // jump back to the first page so the new run is visible
      }
    } catch (error) {
      toast.error(runStartErrorMessage(error));
      // Started elsewhere: reload the evaluation so that run shows up and is polled.
      if (isRunConflict(error)) {
        void getTestEvaluationById(evaluationId).then((fresh) => {
          if (fresh) setEvaluation(fresh);
        });
      }
    } finally {
      setIsStarting(false);
    }
  };

  const openRun = (runId: string | undefined) => {
    if (!runId) return;
    setSelectedRunId(runId);
    setIsRunDetailsOpen(true);
  };

  const selectedRun = runs.find((run) => run.id === selectedRunId);
  const selectedRunResults = selectedRunId ? resultsByRun[selectedRunId] ?? [] : [];
  const selectedRunRuleResults = selectedRunId ? ruleResultsByRun[selectedRunId] ?? [] : [];

  // Turn-level rule results are shown inside the matching test-case detail;
  // conversation results stay in the run-level sections.
  const ruleResultsByCaseId = useMemo(() => {
    const rows = selectedRunId ? ruleResultsByRun[selectedRunId] ?? [] : [];
    const map = new Map<string, TestToolRuleResult[]>();
    for (const ruleResult of rows) {
      if (isTurnScope(ruleResult.scope) && ruleResult.case_id) {
        const existing = map.get(ruleResult.case_id) ?? [];
        existing.push(ruleResult);
        map.set(ruleResult.case_id, existing);
      }
    }
    return map;
  }, [selectedRunId, ruleResultsByRun]);

  // A case's displayed status must reflect its turn-level Tool Usage results too: a
  // tool failure fails the case, and a tool pass can score an otherwise-unscored case.
  const caseTools = (result: TestResult): TestToolRuleResult[] =>
    result.case_id ? ruleResultsByCaseId.get(result.case_id) ?? [] : [];

  const casePassed = (result: TestResult): boolean =>
    caseStatusFor(result, caseTools(result)) === "passed";

  const caseFailed = (result: TestResult): boolean =>
    caseStatusFor(result, caseTools(result)) === "failed";

  const caseNotScored = (result: TestResult): boolean =>
    caseStatusFor(result, caseTools(result)) === "not_scored";

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
  const selectedSummaries = techniqueSummaries(selectedRun);

  // Client-side pagination for the runs list (runs are all loaded up front).
  const runsTotalPages = Math.max(1, Math.ceil(runs.length / RUNS_PAGE_SIZE));
  const runsSafePage = Math.min(runsPage, runsTotalPages);
  const pagedRuns = runs.slice(
    (runsSafePage - 1) * RUNS_PAGE_SIZE,
    runsSafePage * RUNS_PAGE_SIZE,
  );

  // Offered whenever the evaluation targets a workflow; the dialog handles a
  // workflow that has no second version to choose.
  const canRunAgainstVersion = Boolean(workflowAgentId && evaluation?.workflow_id);
  const finishedRunCount = runs.filter(
    (run) => run.status === "completed" || run.status === "failed",
  ).length;

  const lastRunResults = lastRunId ? resultsByRun[lastRunId] : undefined;
  const lastRunTurns =
    lastRunStatus === "completed" && lastRunResults
      ? turnsPassed(lastRunResults, ruleResultsByRun[lastRunId] ?? [])
      : null;
  const lastRunTotals = (lastRun?.summary_metrics as Record<string, unknown> | undefined)?.[
    RUN_TOTALS_KEY
  ] as RunTotals | undefined;

  if (!evaluation) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          className="shrink-0"
          aria-label={backLabel}
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">Evaluation not found</h1>
      </div>
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
    const caseRuleRows = result.case_id ? ruleResultsByCaseId.get(result.case_id) ?? [] : [];
    const caseName = caseLabel(conversationIndex, result.case_id);

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
            <span className="truncate text-sm font-semibold" title={caseName}>
              {caseName}
            </span>
            {notScored && (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700">
                {notScoredLabel(result)}
              </span>
            )}
          </div>
          {result.metrics && (
            <div className="flex flex-wrap justify-end gap-1">
              {Object.entries(result.metrics).map(([tech, metricValue]) => {
                const metricNotScored = metricValue.not_evaluated || metricValue.error;
                return (
                <span
                  key={tech}
                  className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-[10px]",
                    metricNotScored
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400"
                      : metricValue.passed
                        ? "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400"
                        : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400",
                  )}
                >
                  <span className="mr-1 font-semibold">{methodLabel(tech)}</span>
                  {typeof metricValue.score === "number" && (
                    <span>
                      {metricValue.score <= 1
                        ? `${Math.round(metricValue.score * 100)}%`
                        : metricValue.score.toFixed(2)}
                    </span>
                  )}
                </span>
                );
              })}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {/* Metric comments + grading source */}
          {result.metrics && (
            <div className="space-y-1">
              {Object.entries(result.metrics).map(([tech, metricValue]) => {
                const sourceLabel = metricSourceLabel(
                  tech,
                  evaluation?.technique_configs?.[tech],
                );
                const ruleDetails =
                  Array.isArray(metricValue.details) && metricValue.details.length > 1
                    ? metricValue.details
                    : null;
                if (!metricValue.comment && !sourceLabel && !ruleDetails) return null;
                const comment = ruleDetails ? null : metricValue.comment;
                return (
                  <div key={`${result.id}-${tech}-comment`} className="text-xs">
                    <span className="font-semibold text-muted-foreground">{methodLabel(tech)}:</span>{" "}
                    {(comment || sourceLabel) && (
                      <span className="text-muted-foreground">
                        {sourceLabel ? checkedAgainstLine(comment, sourceLabel) : comment}
                      </span>
                    )}
                    {ruleDetails && <MetricRuleBreakdown details={ruleDetails} />}
                  </div>
                );
              })}
            </div>
          )}

          {/* Turn-level rule checks for this case, grouped by technique */}
          {groupByTechnique(caseRuleRows).map(([technique, rows]) => (
            <div key={technique}>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                {methodLabel(technique)}
              </div>
              <div className="space-y-2">
                {rows.map((ruleResult) => (
                  <RuleResultCard
                    key={ruleResult.id}
                    result={ruleResult}
                    labels={conversationIndex}
                  />
                ))}
              </div>
            </div>
          ))}

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
    <>
      {/* Header: back arrow + evaluation name + Run */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          className="shrink-0"
          aria-label={backLabel}
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
        <div className="flex shrink-0 items-center gap-2">
          {canRunAgainstVersion && (
            <TooltipProvider delayDuration={200}>
              <TooltipButton
                button={
                  <Button
                    variant="outline"
                    size="icon"
                    disabled={isRunning}
                    onClick={() => setIsVersionDialogOpen(true)}
                    aria-label="Run against a version"
                  >
                    <GitBranch className="h-4 w-4" />
                  </Button>
                }
                tooltipContent={{ children: <p>Run against a version</p> }}
              />
            </TooltipProvider>
          )}
          <Button
            onClick={() => handleRunEvaluation()}
            disabled={isRunning}
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
                    {methodLabel(technique)}
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
                  {lastRun.workflow_version && (
                    <Badge variant="outline" className="text-[10px]">
                      v{lastRun.workflow_version}
                    </Badge>
                  )}
                  <RunStatusBadge status={lastRun.status} />
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {new Date(lastRun.created_at ?? "").toLocaleString()}
                </div>
              </div>
              {lastRun.status === "failed" ? (
                <div className="text-sm text-red-600 dark:text-red-400">
                  {runFailureText(lastRun)}
                </div>
              ) : lastRun.status === "completed" && !lastRunResults ? (
                <Skeleton className="h-5 w-40" />
              ) : lastRunTurns && lastRunTurns.total === 0 && lastRunTurns.notEvaluated > 0 ? (
                <div className="text-sm text-muted-foreground">
                  No turn could be graded · {lastRunTurns.notEvaluated} not evaluated
                </div>
              ) : lastRunTurns && lastRunTurns.total > 0 ? (
                <div className="flex items-center gap-2">
                  <Progress
                    value={(lastRunTurns.passed / lastRunTurns.total) * 100}
                    className={cn(
                      "h-2 w-40",
                      accuracyBarClass(lastRunTurns.passed / lastRunTurns.total),
                    )}
                  />
                  <span
                    className={cn(
                      "text-sm font-semibold",
                      accuracyTextClass(lastRunTurns.passed / lastRunTurns.total),
                    )}
                  >
                    {lastRunTurns.passed} of {lastRunTurns.total} turns passed
                    {lastRunTurns.notEvaluated > 0 && (
                      <span className="font-normal text-muted-foreground">
                        {" "}
                        · {lastRunTurns.notEvaluated} not evaluated
                      </span>
                    )}
                  </span>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {lastRun.status === "completed"
                    ? "No score"
                    : runProgressText(lastRun) ?? "Not scored yet"}
                </div>
              )}
              {lastRunTotals && (
                <div className="text-xs text-muted-foreground">
                  {lastRunTotals.scored} of {lastRunTotals.cases} turns scored
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
          <div className="flex items-center gap-2">
            {finishedRunCount >= 2 && (
              <Button variant="outline" size="sm" onClick={() => setIsCompareOpen(true)}>
                <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" />
                Compare
              </Button>
            )}
            <Badge variant="secondary" className="text-xs">
              {runs.length} run{runs.length !== 1 ? "s" : ""}
            </Badge>
          </div>
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
              const summaries = techniqueSummaries(run);
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
                      {run.workflow_version && (
                        <Badge variant="outline" className="text-[10px]">
                          v{run.workflow_version}
                        </Badge>
                      )}
                      {avgAccuracy !== null && (
                        <div className="flex items-center gap-1" title={AVG_SCORE_HINT}>
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
                  {run.status === "failed" && (
                    <div className="mt-1 text-xs text-red-600 dark:text-red-400">
                      {runFailureText(run)}
                    </div>
                  )}
                  {summaries.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                      {summaries.map(([tech, summary]) => {
                        const acc = techniqueAccuracy(summary);
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
                            <span className="mr-1 font-semibold">{methodLabel(tech)}</span>
                            <span>{acc !== null ? `${Math.round(acc * 100)}%` : NOT_EVALUATED}</span>
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
        <DialogContent className="flex h-[90vh] max-h-[90vh] w-[95vw] max-w-[1800px] flex-col gap-0 overflow-hidden p-0">
          <DialogHeader className="shrink-0 border-b px-5 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <DialogTitle>Run Details #{selectedRun?.id?.slice(-4)}</DialogTitle>
                {selectedRun?.workflow_version && (
                  <Badge variant="outline" className="text-[10px]">
                    v{selectedRun.workflow_version}
                  </Badge>
                )}
              </div>
              {selectedRun && <RunStatusBadge status={selectedRun.status} />}
            </div>
            {selectedRun?.created_at && (
              <p className="text-xs text-muted-foreground">
                {new Date(selectedRun.created_at).toLocaleString()}
              </p>
            )}
          </DialogHeader>

          {/* Columns: evaluation summary | results list | selected case detail */}
          <div className="min-h-0 flex-1">
            <ResizablePanelGroup
              direction="horizontal"
              autoSaveId="run-details-v2"
              className="h-full"
            >
              {/* Evaluation Summary column */}
              <ResizablePanel defaultSize={24} minSize={18} maxSize={35}>
                <div className="flex h-full flex-col overflow-hidden">
                  <div className="shrink-0 border-b px-4 py-2.5 text-sm font-medium">
                    Evaluation Summary
                  </div>
                  <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
                    {runTotals && runTotals.scored < runTotals.cases && (
                      <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-400">
                        Scores cover {runTotals.scored} of {runTotals.cases} turns
                        {runTotals.execution_failed > 0 &&
                          ` · ${runTotals.execution_failed} failed to execute`}
                        {runTotals.scoring_failed > 0 &&
                          ` · ${runTotals.scoring_failed} ran but failed scoring`}
                        {runTotals.skipped > 0 && ` · ${runTotals.skipped} skipped`}
                      </div>
                    )}
                    {selectedSummaries.length > 0 ? (
                      <div className="grid grid-cols-1 gap-3">
                        {selectedSummaries
                          .filter(([tech]) => tech !== TOOL_USED_TECHNIQUE)
                          .map(([tech, summary]) => {
                            const acc = techniqueAccuracy(summary);
                            return (
                              <div key={tech} className="rounded-lg border bg-card p-3 dark:bg-zinc-900">
                                <div className="mb-2 text-xs font-medium text-muted-foreground">{methodLabel(tech)}</div>
                                {acc !== null ? (
                                  <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                      <span className={cn("text-lg font-semibold", accuracyTextClass(acc))}>
                                        {Math.round(acc * 100)}%
                                      </span>
                                      {typeof summary.cases === "number" && (
                                        <span className="text-xs text-muted-foreground">
                                          {summary.cases} {isRuleTechnique(tech) ? "checks" : "turns"}
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
                                ) : (
                                  <div className="text-sm text-muted-foreground">{NOT_EVALUATED}</div>
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
                    ) : selectedRun?.status === "failed" ? (
                      <div className="text-sm text-red-600 dark:text-red-400">
                        {runFailureText(selectedRun)}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">No metrics available</div>
                    )}
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle withHandle />

              {/* Results list column */}
              <ResizablePanel defaultSize={32} minSize={22}>
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
                    {selectedRunRuleResults.length > 0 && (
                      <RuleResults results={selectedRunRuleResults} labels={conversationIndex} />
                    )}

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
                            ? selectedRun && isRunInProgress(selectedRun)
                              ? "No results yet."
                              : "This run has no results."
                            : resultFilter === "passed"
                              ? "No passed turns."
                              : resultFilter === "not_scored"
                                ? "No unscored turns."
                                : "No failed turns."}
                        </p>
                      </div>
                    ) : (
                      filteredResults.map((result) => {
                        const passed = casePassed(result);
                        const notScored = caseNotScored(result);
                        const isActive = activeCase?.id === result.id;
                        const metricComments = Object.entries(result.metrics ?? {})
                          .filter(([, m]) => m.comment)
                          .map(([tech, m]) => `${methodLabel(tech)}: ${m.comment}`)
                          .join(" | ");
                        let caseStatusLabel = "Passed";
                        if (notScored) caseStatusLabel = notScoredLabel(result);
                        else if (!passed) caseStatusLabel = "Failed";
                        const subtitleText = metricComments || caseStatusLabel;
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
                                  {caseLabel(conversationIndex, result.case_id)}
                                </span>
                              </div>
                            </div>
                            {result.metrics && (
                              <div className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">
                                {subtitleText}
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

              {/* Selected case detail column */}
              <ResizablePanel defaultSize={44} minSize={30}>
                <div className="flex h-full flex-col overflow-hidden">
                  {activeCase ? (
                    renderCaseDetail(activeCase)
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                      <AlertCircle className="mb-3 h-10 w-10 text-muted-foreground/30" />
                      <p className="text-sm text-muted-foreground">
                        {isLoadingResults ? "Loading results..." : "Select a turn to see its details."}
                      </p>
                    </div>
                  )}
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
        </DialogContent>
      </Dialog>

      {canRunAgainstVersion && workflowAgentId && (
        <RunAgainstVersionDialog
          isOpen={isVersionDialogOpen}
          onOpenChange={setIsVersionDialogOpen}
          agentId={workflowAgentId}
          currentWorkflowId={evaluation.workflow_id}
          workflowName={workflowName}
          isStarting={isRunning}
          onRun={(targetWorkflowId) => {
            setIsVersionDialogOpen(false);
            void handleRunEvaluation(targetWorkflowId);
          }}
        />
      )}

      <CompareRunsDialog
        isOpen={isCompareOpen}
        onOpenChange={setIsCompareOpen}
        runs={runs}
        cases={suiteCases}
      />
    </>
  );
};

export default EvaluationDetailPanel;

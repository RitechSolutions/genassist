import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Button } from "@/components/button";
import { ChevronLeft, Pencil, GitCompareArrows, Play } from "lucide-react";
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
import { Skeleton } from "@/components/skeleton";
import { Progress } from "@/components/progress";
import { PaginationBar } from "@/components/PaginationBar";
import { cn } from "@/helpers/utils";
import { RunAgainstVersionDialog } from "./RunAgainstVersionDialog";
import { methodLabel } from "../helpers/methodLabels";
import {
  isRunInProgress,
  checksConversations,
  checksVerdictText,
  numberRuns,
  runAvgAccuracy,
  runGradesTurns,
  runFailureText,
  runInProgressText,
  runName,
  runOpens,
  turnsPassed,
} from "../helpers/runResults";
import { isRunConflict, runStartErrorMessage } from "../helpers/runErrors";
import { CHECKS_TECHNIQUE, checkConversations, leftOutNote, parseChecks } from "../helpers/checks";
import { ChecksDialog } from "./ChecksDialog";
import { CompareConversationView } from "./CompareConversationView";
import { ConversationResultView } from "./ConversationResultView";
import { LeftOutNote } from "./LeftOutNote";
import { CategoryBadge } from "./CategoryBadge";
import { RunCompareView } from "./RunCompareView";
import { RunResultsView } from "./RunResultsView";
import { type RunContext, RunningStatus, VerdictTally } from "./resultsParts";
import { runConversationCounts, tallySlots } from "../helpers/runConversations";
import {
  backFromConversation,
  isComparing,
  type ResultsLocation,
  type ResultsMove,
} from "../helpers/resultsLocation";
import { useEvaluationCatalog } from "../hooks/useEvaluationData";
import { useChecksPreview, withPreview } from "../hooks/useChecksPreview";

const RUNS_PAGE_SIZE = 6;
const RUNNING_POLL_MS = 5000;
const NO_RUNS: TestRun[] = [];
const NO_RUN_IDS: string[] = [];
const AVG_SCORE_HINT = "Avg score: the average of each method's pass rate";

/** Execution counts the backend stores alongside the per-technique metrics. */
const RUN_TOTALS_KEY = "_totals";

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
  /** The run, conversation or comparison open in the evaluation. The standalone page keeps it in the URL. */
  resultsView?: ResultsLocation | null;
  onResultsViewChange?: (view: ResultsLocation | null, move?: ResultsMove) => void;
  /** Opens the editor; without it, the standalone editor page opens. */
  onEditEvaluation?: (evaluationId: string) => void;
  /** Shown inside the workflow's builder, so links stay in it or open apart. */
  embedded?: boolean;
  /** The version Run preselects, such as the one open in the builder; the active one when left out. */
  runVersionId?: string;
}

const accuracyTextClass = (acc: number): string =>
  acc >= 0.9
    ? "text-green-600 dark:text-green-400"
    : acc >= 0.7
      ? "text-amber-600 dark:text-amber-400"
      : "text-red-600 dark:text-red-400";

const accuracyBarClass = (acc: number): string =>
  acc >= 0.9 ? "bg-green-600" : acc >= 0.7 ? "bg-amber-600" : "bg-red-600";

const SummaryItem: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="min-w-0">
    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="mt-1 min-w-0 text-sm">{children}</div>
  </div>
);

/** A run's name, the workflow version it played and when, one to a line. */
const RunFacts: React.FC<{ run: TestRun }> = ({ run }) => (
  <div className="min-w-0 space-y-0.5">
    {/* How the run went, or is going, shows where its results are, not as a badge here. */}
    <div className="font-semibold">{runName(run)}</div>
    {run.workflow_version && (
      <div className="text-xs text-muted-foreground">
        Workflow version: <span className="text-foreground">{run.workflow_version}</span>
      </div>
    )}
    <div className="text-xs text-muted-foreground">
      Ran on: <span className="text-foreground">{new Date(run.created_at ?? "").toLocaleString()}</span>
    </div>
  </div>
);

/**
 * One evaluation: its summary, last run and runs, and the results, conversation and
 * comparison views they open. Shared by the evaluation's page and the workflow
 * builder's Evaluations tab. Renders content only (no page chrome).
 */
export const EvaluationDetailPanel: React.FC<EvaluationDetailPanelProps> = ({
  evaluationId,
  onBack,
  backLabel = "Back",
  onWorkflowResolved,
  resultsView,
  onResultsViewChange,
  onEditEvaluation,
  embedded = false,
  runVersionId,
}) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [ownResultsView, setOwnResultsView] = useState<ResultsLocation | null>(null);
  const view = onResultsViewChange ? resultsView ?? null : ownResultsView;
  const setView = (next: ResultsLocation | null, move?: ResultsMove) =>
    onResultsViewChange ? onResultsViewChange(next, move) : setOwnResultsView(next);
  const topRef = useRef<HTMLDivElement>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [resultsByRun, setResultsByRun] = useState<Record<string, TestResult[]>>({});
  const [ruleResultsByRun, setRuleResultsByRun] = useState<Record<string, TestToolRuleResult[]>>({});
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [workflowName, setWorkflowName] = useState<string>("Dataset default");
  const [workflowAgentId, setWorkflowAgentId] = useState<string | null>(null);
  const [isVersionDialogOpen, setIsVersionDialogOpen] = useState(false);
  const [suiteCases, setSuiteCases] = useState<TestCase[]>([]);
  const [suiteCasesFor, setSuiteCasesFor] = useState<string | null>(null);
  const [suiteCasesFailed, setSuiteCasesFailed] = useState(false);
  const [runsPage, setRunsPage] = useState(1);
  const [showChecks, setShowChecks] = useState(false);
  const [allWorkflows, setAllWorkflows] = useState<WorkflowMinimal[]>([]);

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

  // Report the workflow it runs, its own or else its dataset's, so "back" finds where it is listed
  // (null → unassigned).
  const datasetWorkflowId = suite?.workflow_id ?? null;
  useEffect(() => {
    if (evaluationLoaded) onWorkflowResolved?.(evaluationWorkflowId ?? datasetWorkflowId);
  }, [evaluationLoaded, evaluationWorkflowId, datasetWorkflowId, onWorkflowResolved]);

  useEffect(() => {
    const loadContext = async () => {
      if (!evaluationLoaded) return;
      const [suites, workflows] = await Promise.all([
        listTestSuites(),
        getWorkflowsMinimal(),
      ]);
      setAllWorkflows(workflows ?? []);
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
    const loadCases = async () => {
      if (!evaluation?.suite_id) {
        setSuiteCases([]);
        return;
      }
      setSuiteCasesFailed(false);
      let cases: TestCase[] | null;
      try {
        cases = await listTestCases(evaluation.suite_id);
      } catch {
        setSuiteCasesFailed(true);
        return;
      }
      setSuiteCases(cases ?? []);
      setSuiteCasesFor(evaluation.suite_id);
    };
    loadCases();
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
  const runs = useMemo(
    () => (runIds.length > 0 ? numberRuns(runsData ?? NO_RUNS, runIds) : NO_RUNS),
    [runsData, runIds],
  );
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

  // Runs are sorted newest-first, so the most recent is the summary for the header.
  const lastRun = runs[0];
  const lastRunId = lastRun?.id;
  const lastRunStatus = lastRun?.status;
  // A run that counted its conversations reads by conversation, with no results to load.
  const lastRunCounts = runConversationCounts(lastRun);
  const hasLastRunCounts = Boolean(lastRunCounts);

  // The Last Run card counts turns passed, so it loads the run's results once it completes.
  useEffect(() => {
    if (!lastRunId || lastRunStatus !== "completed" || hasLastRunCounts) return;
    // A failed load falls back to "No score" instead of a skeleton that never resolves.
    loadRunResults(lastRunId, true).catch(() =>
      setResultsByRun((prev) => ({ ...prev, [lastRunId]: prev[lastRunId] ?? [] })),
    );
  }, [lastRunId, lastRunStatus, hasLastRunCounts, loadRunResults]);

  // Each results view opens at its top, with focus on it rather than on the row that opened it.
  useEffect(() => {
    if (!view) return;
    topRef.current?.scrollIntoView({ block: "start" });
    topRef.current?.focus({ preventScroll: true });
  }, [view?.runId, view?.conversation, view?.compareWith]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // The agent's live version, which names the workflow and is what Run preselects outside the builder.
  const evaluationWorkflow = allWorkflows.find((item) => item.id === (evaluation?.workflow_id ?? suite?.workflow_id));
  const liveWorkflow =
    (evaluationWorkflow?.agent_id &&
      allWorkflows.find((item) => item.agent_id === evaluationWorkflow.agent_id && item.is_active_version)) ||
    evaluationWorkflow;
  // Checks are read against the version Run preselects.
  const checksWorkflowId =
    runVersionId ?? liveWorkflow?.id ?? evaluation?.workflow_id ?? suite?.workflow_id ?? undefined;
  const checksCatalog = useEvaluationCatalog(checksWorkflowId, showChecks);
  const previews = useChecksPreview(evaluation ? [evaluation] : []);
  // Older methods show as the checks a run grades them with; saving in the editor keeps them.
  const shownEvaluation = useMemo(() => evaluation && withPreview(evaluation, previews), [evaluation, previews]);
  const parsedChecks = useMemo(() => parseChecks(shownEvaluation?.technique_configs?.checks), [shownEvaluation]);
  const savedChecks = parsedChecks.checks;
  const leftOut = leftOutNote(parsedChecks.olderMethods);


  // The editor is a page of its own, which makes older methods into checks first.
  const openEditor = () => {
    if (!evaluationId) return;
    if (onEditEvaluation) onEditEvaluation(evaluationId);
    else navigate(`/tests/evaluations/${evaluationId}/edit`);
  };
  const datasetConversations = useMemo(() => checkConversations(suiteCases), [suiteCases]);
  const conversationsLoaded = Boolean(evaluation?.suite_id) && suiteCasesFor === evaluation?.suite_id;

  const openRun = (runId: string | undefined) => {
    if (runId) setView({ runId });
  };

  // Opens the comparison with the newest finished run picked, waiting for the second.
  const openComparison = () => {
    const newest = runs.find((run) => run.status === "completed");
    if (newest?.id) setView({ runId: newest.id, compareWith: "" });
  };

  // Client-side pagination for the runs list (runs are all loaded up front).
  const runsTotalPages = Math.max(1, Math.ceil(runs.length / RUNS_PAGE_SIZE));
  const runsSafePage = Math.min(runsPage, runsTotalPages);
  const pagedRuns = runs.slice(
    (runsSafePage - 1) * RUNS_PAGE_SIZE,
    runsSafePage * RUNS_PAGE_SIZE,
  );
  // The runs on screen share verdict slots, so their counts line up.
  const runSlots = tallySlots(pagedRuns.map(runConversationCounts));

  // Run asks for the version when the evaluation targets a workflow; the dialog handles one with no second version.
  const pickVersionOnRun = Boolean(workflowAgentId && evaluation?.workflow_id);
  const completedRunCount = runs.filter((run) => run.status === "completed").length;

  const lastRunResults = lastRunId ? resultsByRun[lastRunId] : undefined;
  const lastRunTurns =
    lastRunStatus === "completed" && lastRunResults
      ? turnsPassed(lastRunResults, ruleResultsByRun[lastRunId] ?? [])
      : null;
  const lastRunTotals = (lastRun?.summary_metrics as Record<string, unknown> | undefined)?.[
    RUN_TOTALS_KEY
  ] as RunTotals | undefined;
  // A run with only checks reads by conversation; turns are not graded one by one.
  const lastRunVerdict = checksConversations(lastRun);
  const verdictFirst = Boolean(lastRunVerdict) && !runGradesTurns(lastRun);
  const verdictGraded = lastRunVerdict ? lastRunVerdict.passed + lastRunVerdict.failed : 0;

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
        {/* Undefined while it loads, null once it could not be found. */}
        {evaluation === undefined ? (
          <Skeleton className="h-8 w-80" />
        ) : (
          <h1 className="text-2xl font-bold tracking-tight">Evaluation not found</h1>
        )}
      </div>
    );
  }

  if (view) {
    const viewRun = runs.find((run) => run.id === view.runId);
    const runId = view.runId;
    // A run is not compared with itself, so that pick waits for another.
    const compareWith = view.compareWith === runId ? "" : view.compareWith;
    // What a run does not carry, for the header of each results page.
    const runContext: RunContext = {
      workflowName: liveWorkflow ? liveWorkflow.agent_name || liveWorkflow.name : undefined,
      workflowAgentId: liveWorkflow?.agent_id ?? undefined,
      datasetName: suite && viewRun?.suite_id === suite.id ? suite.name : undefined,
      embedded,
    };
    let content: React.ReactNode;
    if (!viewRun) {
      content = isLoadingRuns ? (
        <Skeleton className="h-8 w-80" />
      ) : (
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setView(null, { back: true })}
            aria-label={`Back to ${evaluation.name}`}
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <p className="text-sm text-muted-foreground">This run is not part of the evaluation.</p>
        </div>
      );
    } else if (view.conversation && compareWith) {
      const other = runs.find((run) => run.id === compareWith);
      content = other ? (
        <CompareConversationView
          key={view.conversation}
          run={viewRun}
          other={other}
          context={runContext}
          conversationKey={view.conversation}
          onBack={() => setView(backFromConversation(view), { back: true })}
          onNavigate={(conversation) => setView({ ...view, conversation }, { replace: true })}
        />
      ) : (
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => setView({ runId }, { back: true })} aria-label="Back to the run">
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <p className="text-sm text-muted-foreground">The run to compare with is not part of the evaluation.</p>
        </div>
      );
    } else if (view.conversation) {
      content = (
        <ConversationResultView
          key={view.conversation}
          run={viewRun}
          context={runContext}
          conversationKey={view.conversation}
          onBack={() => setView(backFromConversation(view), { back: true })}
          onNavigate={(conversation) => setView({ ...view, conversation }, { replace: true })}
        />
      );
    } else if (isComparing(view)) {
      const other = compareWith ? runs.find((run) => run.id === compareWith) ?? null : null;
      content = (
        <RunCompareView
          run={viewRun}
          other={other}
          runs={runs}
          context={runContext}
          conversations={datasetConversations}
          conversationsReady={conversationsLoaded}
          backLabel={`Back to ${evaluation.name}`}
          onBack={() => setView(null, { back: true })}
          onChangeRuns={(nextRunId, otherId) => setView({ runId: nextRunId, compareWith: otherId }, { replace: true })}
          onOpenConversation={(conversation) => setView({ runId, conversation, compareWith })}
        />
      );
    } else {
      content = (
        <RunResultsView
          run={viewRun}
          context={runContext}
          conversations={datasetConversations}
          conversationsReady={conversationsLoaded}
          backLabel={`Back to ${evaluation.name}`}
          onBack={() => setView(null, { back: true })}
          onOpenConversation={(conversation) => setView({ runId, conversation })}
          onCompare={runs.some((run) => run.id !== runId && run.status === "completed") ? () => setView({ runId, compareWith: "" }) : undefined}
        />
      );
    }
    return (
      <div ref={topRef} tabIndex={-1} className="scroll-mt-16 outline-none">
        {content}
      </div>
    );
  }

  // Methods no check could be read from, as when the preview could not load.
  const olderTechniques = (shownEvaluation ?? evaluation).techniques.filter(
    (technique) => technique !== CHECKS_TECHNIQUE,
  );
  const summaryCard = (
    <div className="rounded-lg border bg-card dark:bg-zinc-900">
      <div className="grid gap-4 p-4 sm:grid-cols-3">
        <SummaryItem label="Workflow">
          {/* Inside the builder the workflow is the one already open. */}
          {liveWorkflow?.agent_id && !embedded ? (
            <Link
              to={`/ai-agents/workflow/${liveWorkflow.agent_id}`}
              className="block truncate font-medium text-primary hover:underline"
            >
              {liveWorkflow.agent_name || liveWorkflow.name}
            </Link>
          ) : liveWorkflow ? (
            <span className="block truncate font-medium">{liveWorkflow.agent_name || liveWorkflow.name}</span>
          ) : (
            <span className="text-muted-foreground">{workflowName}</span>
          )}
        </SummaryItem>
        <SummaryItem label="Dataset">
          {/* From the builder it opens apart, so the builder stays as it was. */}
          <Link
            to={`/tests/datasets/${evaluation.suite_id}`}
            target={embedded ? "_blank" : undefined}
            rel={embedded ? "noreferrer" : undefined}
            className="block truncate font-medium text-primary hover:underline"
          >
            {suite?.name ?? "Its dataset"}
          </Link>
          <span className="text-xs text-muted-foreground">
            {conversationsLoaded
              ? `${datasetConversations.length} conversation${datasetConversations.length === 1 ? "" : "s"}`
              : suiteCasesFailed
                ? "Its conversations could not be loaded."
                : "Loading its conversations…"}
          </span>
        </SummaryItem>
        <SummaryItem label="Checks">
          <span className="font-medium">
            {savedChecks.length} check{savedChecks.length === 1 ? "" : "s"}
          </span>
          {savedChecks.length > 0 && (
            <button
              type="button"
              onClick={() => setShowChecks(true)}
              aria-haspopup="dialog"
              className="ml-2 text-xs font-medium text-primary hover:underline"
            >
              Show
            </button>
          )}
          {olderTechniques.length > 0 && (
            <span className="block text-xs text-muted-foreground">
              Also runs older methods: {olderTechniques.map(methodLabel).join(", ")}
            </span>
          )}
        </SummaryItem>
      </div>
      {/* What the conversion could not make into checks shows until it is seen in the editor. */}
      {leftOut.length > 0 && (
        <div className="border-t p-4">
          <LeftOutNote items={leftOut} />
        </div>
      )}
      <ChecksDialog
        open={showChecks}
        onOpenChange={setShowChecks}
        checks={savedChecks}
        description={`What should and should not happen when ${evaluation.name} runs.`}
        conversations={datasetConversations}
        conversationsReady={conversationsLoaded}
        catalog={checksCatalog}
        actions={
          <Button
            variant="outline"
            onClick={() => {
              setShowChecks(false);
              openEditor();
            }}
            disabled={isRunning}
            icon={<Pencil className="h-4 w-4" />}
          >
            Edit
          </Button>
        }
      />
    </div>
  );

  const lastRunScore = lastRun && (
    lastRun.status === "failed" ? (
      <div className="text-sm text-red-600 dark:text-red-400">
        {runFailureText(lastRun)}
      </div>
    ) : isRunInProgress(lastRun) ? (
      <RunningStatus className="text-sm" iconClassName="h-3.5 w-3.5">
        {runInProgressText(lastRun)}
      </RunningStatus>
    ) : lastRun.status === "completed" && lastRunCounts ? (
      <VerdictTally counts={lastRunCounts} className="text-lg font-semibold" iconClassName="h-5 w-5" slots={runSlots} />
    ) : lastRun.status === "completed" && verdictFirst && lastRunVerdict && verdictGraded > 0 ? (
      <div className="flex items-center gap-2">
        <Progress
          value={(lastRunVerdict.passed / verdictGraded) * 100}
          className="h-2 w-40"
          indicatorClassName={accuracyBarClass(lastRunVerdict.passed / verdictGraded)}
        />
        <span
          className={cn("text-sm font-semibold", accuracyTextClass(lastRunVerdict.passed / verdictGraded))}
        >
          {checksVerdictText(lastRun)}
        </span>
      </div>
    ) : lastRun.status === "completed" && verdictFirst ? (
      <div className="text-sm text-muted-foreground">{checksVerdictText(lastRun)}</div>
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
          className="h-2 w-40"
          indicatorClassName={accuracyBarClass(lastRunTurns.passed / lastRunTurns.total)}
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
      <div className="text-sm text-muted-foreground">No score</div>
    )
  );
  const lastRunNotes = lastRun && (
    <>
      {!verdictFirst && !lastRunCounts && checksVerdictText(lastRun) && (
        <div className="text-xs font-medium">Checks: {checksVerdictText(lastRun)}</div>
      )}
      {lastRunTotals && !verdictFirst && !lastRunCounts && (
        <div className="text-xs text-muted-foreground">
          {lastRunTotals.scored} of {lastRunTotals.cases} turns scored
          {lastRunTotals.execution_failed > 0 &&
            ` · ${lastRunTotals.execution_failed} failed to execute`}
        </div>
      )}
      {lastRunTotals && (verdictFirst || lastRunCounts) && lastRunTotals.execution_failed > 0 && (
        <div className="text-xs text-muted-foreground">
          {lastRunTotals.execution_failed} of {lastRunTotals.cases} turns failed to run
        </div>
      )}
    </>
  );
  // The facts on the left, the result large on the right.
  const lastRunLayout = (
    <>
      {/* A run still going is no last run yet. */}
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {lastRun && isRunInProgress(lastRun) ? "Current Run" : "Last Run"}
      </div>
      {lastRun && !isLoadingRuns ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 space-y-1">
            <RunFacts run={lastRun} />
            {lastRunNotes}
          </div>
          {/* Inset by a run row's border and padding, so its counts sit over theirs. */}
          <div className="flex min-w-0 sm:mr-[13px] sm:max-w-md sm:justify-end sm:text-right">{lastRunScore}</div>
        </div>
      ) : (
        <div className="space-y-2">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-2 w-40" />
        </div>
      )}
    </>
  );

  // Opens the last run on click, like a row in the list.
  // A run still going, or a failed run with no results, says all it has here, so it does not open.
  const lastRunCard =
    lastRun && !isLoadingRuns && runOpens(lastRun) ? (
      <button
        type="button"
        onClick={() => openRun(lastRun.id)}
        className="block w-full rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted dark:bg-zinc-900"
      >
        {lastRunLayout}
      </button>
    ) : (
      <div className="rounded-lg border bg-card p-4 dark:bg-zinc-900">{lastRunLayout}</div>
    );

  const runsCard = (
    <div className="rounded-lg border bg-card p-4 dark:bg-zinc-900">
      <h2 className="mb-3 text-lg font-semibold">All runs</h2>

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
            const counts = runConversationCounts(run);
            const avgAccuracy = counts ? null : runAvgAccuracy(run);
            const opens = runOpens(run);
            const Row = opens ? "button" : "div";
            return (
              <Row
                key={run.id}
                {...(opens ? { type: "button" as const, onClick: () => openRun(run.id) } : {})}
                className={cn(
                  "flex w-full flex-col gap-2 rounded-lg border p-3 text-left sm:flex-row sm:items-center sm:justify-between",
                  opens && "transition-colors hover:bg-muted",
                )}
              >
                <RunFacts run={run} />
                <div className="flex min-w-0 sm:max-w-md sm:justify-end sm:text-right">
                  {run.status === "failed" ? (
                    <span className="text-sm text-red-600 dark:text-red-400">{runFailureText(run)}</span>
                  ) : isRunInProgress(run) ? (
                    <RunningStatus className="text-sm" iconClassName="h-3.5 w-3.5">
                      {runInProgressText(run)}
                    </RunningStatus>
                  ) : counts ? (
                    <VerdictTally
                      counts={counts}
                      className="text-lg font-semibold"
                      iconClassName="h-5 w-5"
                      slots={runSlots}
                    />
                  ) : avgAccuracy !== null ? (
                    <span
                      title={AVG_SCORE_HINT}
                      className={cn("text-lg font-semibold tabular-nums", accuracyTextClass(avgAccuracy))}
                    >
                      {Math.round(avgAccuracy * 100)}%
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground">No score</span>
                  )}
                </div>
              </Row>
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
  );

  return (
    <>
      {/* Header: back arrow + evaluation name + Run; the buttons take their own row on phones. */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-3">
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
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="truncate text-2xl font-bold tracking-tight animate-fade-down">{evaluation.name}</h1>
            {evaluation.category && <CategoryBadge name={evaluation.category} />}
          </div>
          {evaluation.description && (
            <p className="truncate text-sm text-muted-foreground">{evaluation.description}</p>
          )}
        </div>
        <div className="flex w-full shrink-0 flex-wrap items-center justify-end gap-2 sm:w-auto">
          {completedRunCount >= 2 && (
            <Button
              variant="outline"
              onClick={openComparison}
              icon={<GitCompareArrows className="h-4 w-4" />}
            >
              Compare
            </Button>
          )}
          <Button variant="outline" onClick={openEditor} disabled={isRunning} icon={<Pencil className="h-4 w-4" />}>
            Edit
          </Button>
          <Button
            onClick={() => (pickVersionOnRun ? setIsVersionDialogOpen(true) : void handleRunEvaluation())}
            disabled={isRunning}
            aria-label="Run evaluation"
            title={isRunning ? "This evaluation is already running" : undefined}
          >
            {/* The run card below says how the run is going, so the button keeps its name. */}
            <Play className="mr-2 h-4 w-4" />
            Run
          </Button>
        </div>
      </div>

      {summaryCard}
      {/* With no runs, All runs says so on its own. */}
      {(isLoadingRuns || lastRun) && lastRunCard}
      {runsCard}

      {pickVersionOnRun && workflowAgentId && (
        <RunAgainstVersionDialog
          isOpen={isVersionDialogOpen}
          onOpenChange={setIsVersionDialogOpen}
          agentId={workflowAgentId}
          currentWorkflowId={evaluation.workflow_id}
          openWorkflowId={runVersionId}
          asRun={{
            title: "Run evaluation",
            description: (
              <>
                Runs <span className="font-medium text-foreground">{evaluation.name}</span> on the version you pick.
              </>
            ),
          }}
          isStarting={isRunning}
          onRun={(targetWorkflowId) => {
            setIsVersionDialogOpen(false);
            void handleRunEvaluation(targetWorkflowId);
          }}
        />
      )}
    </>
  );
};

export default EvaluationDetailPanel;

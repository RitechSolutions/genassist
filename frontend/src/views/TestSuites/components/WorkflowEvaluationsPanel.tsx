import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, ListChecks, MoreVertical, Play, Plus, Search } from "lucide-react";
import toast from "react-hot-toast";

import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { PaginationBar } from "@/components/PaginationBar";
import { PageListSkeleton } from "@/components/skeletons";
import { TooltipProvider } from "@/components/RadixTooltip";
import { TooltipButton } from "@/components/tooltip-button";
import { cn } from "@/helpers/utils";

import { getWorkflowsMinimal } from "@/services/workflows";
import { getTestRunsBatch } from "@/services/testSuites";
import {
  deleteTestEvaluation,
  exportTestEvaluation,
  exportWorkflowEvaluations,
  getWorkflowEvaluationsPage,
  runTestEvaluation,
  runWorkflowEvaluations,
} from "@/services/testEvaluations";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { TestRun } from "@/interfaces/testSuite.interface";
import { EntityTitle } from "./EntityTitle";
import { useChecksPreview, withPreview } from "../hooks/useChecksPreview";
import { WORKFLOW_SUMMARIES_QUERY_KEY } from "../hooks/useEvaluationData";
import { CATEGORIES_QUERY_KEY } from "../hooks/useCategories";
import { EvaluationListRow } from "./EvaluationListRow";
import { RunningStatus } from "./resultsParts";
import { RunAgainstVersionDialog } from "./RunAgainstVersionDialog";
import { isRunConflict, runStartErrorMessage } from "../helpers/runErrors";
import { runAllStatusText, runAvgAccuracy, runInProgressText } from "../helpers/runResults";
import { runConversationCounts } from "../helpers/runConversations";
import { ALL_CATEGORIES, categoryQuery, runAllScope } from "../helpers/categories";
import {
  apiErrorDetail,
  bundleFilename,
  bundleSetFilename,
  downloadJsonFile,
} from "../helpers/evalBundle";

const PAGE_SIZE = 20;
const UNASSIGNED = "unassigned";
const RUNNING_POLL_MS = 5000;

/** Lists the evaluations page already loaded, so its sections don't load them again. */
export interface EvaluationReferenceData {
  workflows: WorkflowMinimal[];
}

export interface WorkflowEvaluationsPanelProps {
  /** Workflow to scope the list to. Pass "unassigned" for evaluations with no workflow. */
  workflowId: string;
  /** Open an evaluation's detail. In-tab callers swap views; the route wrapper navigates. */
  onOpenEvaluation: (evaluationId: string) => void;
  /**
   * When true, a "New Evaluation" button creates an evaluation pinned to this
   * workflow (used by the in-builder tab). The evaluations page keeps creation in
   * its header, so its sections leave this off.
   */
  allowCreate?: boolean;
  /** "section": one collapsible workflow on the evaluations page, with no search box of its own. */
  variant?: "page" | "section";
  /** Section only: its heading, evaluation count and whether it is open. */
  title?: string;
  count?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Section only: false until the page scrolls near it, so nothing loads before then. */
  load?: boolean;
  /** Section only: the page's search, matched against evaluation names, and how many matched. */
  search?: string;
  matches?: number | null;
  /** Section only: the page's word on running evaluations, for a folded section that loaded nothing. */
  running?: boolean;
  /** Section only: the page's category filter. */
  category?: string;
  reference?: EvaluationReferenceData;
  /** The editor opens through these, as in the builder's tab; without them, its page opens. */
  onCreateEvaluation?: () => void;
  onEditEvaluation?: (evaluationId: string) => void;
  /** The version Run and Run all preselect, such as the one open in the builder; the active one when left out. */
  runVersionId?: string;
}

/**
 * One workflow's evaluations: search, pagination, run, run all, export, edit and
 * delete. Shared by the evaluations page's sections and the workflow builder's
 * Evaluations tab. Renders content only (no page chrome).
 */
export const WorkflowEvaluationsPanel: React.FC<WorkflowEvaluationsPanelProps> = ({
  workflowId,
  onOpenEvaluation,
  allowCreate = false,
  variant = "page",
  title,
  count,
  open = true,
  onOpenChange,
  load = true,
  search: sectionSearch = "",
  matches = null,
  running = false,
  category = ALL_CATEGORIES,
  reference,
  onCreateEvaluation,
  onEditEvaluation,
  runVersionId,
}) => {
  const isUnassigned = workflowId === UNASSIGNED;
  const isSection = variant === "section";
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [ownWorkflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const workflows = reference?.workflows ?? ownWorkflows;

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [ownSearch, setSearch] = useState("");
  // A section is searched from the page, which waits for typing to stop.
  const search = isSection ? sectionSearch : ownSearch;

  const [lastRunsByEvaluationId, setLastRunsByEvaluationId] = useState<
    Record<string, TestRun | null>
  >({});
  const [runningEvalIds, setRunningEvalIds] = useState<Set<string>>(new Set());
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [workflowProgress, setWorkflowProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  // Synchronous guard against a rapid double-click (state updates are async).
  const isRunAllInFlight = useRef(false);
  const runAllPollTimer = useRef<number | null>(null);
  // Bumped whenever the Run-all poll must be abandoned (unmount or workflow switch)
  // so an in-flight poll from a previous context can't apply to the current one.
  const runAllEpoch = useRef(0);
  const isMounted = useRef(true);

  // Set true on setup so React Strict Mode's setup/cleanup/setup cycle leaves it true.
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  // React Router reuses this component across workflows, so when the id changes
  // abandon the previous workflow's Run-all poll and reset its guard/progress —
  // otherwise workflow A's poll could land on workflow B's page.
  useEffect(() => {
    return () => {
      runAllEpoch.current += 1;
      if (runAllPollTimer.current) {
        window.clearTimeout(runAllPollTimer.current);
        runAllPollTimer.current = null;
      }
      isRunAllInFlight.current = false;
      setIsWorkflowRunning(false);
      setWorkflowProgress(null);
    };
  }, [workflowId]);

  const [deletingEvaluationId, setDeletingEvaluationId] = useState<string | null>(null);
  const [isRunAllVersionDialogOpen, setIsRunAllVersionDialogOpen] = useState(false);
  // The evaluation whose Run is asking for the version.
  const [versionRunEvaluation, setVersionRunEvaluation] = useState<TestEvaluationConfig | null>(null);

  // staleTime 0 makes react-query refetch this when the tab regains focus. The
  // interval is the page's only poll: it runs when a batch is active that this
  // session isn't already tracking, and react-query pauses it in a hidden tab.
  // A folded section loads nothing until it is opened.
  const {
    data: pageData = null,
    dataUpdatedAt,
    isPending: isLoading,
    isError: hasError,
    refetch: refetchPage,
  } = useQuery({
    queryKey: ["workflow-evaluations", workflowId, page, search, category],
    queryFn: async () =>
      (await getWorkflowEvaluationsPage(workflowId, {
        page,
        pageSize: PAGE_SIZE,
        search,
        ...categoryQuery(category),
      })) ?? null,
    enabled: !isSection || (open && load),
    staleTime: 0,
    refetchInterval: (query) =>
      query.state.data?.any_running && !isWorkflowRunning ? RUNNING_POLL_MS : false,
  });

  const evaluations = pageData?.items ?? [];
  const total = pageData?.total ?? 0;
  const anyRunning = pageData ? pageData.any_running : running;

  // The page's summaries say how each workflow did, so they follow every change made here;
  // a change that can move an evaluation to another workflow reloads every list.
  const refresh = (everywhere = false) => {
    if (everywhere) void queryClient.invalidateQueries({ queryKey: ["workflow-evaluations"] });
    else void refetchPage();
    void queryClient.invalidateQueries({ queryKey: WORKFLOW_SUMMARIES_QUERY_KEY });
  };

  const previews = useChecksPreview(evaluations);

  // The editor is a page of its own, which makes older methods into checks first.
  const editEvaluation = (evaluation: TestEvaluationConfig) => {
    if (!evaluation.id) return;
    if (onEditEvaluation) onEditEvaluation(evaluation.id);
    else navigate(`/tests/evaluations/${evaluation.id}/edit`);
  };
  const createEvaluation = () => {
    if (onCreateEvaluation) onCreateEvaluation();
    else navigate(`/tests/evaluations/new?workflow=${encodeURIComponent(workflowId)}`);
  };
  const totalUnfiltered = pageData?.total_unfiltered ?? 0;
  const currentWorkflow = workflows.find((w) => w.id === workflowId);
  const workflowName = isUnassigned
    ? "Unassigned evaluations"
    : currentWorkflow?.agent_name || currentWorkflow?.name || "Workflow";
  const workflowAgentId = isUnassigned ? null : currentWorkflow?.agent_id ?? null;
  // Run and Run all ask for the version first, starting from the given one; a workflow with no agent runs directly.
  const pickVersionOnRun = Boolean(workflowAgentId);

  useEffect(() => {
    if (reference) return;
    void getWorkflowsMinimal().then((workflowData) => setWorkflows(workflowData ?? []));
  }, [reference]);

  // Debounce the search box and reset to the first page when it changes.
  useEffect(() => {
    if (isSection) return;
    const timer = window.setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput, isSection]);

  // A section's search and category come from the page, the search already debounced.
  useEffect(() => {
    if (isSection) setPage(1);
  }, [sectionSearch, category, isSection]);

  // Load the latest run for each evaluation on the page.
  useEffect(() => {
    const loadLastRuns = async () => {
      const items = pageData?.items ?? [];
      const runIdToEvalId: Record<string, string> = {};
      items.forEach((evaluation) => {
        const lastRunId = evaluation.run_ids?.[0];
        if (evaluation.id && lastRunId) runIdToEvalId[lastRunId] = evaluation.id;
      });
      const runIds = Object.keys(runIdToEvalId);
      if (!runIds.length) {
        setLastRunsByEvaluationId({});
        return;
      }
      try {
        const runs = await getTestRunsBatch(runIds);
        const mapping: Record<string, TestRun | null> = {};
        (runs ?? []).forEach((run) => {
          const evalId = run.id ? runIdToEvalId[run.id] : undefined;
          if (evalId) mapping[evalId] = run;
        });
        setLastRunsByEvaluationId(mapping);
      } catch {
        setLastRunsByEvaluationId({});
      }
    };
    void loadLastRuns();
    // Keyed on dataUpdatedAt, not pageData: react-query's structural sharing keeps
    // the same object reference when a poll returns identical rows, but run status
    // lives in test_runs — so it must refresh on every fetch, not only on change.
  }, [dataUpdatedAt]);

  const isEvaluationRunning = (evaluation: TestEvaluationConfig): boolean => {
    if (evaluation.id && runningEvalIds.has(evaluation.id)) return true;
    const lastRun = evaluation.id ? lastRunsByEvaluationId[evaluation.id] : null;
    return lastRun?.status === "queued" || lastRun?.status === "running";
  };

  const getAverageAccuracy = (evaluation: TestEvaluationConfig): number | null => {
    const lastRun = evaluation.id ? lastRunsByEvaluationId[evaluation.id] : null;
    return lastRun ? runAvgAccuracy(lastRun) : null;
  };

  const startRun = async (evaluation: TestEvaluationConfig, targetWorkflowId?: string) => {
    if (!evaluation.id || isEvaluationRunning(evaluation)) return;
    setRunningEvalIds((prev) => new Set(prev).add(evaluation.id));
    try {
      const created = await runTestEvaluation(evaluation.id, targetWorkflowId);
      if (created?.id) {
        setLastRunsByEvaluationId((prev) => ({ ...prev, [evaluation.id as string]: created }));
        toast.success("Evaluation started");
        refresh(); // any_running turns on, which starts the status poll
      }
    } catch (error) {
      toast.error(runStartErrorMessage(error));
      if (isRunConflict(error)) refresh();
    } finally {
      setRunningEvalIds((prev) => {
        const next = new Set(prev);
        if (evaluation.id) next.delete(evaluation.id);
        return next;
      });
    }
  };

  const handleQuickRun = (evaluation: TestEvaluationConfig, e: React.MouseEvent) => {
    e.stopPropagation();
    if (pickVersionOnRun) setVersionRunEvaluation(evaluation);
    else void startRun(evaluation);
  };

  const handleRunAll = async (targetWorkflowId?: string) => {
    if (isUnassigned || isRunAllInFlight.current || isWorkflowRunning || anyRunning) {
      return;
    }
    isRunAllInFlight.current = true;
    const epoch = runAllEpoch.current; // invalidated if the workflow changes
    setIsWorkflowRunning(true);
    setWorkflowProgress(null); // real total is known only once runs are started
    const isStale = () => !isMounted.current || epoch !== runAllEpoch.current;
    const finish = () => {
      if (isStale()) return; // don't touch another workflow's guard/progress
      isRunAllInFlight.current = false;
      setIsWorkflowRunning(false);
      refresh(); // settle any_running/health once the batch ends
    };

    try {
      const started = await runWorkflowEvaluations(workflowId, targetWorkflowId, categoryQuery(category));
      if (isStale()) return; // navigated away before the POST resolved
      const startedRuns = (started ?? []).filter(
        (s): s is typeof s & { run_id: string } => Boolean(s.run_id),
      );
      const failedCount = (started ?? []).length - startedRuns.length;
      if (!startedRuns.length) {
        toast.error("No evaluations could be started");
        finish();
        return;
      }
      if (failedCount > 0) {
        toast.error(`${failedCount} evaluation${failedCount !== 1 ? "s" : ""} failed to start`);
      }
      const runIdToEvalId: Record<string, string> = {};
      startedRuns.forEach((s) => {
        runIdToEvalId[s.run_id] = s.evaluation_id;
      });
      const runIds = startedRuns.map((s) => s.run_id);
      // Run all starts every evaluation in the workflow, or in the picked category, not just the filtered page.
      setWorkflowProgress({ done: 0, total: runIds.length });
      toast.success(`Started ${runIds.length} evaluation${runIds.length !== 1 ? "s" : ""}`);
      void queryClient.invalidateQueries({ queryKey: WORKFLOW_SUMMARIES_QUERY_KEY });

      let consecutivePollErrors = 0;
      const maxPollErrors = 5;
      const poll = async () => {
        if (isStale()) return;
        // Don't poll a hidden tab; pick back up on the next tick.
        if (document.visibilityState !== "visible") {
          runAllPollTimer.current = window.setTimeout(poll, RUNNING_POLL_MS);
          return;
        }
        try {
          const runs = await getTestRunsBatch(runIds);
          consecutivePollErrors = 0;
          const updates: Record<string, TestRun> = {};
          let done = 0;
          (runs ?? []).forEach((run) => {
            if (!run?.id) return;
            const evalId = runIdToEvalId[run.id];
            if (evalId) updates[evalId] = run;
            if (run.status === "completed" || run.status === "failed") done += 1;
          });
          if (isStale()) return;
          setLastRunsByEvaluationId((prev) => ({ ...prev, ...updates }));
          setWorkflowProgress({ done, total: runIds.length });
          if (done >= runIds.length) {
            finish();
            return;
          }
        } catch {
          consecutivePollErrors += 1;
          if (consecutivePollErrors >= maxPollErrors) {
            toast.error("Lost track of running evaluations. Refresh to see their status.");
            finish();
            return;
          }
        }
        if (!isStale()) runAllPollTimer.current = window.setTimeout(poll, RUNNING_POLL_MS);
      };
      runAllPollTimer.current = window.setTimeout(poll, 2000);
    } catch (error) {
      if (isStale()) return; // navigated away before the POST rejected
      // A 409 here is about the whole workflow, so it keeps its own message.
      if (isRunConflict(error)) {
        toast.error("This workflow already has running evaluations");
        refresh(); // refetch so any_running blocks the button
      } else {
        toast.error(runStartErrorMessage(error));
      }
      finish();
    }
  };

  const handleExport = async (evaluation: TestEvaluationConfig) => {
    if (!evaluation.id) return;
    try {
      const bundle = await exportTestEvaluation(evaluation.id);
      if (!bundle) {
        toast.error("You don't have permission to export evaluations.");
        return;
      }
      downloadJsonFile(bundleFilename(evaluation.name), bundle);
      toast.success("Evaluation exported");
    } catch {
      toast.error("Failed to export evaluation");
    }
  };

  const handleExportAll = async () => {
    try {
      // Like Run all, it takes the evaluations in the picked category.
      const bundleSet = await exportWorkflowEvaluations(workflowId, categoryQuery(category));
      if (!bundleSet) {
        toast.error("You don't have permission to export evaluations.");
        return;
      }
      downloadJsonFile(bundleSetFilename(title ?? workflowName, categoryQuery(category)), bundleSet);
      const exported = bundleSet.evaluations.length;
      toast.success(`Exported ${exported} evaluation${exported !== 1 ? "s" : ""}`);
    } catch (error) {
      // The backend explains its export limits precisely; a generic message
      // would hide both the limit and how far over it this workflow is.
      toast.error(apiErrorDetail(error) ?? "Failed to export evaluations");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTestEvaluation(id);
    } catch (error) {
      setDeletingEvaluationId(null);
      if (isRunConflict(error)) {
        toast.error("This evaluation is running. Wait for it to finish before deleting.");
        refresh();
      } else {
        toast.error("Failed to delete evaluation");
      }
      return;
    }
    setDeletingEvaluationId(null);
    toast.success("Evaluation deleted");
    // Its category may have been the last one in use.
    void queryClient.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
    if (evaluations.length === 1 && page > 1) {
      setPage((current) => current - 1);
      void queryClient.invalidateQueries({ queryKey: WORKFLOW_SUMMARIES_QUERY_KEY });
    } else {
      refresh();
    }
  };

  const runAllDisabled = isWorkflowRunning || Boolean(anyRunning);
  const runAll = () => (pickVersionOnRun ? setIsRunAllVersionDialogOpen(true) : void handleRunAll());
  const sectionCount = isSection ? count ?? totalUnfiltered : 0;
  // Run all keeps its name; what the evaluations are doing shows beside it, as a row's run shows beside Run.
  const runAllLabel = (
    <>
      <Play className="h-3.5 w-3.5 mr-1" />
      Run all
    </>
  );
  const runAllStatusLabel = runAllStatusText(isWorkflowRunning, workflowProgress, Boolean(anyRunning));
  const runAllStatus = runAllStatusLabel && (
    <RunningStatus className="shrink-0 text-xs">
      {/* Phones keep the room for the name; the spinner still shows, and screen readers still hear it. */}
      <span className="sr-only sm:not-sr-only">{runAllStatusLabel}</span>
    </RunningStatus>
  );

  const listBody = isLoading ? (
    <PageListSkeleton variant="evaluation" bordered={false} />
  ) : hasError ? (
    <div className="py-16 text-center">
      <p className="text-sm text-muted-foreground mb-3">Couldn't load evaluations.</p>
      <Button variant="outline" onClick={() => void refetchPage()}>
        Retry
      </Button>
    </div>
  ) : evaluations.length === 0 ? (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <div className="rounded-full bg-muted p-4">
        <ListChecks className="h-10 w-10 text-muted-foreground" />
      </div>
      <p className="text-sm text-muted-foreground max-w-sm">
        {category !== ALL_CATEGORIES
          ? "No evaluations match your search or category."
          : search
            ? "No evaluations match your search."
            : allowCreate && !isUnassigned
              ? "This workflow has no evaluations yet. Create your first one to get started."
              : isSection
                ? "This workflow has no evaluations yet."
                : "This workflow has no evaluations yet. Create one from the Evaluations overview."}
      </p>
      {!search && allowCreate && !isUnassigned && (
        <Button onClick={createEvaluation}>
          <Plus className="h-4 w-4 mr-2" />
          New Evaluation
        </Button>
      )}
    </div>
  ) : (
    <div className="divide-y divide-border">
      {evaluations.map((evaluation) => (
        <EvaluationListRow
          key={evaluation.id}
          evaluation={withPreview(evaluation, previews)}
          avgAccuracy={getAverageAccuracy(evaluation)}
          conversations={evaluation.id ? runConversationCounts(lastRunsByEvaluationId[evaluation.id]) : null}
          isRunning={isEvaluationRunning(evaluation)}
          indent={isSection}
          lastRunStatus={
            evaluation.id ? lastRunsByEvaluationId[evaluation.id]?.status : undefined
          }
          runningText={runInProgressText(evaluation.id ? lastRunsByEvaluationId[evaluation.id] : null)}
          onOpen={() => evaluation.id && onOpenEvaluation(evaluation.id)}
          onEdit={() => void editEvaluation(evaluation)}
          onExport={() => void handleExport(evaluation)}
          onDelete={() => setDeletingEvaluationId(evaluation.id ?? null)}
          onRun={(e) => handleQuickRun(evaluation, e)}
        />
      ))}
    </div>
  );

  const pagination = !isLoading && !hasError && total > PAGE_SIZE && (
    <PaginationBar
      total={total}
      currentPage={page}
      pageSize={PAGE_SIZE}
      pageItemCount={evaluations.length}
      onPageChange={setPage}
      className={isSection ? "border-t px-4 py-3" : "mt-4"}
    />
  );

  return (
    <>
      {isSection ? (
        <section className="overflow-hidden rounded-lg border bg-card dark:bg-zinc-900">
          {/* Anywhere on the header folds the section; the button's click reaches it. */}
          <div className="flex cursor-pointer items-center gap-3 px-4 py-3" onClick={() => onOpenChange?.(!open)}>
            <button
              type="button"
              aria-expanded={open}
              className="flex min-w-0 flex-1 items-center gap-3 text-left"
            >
              <ChevronDown
                className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", !open && "-rotate-90")}
              />
              <EntityTitle level="group" muted={isUnassigned} className="w-auto shrink">
                {title ?? workflowName}
              </EntityTitle>
              {/* Phones keep the room for the name. */}
              <Badge variant="secondary" className="hidden shrink-0 sm:inline-flex">
                {search
                  ? `${pageData ? total : matches ?? 0} of ${sectionCount} match`
                  : `${sectionCount} evaluation${sectionCount !== 1 ? "s" : ""}`}
              </Badge>
            </button>
            {!isUnassigned && runAllStatus}
            {!isUnassigned && (
              // Run all and the menu act on their own instead of folding the section.
              <div className="flex shrink-0 items-center gap-1" onClick={(event) => event.stopPropagation()}>
                <Button variant="outline" size="sm" disabled={runAllDisabled} onClick={runAll}>
                  {runAllLabel}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`More actions for ${title ?? workflowName}`}>
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => void handleExportAll()}>
                      <Download className="h-4 w-4 mr-2" />
                      Export all
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}
          </div>
          {open && (
            <div className="border-t">
              {listBody}
              {pagination}
            </div>
          )}
        </section>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-2xl font-bold tracking-tight truncate animate-fade-down">
                {workflowName}
              </h1>
              <Badge variant="secondary" className="shrink-0">
                {search
                  ? `Showing ${total} of ${totalUnfiltered}`
                  : `${total} evaluation${total !== 1 ? "s" : ""}`}
              </Badge>
            </div>
            {/* Wraps on narrow screens, as Run all's status can make it wider than the header. */}
            <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
              <div className="relative w-56">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Search evaluations..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              {!isUnassigned && (
                <div className="flex items-center gap-2">
                  <TooltipProvider delayDuration={200}>
                    <TooltipButton
                      button={
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => void handleExportAll()}
                          aria-label="Export all evaluations"
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      }
                      tooltipContent={{ children: <p>Export all evaluations</p> }}
                    />
                  </TooltipProvider>
                  {runAllStatus}
                  <Button variant="outline" disabled={runAllDisabled} onClick={runAll}>
                    {runAllLabel}
                  </Button>
                </div>
              )}
              {allowCreate && !isUnassigned && (
                <Button onClick={createEvaluation}>
                  <Plus className="h-4 w-4 mr-1" />
                  New Evaluation
                </Button>
              )}
            </div>
          </div>

          <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">{listBody}</div>

          {pagination}
        </>
      )}

      {workflowAgentId && (
        <RunAgainstVersionDialog
          isOpen={isRunAllVersionDialogOpen}
          onOpenChange={setIsRunAllVersionDialogOpen}
          agentId={workflowAgentId}
          currentWorkflowId={workflowId}
          openWorkflowId={runVersionId}
          confirmLabel="Run all"
          asRun={{
            title: "Run all evaluations",
            description: `Runs ${runAllScope(category, title ?? workflowName)} on the version you pick.`,
          }}
          isStarting={isWorkflowRunning}
          onRun={(targetWorkflowId) => {
            setIsRunAllVersionDialogOpen(false);
            void handleRunAll(targetWorkflowId);
          }}
        />
      )}

      {workflowAgentId && versionRunEvaluation && (
        <RunAgainstVersionDialog
          isOpen
          onOpenChange={(isOpen) => {
            if (!isOpen) setVersionRunEvaluation(null);
          }}
          agentId={workflowAgentId}
          currentWorkflowId={versionRunEvaluation.workflow_id ?? workflowId}
          openWorkflowId={runVersionId}
          asRun={{
            title: "Run evaluation",
            description: (
              <>
                Runs <span className="font-medium text-foreground">{versionRunEvaluation.name}</span> on the version
                you pick.
              </>
            ),
          }}
          onRun={(targetWorkflowId) => {
            const evaluation = versionRunEvaluation;
            setVersionRunEvaluation(null);
            void startRun(evaluation, targetWorkflowId);
          }}
        />
      )}

      <Dialog
        open={!!deletingEvaluationId}
        onOpenChange={(isOpen) => {
          if (!isOpen) setDeletingEvaluationId(null);
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Evaluation</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete this evaluation? This will also permanently delete all
            associated runs and their results. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingEvaluationId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deletingEvaluationId && handleDelete(deletingEvaluationId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default WorkflowEvaluationsPanel;

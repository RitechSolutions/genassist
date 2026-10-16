import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ListChecks, Loader2, Plus, Upload } from "lucide-react";

import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { PageListSkeleton } from "@/components/skeletons";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { getWorkflowsMinimal } from "@/services/workflows";
import { listTestSuites } from "@/services/testSuites";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import {
  createTestEvaluation,
  getWorkflowEvaluationSummaries,
  runTestEvaluation,
} from "@/services/testEvaluations";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { TestSuite } from "@/interfaces/testSuite.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { EvaluationWizard, EvaluationWizardData } from "../components/EvaluationWizard";
import { WorkflowEvaluationsPanel } from "../components/WorkflowEvaluationsPanel";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import { FeatureFlags } from "@/config/featureFlags";
import toast from "react-hot-toast";
import { runStartErrorMessage } from "../helpers/runErrors";
import { ImportEvaluationDialog } from "../components/ImportEvaluationDialog";
import { EntityTitle } from "../components/EntityTitle";
import { buildTechniqueConfigs, wizardMetadata } from "../helpers/evaluationForm";
import { accuracyColorClass } from "../helpers/evaluationMetrics";
import { WORKFLOW_SUMMARIES_QUERY_KEY } from "../hooks/useEvaluationData";
import { planSections, sectionKeyFor } from "../helpers/evaluationSections";

const UNASSIGNED = "unassigned";
const RUNNING_POLL_MS = 5000;
// Which workflows the person opened or folded, kept in this browser only.
const OPENED_KEY = "genassist.evaluations.openedWorkflows";

interface WorkflowRow {
  key: string;
  workflowId: string | null;
  name: string;
  count: number;
  health: number | null;
  finishedCount: number;
  anyRunning: boolean;
  isUnassigned: boolean;
}

// Rows are named after the agent, matching Agent Studio and the workflow picker.
// Two versions of one agent would then read identically, so those keep a version.
const nameRows = (rows: WorkflowRow[], workflows: WorkflowMinimal[]): WorkflowRow[] => {
  const counts = new Map<string, number>();
  rows.forEach((row) => counts.set(row.name, (counts.get(row.name) ?? 0) + 1));

  return rows.map((row) => {
    if ((counts.get(row.name) ?? 0) < 2) return row;
    const version = workflows.find((w) => w.id === row.workflowId)?.version;
    return version ? { ...row, name: `${row.name} · v${version}` } : row;
  });
};

const readOpened = (): Record<string, boolean> => {
  try {
    const stored: unknown = JSON.parse(window.localStorage.getItem(OPENED_KEY) ?? "{}");
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) return {};
    return Object.fromEntries(
      Object.entries(stored).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean"),
    );
  } catch {
    return {};
  }
};

const saveOpened = (opened: Record<string, boolean>) => {
  try {
    window.localStorage.setItem(OPENED_KEY, JSON.stringify(opened));
  } catch {
    // Folding is a convenience, so a browser that keeps nothing is fine.
  }
};

const sectionId = (key: string) => `workflow-evaluations-${key}`;

/** Renders its section once it comes near the screen, so a long page loads as it is scrolled. */
const NearScreen: React.FC<{ id: string; className?: string; children: (near: boolean) => React.ReactNode }> = ({
  id,
  className,
  children,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    const element = ref.current;
    if (near || !element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setNear(true);
      },
      { rootMargin: "300px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);
  return (
    <div ref={ref} id={id} className={className}>
      {children(near)}
    </div>
  );
};

const EvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [providers, setProviders] = useState<LLMProviderMinimal[]>([]);
  const [isReferenceLoading, setIsReferenceLoading] = useState(true);
  const [hasReferenceError, setHasReferenceError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const checksEnabled = useFeatureFlagVisible(FeatureFlags.EVALUATIONS.CHECKS);
  const { hydrated: flagsLoaded } = useFeatureFlag();
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [opened, setOpened] = useState<Record<string, boolean>>(readOpened);
  const query = useDebouncedValue(searchQuery.trim(), 300);
  // Folding during a search lasts for that search only.
  const [foldedInSearch, setFoldedInSearch] = useState<{ query: string; keys: Set<string> }>({
    query: "",
    keys: new Set(),
  });
  const focusWorkflow = searchParams.get("workflow");

  // Summaries carry the live health and running state. staleTime 0 makes
  // react-query refetch them when the tab regains focus; the interval only runs
  // while a batch is active and react-query pauses it in a hidden tab.
  const {
    data: summaries = [],
    isPending: isSummariesLoading,
    isError: hasSummariesError,
    refetch: refetchSummaries,
  } = useQuery({
    queryKey: WORKFLOW_SUMMARIES_QUERY_KEY,
    queryFn: async () => (await getWorkflowEvaluationSummaries()) ?? [],
    staleTime: 0,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((summary) => summary.any_running)
        ? RUNNING_POLL_MS
        : false,
  });

  // One request finds the workflows with matching evaluations, instead of one per section.
  const matching = useQuery({
    queryKey: [...WORKFLOW_SUMMARIES_QUERY_KEY, "search", query],
    queryFn: async () => (await getWorkflowEvaluationSummaries(query)) ?? [],
    enabled: checksEnabled && Boolean(query),
    staleTime: 0,
  });
  const matches = useMemo(() => {
    if (!query) return null;
    // A failed search falls back to the workflow names.
    if (matching.isError) return new Map<string, number>();
    if (!matching.data) return null;
    return new Map(matching.data.map((summary) => [summary.workflow_id ?? UNASSIGNED, summary.eval_count]));
  }, [query, matching.data, matching.isError]);

  // The page waits for the flags, so the old list never flashes before the new one.
  const isLoading = isSummariesLoading || isReferenceLoading || !flagsLoaded;
  const hasError = hasSummariesError || hasReferenceError;

  const loadReference = useCallback(async () => {
    const [workflowData, suiteData, providersData] = await Promise.all([
      getWorkflowsMinimal(),
      listTestSuites(),
      getLLMProvidersMinimal(),
    ]);
    return {
      workflows: workflowData ?? [],
      suites: suiteData ?? [],
      providers: (providersData ?? []).filter((p) => p.is_active === 1),
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsReferenceLoading(true);
      setHasReferenceError(false);
      try {
        const loaded = await loadReference();
        if (cancelled) return;
        setWorkflows(loaded.workflows);
        setSuites(loaded.suites);
        setProviders(loaded.providers);
      } catch {
        if (!cancelled) setHasReferenceError(true);
      } finally {
        if (!cancelled) setIsReferenceLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey, loadReference]);

  // An import can add datasets and evaluations to any workflow, so everything is read again quietly.
  const afterImport = () => {
    void queryClient.invalidateQueries({ queryKey: WORKFLOW_SUMMARIES_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: ["workflow-evaluations"] });
    loadReference()
      .then((loaded) => {
        setWorkflows(loaded.workflows);
        setSuites(loaded.suites);
        setProviders(loaded.providers);
      })
      .catch(() => undefined);
  };

  const reference = useMemo(() => ({ workflows, suites, providers }), [workflows, suites, providers]);

  const allRows = useMemo<WorkflowRow[]>(() => {
    const nameFor = (workflowId: string | null): string => {
      if (workflowId === null) return "Unassigned evaluations";
      const workflow = workflows.find((w) => w.id === workflowId);
      if (!workflow) return "Unknown workflow";
      return workflow.agent_name || workflow.name;
    };
    const named = nameRows(
      summaries.map((summary) => ({
        key: summary.workflow_id ?? UNASSIGNED,
        workflowId: summary.workflow_id,
        name: nameFor(summary.workflow_id),
        count: summary.eval_count,
        health: summary.health,
        finishedCount: summary.finished_count,
        anyRunning: summary.any_running,
        isUnassigned: summary.workflow_id === null,
      })),
      workflows,
    );
    return named.sort((a, b) => {
      if (a.isUnassigned) return 1;
      if (b.isUnassigned) return -1;
      return a.name.localeCompare(b.name);
    });
  }, [summaries, workflows]);

  // The older list matches workflow names only.
  const rows = useMemo(() => {
    const lowered = searchQuery.trim().toLowerCase();
    return allRows.filter((row) => !lowered || row.name.toLowerCase().includes(lowered));
  }, [allRows, searchQuery]);

  // Folds are kept by agent, so a newly activated version keeps its workflow's fold.
  const foldKey = useCallback(
    (rowKey: string) => {
      const workflowId = allRows.find((row) => row.key === rowKey)?.workflowId;
      return workflows.find((workflow) => workflow.id === workflowId)?.agent_id ?? rowKey;
    },
    [allRows, workflows],
  );
  const openedRows = useMemo(
    () =>
      Object.fromEntries(
        allRows.flatMap((row) => (opened[foldKey(row.key)] === undefined ? [] : [[row.key, opened[foldKey(row.key)]]])),
      ) as Record<string, boolean>,
    [allRows, opened, foldKey],
  );
  const setOpen = useCallback(
    (rowKey: string, open: boolean) => {
      const key = foldKey(rowKey);
      setOpened((previous) => {
        if (previous[key] === open) return previous;
        const next = { ...previous, [key]: open };
        saveOpened(next);
        return next;
      });
    },
    [foldKey],
  );

  const keysFoldedInSearch = foldedInSearch.query === query ? foldedInSearch.keys : new Set<string>();
  const setOpenInSearch = (key: string, open: boolean) => {
    const next = new Set(keysFoldedInSearch);
    if (open) next.delete(key);
    else next.add(key);
    setFoldedInSearch({ query, keys: next });
  };

  // Back from an evaluation opens its workflow here and brings it into view, found through its agent.
  useEffect(() => {
    if (!focusWorkflow || isLoading || !checksEnabled) return;
    const key = sectionKeyFor(focusWorkflow, allRows, workflows);
    if (key) {
      setOpen(key, true);
      window.requestAnimationFrame(() => document.getElementById(sectionId(key))?.scrollIntoView({ block: "start" }));
    }
    setSearchParams(
      (params) => {
        params.delete("workflow");
        return params;
      },
      { replace: true },
    );
  }, [focusWorkflow, isLoading, checksEnabled, allRows, workflows, setOpen, setSearchParams]);

  // With checks on, a new evaluation is made on its own page.
  const startCreating = () => (checksEnabled ? navigate("/tests/evaluations/new") : setIsCreateDialogOpen(true));

  const openWorkflow = (row: WorkflowRow) => {
    navigate(`/tests/evaluations/workflows/${row.workflowId ?? UNASSIGNED}`);
  };

  const handleCreate = async (data: EvaluationWizardData, options?: { run?: boolean }) => {
    const created = await createTestEvaluation({
      name: data.name.trim(),
      description: data.description.trim() || undefined,
      suite_id: data.suiteId,
      workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
      techniques: data.metrics,
      technique_configs: buildTechniqueConfigs(data),
      input_metadata: wizardMetadata(data),
    });
    if (!created) return;
    setIsCreateDialogOpen(false);
    if (options?.run && created.id) {
      try {
        await runTestEvaluation(created.id);
        toast.success("Evaluation started");
      } catch (error) {
        toast.error(runStartErrorMessage(error));
      }
    }
    navigate(`/tests/evaluations/${created.id}`);
  };

  const renderRow = (row: WorkflowRow) => {
    const healthTooltip = row.anyRunning
      ? row.health !== null
        ? "Evaluations running. The avg score shown is from the previous completed runs."
        : "Evaluations are running…"
      : row.health !== null
        ? `Avg score: the average of each method's pass rate, across ${row.finishedCount} of ${
            row.count
          } evaluation${row.count !== 1 ? "s" : ""}. Failed runs count as 0%.`
        : "No evaluations scored yet";
    return (
      <tr
        key={row.key}
        onClick={() => openWorkflow(row)}
        className="hover:bg-muted transition-colors cursor-pointer"
      >
        <td className="px-6 py-4">
          <div className="flex items-center gap-2 min-w-0">
            <EntityTitle muted={row.isUnassigned}>{row.name}</EntityTitle>
          </div>
        </td>
        <td className="px-6 py-4">
          <div className="flex items-center gap-1.5" title={healthTooltip}>
            {row.anyRunning ? (
              <Loader2 className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 animate-spin" />
            ) : (
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            {row.health !== null ? (
              <span className={cn("font-medium", accuracyColorClass(row.health))}>
                {Math.round(row.health * 100)}%
              </span>
            ) : row.anyRunning ? (
              <span className="text-blue-600 dark:text-blue-400">Running…</span>
            ) : (
              <span className="text-muted-foreground">No scores yet</span>
            )}
          </div>
        </td>
        <td className="px-6 py-4">
          <Badge variant="secondary">
            {row.count} eval{row.count !== 1 ? "s" : ""}
          </Badge>
        </td>
      </tr>
    );
  };

  const { sections, searching } = planSections(allRows, query, matches, openedRows, keysFoldedInSearch);

  const emptyState = (message: string, create: boolean) => (
    <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
      <div className="rounded-full bg-muted p-4">
        <ListChecks className="h-12 w-12 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-lg">No evaluations yet</h3>
      <p className="text-sm text-muted-foreground max-w-sm">{message}</p>
      {create && (
        <Button onClick={startCreating}>
          <Plus className="h-4 w-4 mr-2" />
          Create your first evaluation
        </Button>
      )}
    </div>
  );

  const errorState = (
    <div className="py-16 text-center">
      <p className="text-sm text-muted-foreground mb-3">Couldn't load evaluations.</p>
      <Button
        variant="outline"
        onClick={() => {
          setReloadKey((key) => key + 1);
          void refetchSummaries();
        }}
      >
        Retry
      </Button>
    </div>
  );

  const firstUse =
    "Evaluations help you test your AI agents against golden datasets. Create your first evaluation to get started.";

  return (
    <PageLayout>
      <PageHeader
        title="Evaluations"
        subtitle={
          checksEnabled
            ? "Your evaluations, grouped by workflow."
            : "Grouped by workflow. Open a workflow to view and run its evaluations."
        }
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder={checksEnabled ? "Search evaluations..." : "Search workflows..."}
        actionButtonText="New Evaluation"
        onActionClick={startCreating}
        secondaryActionButtonText={
          <>
            <Upload className="w-4 h-4" />
            Import
          </>
        }
        onSecondaryActionClick={() => setIsImportDialogOpen(true)}
      />

      {checksEnabled && !isLoading && !hasError && allRows.length > 0 ? (
        <div className="space-y-4">
          {sections.map(({ row, search, open, matches: matched }) => (
            <NearScreen key={row.key} id={sectionId(row.key)} className="scroll-mt-4">
              {(near) => (
                <WorkflowEvaluationsPanel
                  variant="section"
                  workflowId={row.workflowId ?? UNASSIGNED}
                  title={row.name}
                  count={row.count}
                  matches={matched}
                  open={open}
                  load={near}
                  onOpenChange={(next) => (query ? setOpenInSearch(row.key, next) : setOpen(row.key, next))}
                  search={search}
                  running={row.anyRunning}
                  reference={reference}
                  onOpenEvaluation={(evaluationId) => navigate(`/tests/evaluations/${evaluationId}`)}
                />
              )}
            </NearScreen>
          ))}
          {searching && sections.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">Searching…</p>
          )}
          {!searching && sections.length === 0 && (
            <div className="rounded-lg border bg-card py-12 text-center text-sm text-muted-foreground dark:bg-zinc-900">
              No workflows or evaluations match your search.
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
          {isLoading ? (
            <PageListSkeleton variant="evaluation" bordered={false} />
          ) : hasError ? (
            errorState
          ) : checksEnabled ? (
            emptyState(firstUse, true)
          ) : rows.length === 0 ? (
            emptyState(searchQuery ? "No workflows match your search." : firstUse, !searchQuery)
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted text-left text-xs font-medium text-muted-foreground">
                    <th className="px-6 py-3 font-medium">Workflow</th>
                    <th className="px-6 py-3 font-medium">Avg score</th>
                    <th className="px-6 py-3 font-medium">Evaluations</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">{rows.map(renderRow)}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!checksEnabled && (
        <EvaluationWizard
          isOpen={isCreateDialogOpen}
          onOpenChange={setIsCreateDialogOpen}
          onSubmit={handleCreate}
          suites={suites}
          workflows={workflows}
          providers={providers}
          mode="create"
        />
      )}

      <ImportEvaluationDialog
        isOpen={isImportDialogOpen}
        onOpenChange={setIsImportDialogOpen}
        workflows={workflows}
        onImported={(result) => {
          afterImport();
          navigate(`/tests/evaluations/${result.evaluation_id}`);
        }}
        onSetImported={afterImport}
      />
    </PageLayout>
  );
};

export default EvaluationsPage;

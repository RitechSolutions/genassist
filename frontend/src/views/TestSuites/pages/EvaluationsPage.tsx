import React, {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {PageLayout} from "@/components/PageLayout";
import {PageHeader} from "@/components/PageHeader";
import {getAllWorkflows} from "@/services/workflows";
import {getTestRun, listTestSuites, startTestRun} from "@/services/testSuites";
import {Workflow} from "@/interfaces/workflow.interface";
import {TestRun, TestSuite} from "@/interfaces/testSuite.interface";
import {Button} from "@/components/button";
import {Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,} from "@/components/ui/dialog";
import {ListChecks, Pencil, Play, Plus, Trash2} from "lucide-react";
import {
  appendRunToEvaluation,
  createTestEvaluation,
  deleteTestEvaluation,
  listTestEvaluations,
  updateTestEvaluation,
} from "@/services/testEvaluations";
import {TestEvaluationConfig} from "@/interfaces/testEvaluation.interface";
import {getAllLLMProviders} from "@/services/llmProviders";
import {LLMProvider} from "@/interfaces/llmProvider.interface";
import {Skeleton} from "@/components/skeleton";
import {Progress} from "@/components/progress";
import {Badge} from "@/components/badge";
import {EvaluationWizard, EvaluationWizardData} from "../components/EvaluationWizard";
import toast from "react-hot-toast";

const EvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [evaluations, setEvaluations] = useState<TestEvaluationConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [runningEvalIds, setRunningEvalIds] = useState<Set<string>>(new Set());
  const [lastRunsByEvaluationId, setLastRunsByEvaluationId] = useState<
    Record<string, TestRun | null>
  >({});
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingEvaluation, setEditingEvaluation] = useState<TestEvaluationConfig | null>(null);
  const [deletingEvaluationId, setDeletingEvaluationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const [suiteData, workflowData, providersData] = await Promise.all([
          listTestSuites(),
          getAllWorkflows(),
          getAllLLMProviders(),
        ]);
        setSuites(suiteData ?? []);
        setWorkflows(workflowData ?? []);
        const activeProviders = (providersData ?? []).filter((p) => p.is_active === 1);
        setProviders(activeProviders);
        const evaluationData = await listTestEvaluations();
        setEvaluations(evaluationData ?? []);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    const loadLastRuns = async () => {
      if (!evaluations.length) {
        setLastRunsByEvaluationId({});
        return;
      }
      const pairs = await Promise.all(
        evaluations.map(async (evaluation) => {
          const evalId = evaluation.id;
          const lastRunId = evaluation.run_ids[0];
          if (!evalId || !lastRunId) return [evalId ?? "", null] as const;
          try {
            const run = await getTestRun(lastRunId);
            return [evalId, run] as const;
          } catch {
            return [evalId, null] as const;
          }
        }),
      );
      const mapping: Record<string, TestRun | null> = {};
      pairs.forEach(([id, run]) => {
        if (id) mapping[id] = run;
      });
      setLastRunsByEvaluationId(mapping);
    };
    void loadLastRuns();
  }, [evaluations]);

  const handleDeleteEvaluation = async (id: string) => {
    await deleteTestEvaluation(id);
    setEvaluations((prev) => prev.filter((e) => e.id !== id));
    setDeletingEvaluationId(null);
  };

  const getEditInitialData = (evaluation: TestEvaluationConfig): Partial<EvaluationWizardData> => {
    const nliCfg = evaluation.technique_configs?.["nli_eval"] as Record<string, unknown> | undefined;
    const provCfg = evaluation.technique_configs?.["provenance_eval"] as Record<string, unknown> | undefined;
    const metaWithoutMemory = evaluation.input_metadata
      ? Object.fromEntries(Object.entries(evaluation.input_metadata).filter(([k]) => k !== "use_memory"))
      : {};

    return {
      name: evaluation.name,
      description: evaluation.description ?? "",
      suiteId: evaluation.suite_id,
      workflowId: evaluation.workflow_id ?? "none",
      metrics: evaluation.techniques,
      inputMetadataText: JSON.stringify(metaWithoutMemory, null, 2),
      useMemory: Boolean(evaluation.input_metadata?.use_memory),
      nliModelName: (nliCfg?.nli_model_name as string) ?? "cross-encoder/nli-deberta-v3-base",
      nliMinEntailScore: String(nliCfg?.min_entail_score ?? "0.5"),
      nliFailOnContradiction: Boolean(nliCfg?.fail_on_contradiction),
      provMode: (provCfg?.provenance_mode as "embeddings" | "llm") ?? "embeddings",
      provEmbeddingType: (provCfg?.embedding_type as "openai" | "huggingface" | "bedrock") ?? "huggingface",
      provEmbeddingModelName: (provCfg?.embedding_model_name as string) ?? "all-MiniLM-L6-v2",
      provMinScore: String(provCfg?.min_score ?? "0.5"),
      provFailOnViolation: Boolean(provCfg?.fail_on_violation),
      provLlmProviderId: (provCfg?.llm_provider_id as string) ?? providers[0]?.id ?? "",
      provLlmJudgeSystemPromptSuffix: (provCfg?.llm_judge_system_prompt_suffix as string) ?? "",
    };
  };

  const handleEditWizardSubmit = async (data: EvaluationWizardData) => {
    if (!editingEvaluation?.id) return;

    let parsedMetadata: Record<string, unknown> | undefined;
    try {
      const parsed = JSON.parse(data.inputMetadataText || "{}");
      parsedMetadata = parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : undefined;
    } catch {
      parsedMetadata = undefined;
    }
    if (data.useMemory) {
      parsedMetadata = { ...(parsedMetadata ?? {}), use_memory: true };
    } else if (parsedMetadata) {
      delete parsedMetadata["use_memory"];
    }

    const updated = await updateTestEvaluation(editingEvaluation.id, {
      name: data.name.trim(),
      description: data.description.trim() || undefined,
      suite_id: data.suiteId,
      workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
      techniques: data.metrics,
      technique_configs: {
        ...(data.metrics.includes("nli_eval")
          ? {
              nli_eval: {
                min_entail_score: Number(data.nliMinEntailScore || "0.5"),
                fail_on_contradiction: data.nliFailOnContradiction,
                ...(data.nliModelName.trim() ? { nli_model_name: data.nliModelName.trim() } : {}),
              },
            }
          : {}),
        ...(data.metrics.includes("provenance_eval")
          ? {
              provenance_eval: {
                min_score: Number(data.provMinScore || "0.5"),
                fail_on_violation: data.provFailOnViolation,
                use_llm_judge: data.provMode === "llm",
                ...(data.provMode === "llm" && data.provLlmProviderId.trim()
                  ? { llm_provider_id: data.provLlmProviderId.trim() }
                  : {}),
                ...(data.provMode === "llm" && data.provLlmJudgeSystemPromptSuffix.trim()
                  ? { llm_judge_system_prompt_suffix: data.provLlmJudgeSystemPromptSuffix.trim() }
                  : {}),
                ...(data.provMode === "embeddings"
                  ? {
                      embedding_type: data.provEmbeddingType,
                      embedding_model_name: data.provEmbeddingModelName.trim() || undefined,
                    }
                  : {}),
                provenance_mode: data.provMode,
              },
            }
          : {}),
      },
      input_metadata: parsedMetadata,
    });

    if (!updated) return;
    setEvaluations((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    setEditingEvaluation(null);
    toast.success("Evaluation updated successfully");
  };

  const handleQuickRun = async (evaluation: TestEvaluationConfig, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!evaluation.id) return;

    setRunningEvalIds((prev) => new Set(prev).add(evaluation.id));
    try {
      let runMetadata = evaluation.input_metadata ?? undefined;
      if (runMetadata?.use_memory) {
        runMetadata = { ...runMetadata, thread_id: crypto.randomUUID() };
      }
      const created = await startTestRun(evaluation.suite_id, {
        techniques: evaluation.techniques,
        technique_configs: evaluation.technique_configs,
        workflow_id: evaluation.workflow_id,
        input_metadata: runMetadata,
      });
      if (created?.id) {
        await appendRunToEvaluation(evaluation.id, created.id);
        // Update the last run for this evaluation
        setLastRunsByEvaluationId((prev) => ({ ...prev, [evaluation.id]: created }));
        toast.success("Evaluation started successfully");
        navigate(`/tests/evaluations/${evaluation.id}`);
      }
    } catch (err) {
      toast.error("Failed to start evaluation");
    } finally {
      setRunningEvalIds((prev) => {
        const next = new Set(prev);
        next.delete(evaluation.id);
        return next;
      });
    }
  };

  const handleWizardSubmit = async (data: EvaluationWizardData) => {
    let parsedMetadata: Record<string, unknown> | undefined;
    try {
      const parsed = JSON.parse(data.inputMetadataText || "{}");
      parsedMetadata =
        parsed && typeof parsed === "object"
          ? (parsed as Record<string, unknown>)
          : undefined;
    } catch {
      parsedMetadata = undefined;
    }
    if (data.useMemory) {
      parsedMetadata = { ...(parsedMetadata ?? {}), use_memory: true };
    } else if (parsedMetadata) {
      delete parsedMetadata["use_memory"];
    }

    const created = await createTestEvaluation({
      name: data.name.trim(),
      description: data.description.trim() || undefined,
      suite_id: data.suiteId,
      workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
      techniques: data.metrics,
      technique_configs: {
        ...(data.metrics.includes("nli_eval")
          ? {
              nli_eval: {
                min_entail_score: Number(data.nliMinEntailScore || "0.5"),
                fail_on_contradiction: data.nliFailOnContradiction,
                ...(data.nliModelName.trim()
                  ? { nli_model_name: data.nliModelName.trim() }
                  : {}),
              },
            }
          : {}),
        ...(data.metrics.includes("provenance_eval")
          ? {
              provenance_eval: {
                min_score: Number(data.provMinScore || "0.5"),
                fail_on_violation: data.provFailOnViolation,
                use_llm_judge: data.provMode === "llm",
                ...(data.provMode === "llm" && data.provLlmProviderId.trim()
                  ? { llm_provider_id: data.provLlmProviderId.trim() }
                  : {}),
                ...(data.provMode === "llm" && data.provLlmJudgeSystemPromptSuffix.trim()
                  ? { llm_judge_system_prompt_suffix: data.provLlmJudgeSystemPromptSuffix.trim() }
                  : {}),
                ...(data.provMode === "embeddings"
                  ? {
                      embedding_type: data.provEmbeddingType,
                      embedding_model_name: data.provEmbeddingModelName.trim() || undefined,
                    }
                  : {}),
                provenance_mode: data.provMode,
              },
            }
          : {}),
      },
      input_metadata: parsedMetadata,
    });
    if (!created) return;
    setIsCreateDialogOpen(false);
    navigate(`/tests/evaluations/${created.id}`);
  };

  const getAverageAccuracy = (evaluation: TestEvaluationConfig): number | null => {
    if (!evaluation.id) return null;
    const lastRun = lastRunsByEvaluationId[evaluation.id];
    if (!lastRun?.summary_metrics) return null;

    const metrics = lastRun.summary_metrics as Record<
      string,
      { accuracy?: number; avg_score?: number; cases?: number }
    >;
    const accuracies = Object.values(metrics)
      .map((m) => m.accuracy)
      .filter((a): a is number => typeof a === "number");

    if (accuracies.length === 0) return null;
    return accuracies.reduce((sum, a) => sum + a, 0) / accuracies.length;
  };

  const filteredEvaluations = evaluations.filter((evaluation) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;
    return (
      evaluation.name.toLowerCase().includes(query) ||
      (evaluation.description ?? "").toLowerCase().includes(query)
    );
  });

  return (
    <PageLayout>
      <PageHeader
        title="Evaluations"
        subtitle="Create and execute evaluations by linking dataset, workflow, metadata, and metrics."
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search evaluations..."
        actionButtonText="New Evaluation"
        onActionClick={() => setIsCreateDialogOpen(true)}
      />

      <div className="rounded-lg border bg-white overflow-hidden">
        {isLoading ? (
          <div className="divide-y divide-gray-100">
            {[1, 2, 3].map((i) => (
              <div key={i} className="py-4 px-6">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-4 w-64" />
                    <div className="flex items-center gap-2 mt-2">
                      <Skeleton className="h-2 w-32 rounded-full" />
                      <Skeleton className="h-4 w-16" />
                    </div>
                    <div className="flex gap-1 mt-2">
                      <Skeleton className="h-5 w-20 rounded-full" />
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-8 w-8 rounded" />
                    <Skeleton className="h-8 w-8 rounded" />
                    <Skeleton className="h-8 w-20 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredEvaluations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <ListChecks className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">No evaluations yet</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              {searchQuery
                ? "No evaluations match your search. Try adjusting your query."
                : "Evaluations help you test your AI agents against golden datasets. Create your first evaluation to get started."}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create your first evaluation
              </Button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredEvaluations.map((evaluation) => {
              const avgAccuracy = getAverageAccuracy(evaluation);
              const isRunning = evaluation.id ? runningEvalIds.has(evaluation.id) : false;

              return (
                <div
                  key={evaluation.id}
                  className="w-full py-4 px-6 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-4">
                    <button
                      type="button"
                      onClick={() => navigate(`/tests/evaluations/${evaluation.id}`)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="flex items-center gap-2">
                        <div className="text-lg font-semibold truncate">
                          {evaluation.name}
                        </div>
                        <Badge variant="secondary" className="shrink-0 text-[10px] px-1.5">
                          EVAL
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                        {evaluation.description || "No description"}
                      </p>

                      {/* Accuracy progress bar */}
                      {avgAccuracy !== null && (
                        <div className="flex items-center gap-2 mt-2">
                          <Progress
                            value={avgAccuracy * 100}
                            className="h-2 w-32 bg-gray-100"
                          />
                          <span
                            className={`text-xs font-medium ${
                              avgAccuracy >= 0.9
                                ? "text-green-600"
                                : avgAccuracy >= 0.7
                                ? "text-amber-600"
                                : "text-red-600"
                            }`}
                          >
                            {Math.round(avgAccuracy * 100)}% accuracy
                          </span>
                          <span className="text-xs text-gray-400">
                            ({evaluation.run_ids.length} run{evaluation.run_ids.length !== 1 ? "s" : ""})
                          </span>
                        </div>
                      )}

                      {/* Metrics badges */}
                      <div className="flex flex-wrap items-center gap-1 mt-2">
                        <span className="text-xs text-gray-500 mr-1">Metrics:</span>
                        {evaluation.techniques.map((tech) => (
                          <Badge key={tech} variant="outline" className="text-[10px] px-1.5 py-0">
                            {tech}
                          </Badge>
                        ))}
                      </div>
                    </button>

                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        aria-label="Edit evaluation"
                        onClick={() => setEditingEvaluation(evaluation)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        aria-label="Delete evaluation"
                        onClick={() => setDeletingEvaluationId(evaluation.id ?? null)}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                      <Button
                        size="sm"
                        className="ml-1"
                        disabled={isRunning}
                        onClick={(e) => handleQuickRun(evaluation, e)}
                      >
                        <Play className="h-3.5 w-3.5 mr-1" />
                        {isRunning ? "Running..." : "Run"}
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Edit Wizard */}
      {editingEvaluation && (
        <EvaluationWizard
          isOpen={!!editingEvaluation}
          onOpenChange={(open) => { if (!open) setEditingEvaluation(null); }}
          onSubmit={handleEditWizardSubmit}
          suites={suites}
          workflows={workflows}
          providers={providers}
          mode="edit"
          initialData={getEditInitialData(editingEvaluation)}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingEvaluationId} onOpenChange={(open) => { if (!open) setDeletingEvaluationId(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Evaluation</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            Are you sure you want to delete this evaluation? This will also permanently delete all
            associated runs and their results. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingEvaluationId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deletingEvaluationId && handleDeleteEvaluation(deletingEvaluationId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <EvaluationWizard
        isOpen={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onSubmit={handleWizardSubmit}
        suites={suites}
        workflows={workflows}
        providers={providers}
        mode="create"
      />
    </PageLayout>
  );
};

export default EvaluationsPage;


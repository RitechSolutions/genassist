import React, {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {PageLayout} from "@/components/PageLayout";
import {PageHeader} from "@/components/PageHeader";
import {getAllWorkflows} from "@/services/workflows";
import {getTestRun, listTestSuites} from "@/services/testSuites";
import {Workflow} from "@/interfaces/workflow.interface";
import {TestRun, TestSuite} from "@/interfaces/testSuite.interface";
import {Label} from "@/components/label";
import {Checkbox} from "@/components/checkbox";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue,} from "@/components/select";
import {Button} from "@/components/button";
import {Input} from "@/components/input";
import {Textarea} from "@/components/textarea";
import {Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,} from "@/components/ui/dialog";
import {ListChecks, Pencil, Trash2} from "lucide-react";
import {Switch} from "@/components/switch";
import {
  createTestEvaluation,
  deleteTestEvaluation,
  listTestEvaluations,
  updateTestEvaluation,
} from "@/services/testEvaluations";
import {TestEvaluationConfig} from "@/interfaces/testEvaluation.interface";
import {getAllLLMProviders} from "@/services/llmProviders";
import {LLMProvider} from "@/interfaces/llmProvider.interface";

const METRICS = [
  "exact_match",
  "contains",
  "json_match",
  "nli_eval",
  "provenance_eval",
];

const NLI_MODEL_OPTIONS = [
  {
    value: "cross-encoder/nli-deberta-v3-base",
    label: "DeBERTa v3 Base (NLI)",
  },
  {
    value: "cross-encoder/nli-roberta-base",
    label: "RoBERTa Base (NLI)",
  },
];

const EvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [evaluations, setEvaluations] = useState<TestEvaluationConfig[]>([]);
  const [lastRunsByEvaluationId, setLastRunsByEvaluationId] = useState<
    Record<string, TestRun | null>
  >({});
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingEvaluation, setEditingEvaluation] = useState<TestEvaluationConfig | null>(null);
  const [deletingEvaluationId, setDeletingEvaluationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [evaluationName, setEvaluationName] = useState("");
  const [evaluationDescription, setEvaluationDescription] = useState("");
  const [selectedSuiteId, setSelectedSuiteId] = useState<string>("none");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("none");
  const [metrics, setMetrics] = useState<string[]>(["exact_match"]);
  const [inputMetadataText, setInputMetadataText] = useState("{}");
  const [useMemory, setUseMemory] = useState(false);
  const [nliModelName, setNliModelName] = useState(
    "cross-encoder/nli-deberta-v3-base",
  );
  const [nliMinEntailScore, setNliMinEntailScore] = useState("0.5");
  const [nliFailOnContradiction, setNliFailOnContradiction] = useState(false);
  const [provMode, setProvMode] = useState<"embeddings" | "llm">("embeddings");
  const [provEmbeddingType, setProvEmbeddingType] = useState<
    "openai" | "huggingface" | "bedrock"
  >("huggingface");
  const [provEmbeddingModelName, setProvEmbeddingModelName] = useState(
    "all-MiniLM-L6-v2",
  );
  const [provMinScore, setProvMinScore] = useState("0.5");
  const [provFailOnViolation, setProvFailOnViolation] = useState(false);
  const [provLlmProviderId, setProvLlmProviderId] = useState("");
  const [provLlmJudgeSystemPromptSuffix, setProvLlmJudgeSystemPromptSuffix] = useState("");

  useEffect(() => {
    const load = async () => {
      const [suiteData, workflowData, providersData] = await Promise.all([
        listTestSuites(),
        getAllWorkflows(),
        getAllLLMProviders(),
      ]);
      setSuites(suiteData ?? []);
      setWorkflows(workflowData ?? []);
      const activeProviders = (providersData ?? []).filter((p) => p.is_active === 1);
      setProviders(activeProviders);
      if (activeProviders[0]?.id) {
        setProvLlmProviderId(activeProviders[0].id);
      }
      const evaluationData = await listTestEvaluations();
      setEvaluations(evaluationData ?? []);
      if (suiteData?.[0]?.id) setSelectedSuiteId(suiteData[0].id);
      if (workflowData?.[0]?.id) setSelectedWorkflowId(workflowData[0].id);
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

  const handleCreateEvaluation = async () => {
    if (!evaluationName.trim() || selectedSuiteId === "none" || metrics.length === 0) {
      return;
    }

    let parsedMetadata: Record<string, unknown> | undefined;
    try {
      const parsed = JSON.parse(inputMetadataText || "{}");
      parsedMetadata =
        parsed && typeof parsed === "object"
          ? (parsed as Record<string, unknown>)
          : undefined;
    } catch {
      parsedMetadata = undefined;
    }
    if (useMemory) {
      parsedMetadata = { ...(parsedMetadata ?? {}), use_memory: true };
    } else if (parsedMetadata) {
      delete parsedMetadata["use_memory"];
    }

    const created = await createTestEvaluation({
      name: evaluationName.trim(),
      description: evaluationDescription.trim() || undefined,
      suite_id: selectedSuiteId,
      workflow_id: selectedWorkflowId === "none" ? undefined : selectedWorkflowId,
      techniques: metrics,
      technique_configs: {
        ...(metrics.includes("nli_eval")
          ? {
              nli_eval: {
                min_entail_score: Number(nliMinEntailScore || "0.5"),
                fail_on_contradiction: nliFailOnContradiction,
                ...(nliModelName.trim()
                  ? { nli_model_name: nliModelName.trim() }
                  : {}),
              },
            }
          : {}),
        ...(metrics.includes("provenance_eval")
          ? {
              provenance_eval: {
                min_score: Number(provMinScore || "0.5"),
                fail_on_violation: provFailOnViolation,
                use_llm_judge: provMode === "llm",
                ...(provMode === "llm" && provLlmProviderId.trim()
                  ? { llm_provider_id: provLlmProviderId.trim() }
                  : {}),
                ...(provMode === "llm" && provLlmJudgeSystemPromptSuffix.trim()
                  ? { llm_judge_system_prompt_suffix: provLlmJudgeSystemPromptSuffix.trim() }
                  : {}),
                ...(provMode === "embeddings"
                  ? {
                      embedding_type: provEmbeddingType,
                      embedding_model_name: provEmbeddingModelName.trim() || undefined,
                    }
                  : {}),
                provenance_mode: provMode,
              },
            }
          : {}),
      },
      input_metadata: parsedMetadata,
    });
    if (!created) return;
    setIsCreateDialogOpen(false);
    setEvaluationName("");
    setEvaluationDescription("");
    setInputMetadataText("{}");
    setUseMemory(false);
    navigate(`/tests/evaluations/${created.id}`);
  };

  const openEditDialog = (evaluation: TestEvaluationConfig) => {
    setEditingEvaluation(evaluation);
    setEvaluationName(evaluation.name);
    setEvaluationDescription(evaluation.description ?? "");
    setSelectedSuiteId(evaluation.suite_id);
    setSelectedWorkflowId(evaluation.workflow_id ?? "none");
    setMetrics(evaluation.techniques);
    const metaWithoutMemory = evaluation.input_metadata
      ? Object.fromEntries(Object.entries(evaluation.input_metadata).filter(([k]) => k !== "use_memory"))
      : {};
    setInputMetadataText(JSON.stringify(metaWithoutMemory, null, 2));
    setUseMemory(Boolean(evaluation.input_metadata?.use_memory));
    const nliCfg = evaluation.technique_configs?.["nli_eval"] as Record<string, unknown> | undefined;
    if (nliCfg) {
      setNliModelName((nliCfg.nli_model_name as string) ?? "cross-encoder/nli-deberta-v3-base");
      setNliMinEntailScore(String(nliCfg.min_entail_score ?? "0.5"));
      setNliFailOnContradiction(Boolean(nliCfg.fail_on_contradiction));
    }
    const provCfg = evaluation.technique_configs?.["provenance_eval"] as Record<string, unknown> | undefined;
    if (provCfg) {
      setProvMode((provCfg.provenance_mode as "embeddings" | "llm") ?? "embeddings");
      setProvMinScore(String(provCfg.min_score ?? "0.5"));
      setProvFailOnViolation(Boolean(provCfg.fail_on_violation));
      setProvEmbeddingType((provCfg.embedding_type as "openai" | "huggingface" | "bedrock") ?? "huggingface");
      setProvEmbeddingModelName((provCfg.embedding_model_name as string) ?? "all-MiniLM-L6-v2");
      setProvLlmProviderId((provCfg.llm_provider_id as string) ?? "");
      setProvLlmJudgeSystemPromptSuffix((provCfg.llm_judge_system_prompt_suffix as string) ?? "");
    }
  };

  const closeEditDialog = () => {
    setEditingEvaluation(null);
    setEvaluationName("");
    setEvaluationDescription("");
    setInputMetadataText("{}");
    setUseMemory(false);
  };

  const handleUpdateEvaluation = async () => {
    if (!editingEvaluation?.id || !evaluationName.trim() || selectedSuiteId === "none" || metrics.length === 0) return;

    let parsedMetadata: Record<string, unknown> | undefined;
    try {
      const parsed = JSON.parse(inputMetadataText || "{}");
      parsedMetadata = parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : undefined;
    } catch {
      parsedMetadata = undefined;
    }
    if (useMemory) {
      parsedMetadata = { ...(parsedMetadata ?? {}), use_memory: true };
    } else if (parsedMetadata) {
      delete parsedMetadata["use_memory"];
    }

    const updated = await updateTestEvaluation(editingEvaluation.id, {
      name: evaluationName.trim(),
      description: evaluationDescription.trim() || undefined,
      suite_id: selectedSuiteId,
      workflow_id: selectedWorkflowId === "none" ? undefined : selectedWorkflowId,
      techniques: metrics,
      technique_configs: {
        ...(metrics.includes("nli_eval")
          ? {
              nli_eval: {
                min_entail_score: Number(nliMinEntailScore || "0.5"),
                fail_on_contradiction: nliFailOnContradiction,
                ...(nliModelName.trim() ? { nli_model_name: nliModelName.trim() } : {}),
              },
            }
          : {}),
        ...(metrics.includes("provenance_eval")
          ? {
              provenance_eval: {
                min_score: Number(provMinScore || "0.5"),
                fail_on_violation: provFailOnViolation,
                use_llm_judge: provMode === "llm",
                ...(provMode === "llm" && provLlmProviderId.trim() ? { llm_provider_id: provLlmProviderId.trim() } : {}),
                ...(provMode === "llm" && provLlmJudgeSystemPromptSuffix.trim()
                  ? { llm_judge_system_prompt_suffix: provLlmJudgeSystemPromptSuffix.trim() }
                  : {}),
                ...(provMode === "embeddings"
                  ? { embedding_type: provEmbeddingType, embedding_model_name: provEmbeddingModelName.trim() || undefined }
                  : {}),
                provenance_mode: provMode,
              },
            }
          : {}),
      },
      input_metadata: parsedMetadata,
    });
    if (!updated) return;
    setEvaluations((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    closeEditDialog();
  };

  const handleDeleteEvaluation = async (id: string) => {
    await deleteTestEvaluation(id);
    setEvaluations((prev) => prev.filter((e) => e.id !== id));
    setDeletingEvaluationId(null);
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
          {filteredEvaluations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
              <ListChecks className="h-12 w-12 text-gray-400" />
              <h3 className="font-medium text-lg">No evaluations found</h3>
              <p className="text-sm text-gray-500 max-w-sm">
                {searchQuery ? "Try adjusting your search query or " : ""}
                create your first evaluation.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredEvaluations.map((evaluation) => (
                <div
                  key={evaluation.id}
                  className="w-full py-4 px-6 text-left hover:bg-gray-50 transition-colors flex items-center gap-3"
                >
                  <button
                    type="button"
                    onClick={() => navigate(`/tests/evaluations/${evaluation.id}`)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-lg font-semibold truncate">
                          {evaluation.name}
                        </div>
                        <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                          {evaluation.description || "No description"}
                        </p>
                        <div className="text-xs text-gray-500 mt-1">
                          Metrics: {evaluation.techniques.join(", ")} | Runs:{" "}
                          {evaluation.run_ids.length}
                        </div>
                        {evaluation.id &&
                          lastRunsByEvaluationId[evaluation.id] &&
                          lastRunsByEvaluationId[evaluation.id]?.summary_metrics && (
                            <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-gray-600">
                              {Object.entries(
                                lastRunsByEvaluationId[evaluation.id]!
                                  .summary_metrics as Record<
                                  string,
                                  { accuracy?: number; avg_score?: number; cases?: number }
                                >,
                              ).map(([tech, summary]) => (
                                <span
                                  key={tech}
                                  className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5"
                                >
                                  <span className="font-semibold mr-1">
                                    {tech}
                                  </span>
                                  {typeof summary.accuracy === "number" && (
                                    <span>
                                      {Math.round(summary.accuracy * 100)}%
                                    </span>
                                  )}
                                </span>
                              ))}
                            </div>
                          )}
                      </div>
                      <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                        EVAL
                      </span>
                    </div>
                  </button>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEditDialog(evaluation)}
                      title="Edit evaluation"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeletingEvaluationId(evaluation.id ?? null)}
                      title="Delete evaluation"
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={!!editingEvaluation} onOpenChange={(open) => { if (!open) closeEditDialog(); }}>
        <DialogContent className="w-[95vw] max-w-xl h-[90vh] max-h-[90vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Edit Evaluation</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            <Label className="text-xs">Evaluation name</Label>
            <Input
              value={evaluationName}
              onChange={(e) => setEvaluationName(e.target.value)}
              placeholder="e.g. FAQ assistant regression"
            />
            <Label className="text-xs">Description</Label>
            <Textarea
              value={evaluationDescription}
              onChange={(e) => setEvaluationDescription(e.target.value)}
              rows={2}
            />
            <Label className="text-xs">Dataset</Label>
            <Select value={selectedSuiteId} onValueChange={setSelectedSuiteId}>
              <SelectTrigger>
                <SelectValue placeholder="Select dataset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Select dataset</SelectItem>
                {suites
                  .filter((s): s is TestSuite & { id: string } => Boolean(s.id))
                  .map((suite) => (
                    <SelectItem key={suite.id} value={suite.id}>
                      {suite.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Label className="text-xs">Workflow version to evaluate</Label>
            <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
              <SelectTrigger>
                <SelectValue placeholder="Select workflow version" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Use dataset default workflow</SelectItem>
                {workflows
                  .filter((wf): wf is Workflow & { id: string } => Boolean(wf.id))
                  .map((wf) => (
                    <SelectItem key={wf.id} value={wf.id}>
                      {wf.name} (v{wf.version})
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Label className="text-xs">Extra metadata (JSON)</Label>
            <Textarea
              value={inputMetadataText}
              onChange={(e) => setInputMetadataText(e.target.value)}
              className="font-mono text-xs"
              rows={4}
            />
            <div className="flex items-center justify-between rounded-md border px-3 py-2 mt-1">
              <div>
                <div className="text-xs font-medium">Use memory</div>
                <div className="text-xs text-gray-400">Generates a unique thread ID per run so the workflow remembers previous inputs/outputs</div>
              </div>
              <Switch checked={useMemory} onCheckedChange={setUseMemory} />
            </div>
            <Label className="text-xs">Validation methods</Label>
            <div className="space-y-2">
              {METRICS.map((metric) => (
                <div key={metric} className="flex items-center space-x-2">
                  <Checkbox
                    id={`metric-${metric}`}
                    checked={metrics.includes(metric)}
                    onCheckedChange={(checked) => {
                      setMetrics((prev) =>
                        checked
                          ? [...prev, metric]
                          : prev.filter((m) => m !== metric),
                      );
                    }}
                  />
                  <Label
                    htmlFor={`metric-${metric}`}
                    className="text-xs font-normal cursor-pointer"
                  >
                    {metric}
                  </Label>
                </div>
              ))}
            </div>

            {metrics.includes("nli_eval") && (
              <div className="border rounded-md p-3 space-y-2">
                <div className="text-xs font-semibold">Guardrail NLI Config</div>
                <Label className="text-xs">NLI model</Label>
                <Select value={nliModelName} onValueChange={setNliModelName}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select NLI model" />
                  </SelectTrigger>
                  <SelectContent>
                    {NLI_MODEL_OPTIONS.map((model) => (
                      <SelectItem key={model.value} value={model.value}>
                        {model.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Label className="text-xs">Min entailment score (0-1)</Label>
                <Input value={nliMinEntailScore} onChange={(e) => setNliMinEntailScore(e.target.value)} />
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="nli-fail-on-contradiction"
                    checked={nliFailOnContradiction}
                    onCheckedChange={(checked) => setNliFailOnContradiction(Boolean(checked))}
                  />
                  <Label htmlFor="nli-fail-on-contradiction" className="text-xs font-normal cursor-pointer">
                    Fail on contradiction
                  </Label>
                </div>
              </div>
            )}

            {metrics.includes("provenance_eval") && (
              <div className="border rounded-md p-3 space-y-2">
                <div className="text-xs font-semibold">Guardrail Provenance Config</div>
                <Label className="text-xs">Provenance mode</Label>
                <Select
                  value={provMode}
                  onValueChange={(value: "embeddings" | "llm") => setProvMode(value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="embeddings">Provenance (Embeddings)</SelectItem>
                    <SelectItem value="llm">Provenance (LLM judge)</SelectItem>
                  </SelectContent>
                </Select>
                <Label className="text-xs">Min score (0-1)</Label>
                <Input value={provMinScore} onChange={(e) => setProvMinScore(e.target.value)} />
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="prov-fail-on-violation"
                    checked={provFailOnViolation}
                    onCheckedChange={(checked) => setProvFailOnViolation(Boolean(checked))}
                  />
                  <Label htmlFor="prov-fail-on-violation" className="text-xs font-normal cursor-pointer">
                    Fail on violation
                  </Label>
                </div>
                {provMode === "embeddings" && (
                  <>
                    <Label className="text-xs">Embedding provider</Label>
                    <Select
                      value={provEmbeddingType}
                      onValueChange={(value: "openai" | "huggingface" | "bedrock") => setProvEmbeddingType(value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select embedding provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="huggingface">HuggingFace</SelectItem>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                      </SelectContent>
                    </Select>
                    <Label className="text-xs">Embedding model name</Label>
                    <Input
                      value={provEmbeddingModelName}
                      onChange={(e) => setProvEmbeddingModelName(e.target.value)}
                      placeholder="all-MiniLM-L6-v2"
                    />
                  </>
                )}
                {provMode === "llm" && (
                  <>
                    <Label className="text-xs">LLM Provider</Label>
                    <Select value={provLlmProviderId} onValueChange={setProvLlmProviderId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Label className="text-xs">Additional judge instructions</Label>
                    <Textarea
                      value={provLlmJudgeSystemPromptSuffix}
                      onChange={(e) => setProvLlmJudgeSystemPromptSuffix(e.target.value)}
                      placeholder="Optional extra instructions for the judge..."
                      rows={4}
                    />
                  </>
                )}
              </div>
            )}
          </div>
          <DialogFooter className="border-t px-6 py-4 shrink-0">
            <Button variant="outline" onClick={closeEditDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleUpdateEvaluation}
              disabled={!evaluationName.trim() || selectedSuiteId === "none" || metrics.length === 0}
            >
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="w-[95vw] max-w-xl h-[90vh] max-h-[90vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Create Evaluation</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            <Label className="text-xs">Evaluation name</Label>
            <Input
              value={evaluationName}
              onChange={(e) => setEvaluationName(e.target.value)}
              placeholder="e.g. FAQ assistant regression"
            />
            <Label className="text-xs">Description</Label>
            <Textarea
              value={evaluationDescription}
              onChange={(e) => setEvaluationDescription(e.target.value)}
              rows={2}
            />
            <Label className="text-xs">Dataset</Label>
            <Select value={selectedSuiteId} onValueChange={setSelectedSuiteId}>
              <SelectTrigger>
                <SelectValue placeholder="Select dataset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Select dataset</SelectItem>
                {suites
                  .filter((s): s is TestSuite & { id: string } => Boolean(s.id))
                  .map((suite) => (
                    <SelectItem key={suite.id} value={suite.id}>
                      {suite.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Label className="text-xs">Workflow version to evaluate</Label>
            <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
              <SelectTrigger>
                <SelectValue placeholder="Select workflow version" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Use dataset default workflow</SelectItem>
                {workflows
                  .filter((wf): wf is Workflow & { id: string } => Boolean(wf.id))
                  .map((wf) => (
                    <SelectItem key={wf.id} value={wf.id}>
                      {wf.name} (v{wf.version})
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Label className="text-xs">Extra metadata (JSON)</Label>
            <Textarea
              value={inputMetadataText}
              onChange={(e) => setInputMetadataText(e.target.value)}
              className="font-mono text-xs"
              rows={4}
            />
            <div className="flex items-center justify-between rounded-md border px-3 py-2 mt-1">
              <div>
                <div className="text-xs font-medium">Use memory</div>
                <div className="text-xs text-gray-400">Generates a unique thread ID per run so the workflow remembers previous inputs/outputs</div>
              </div>
              <Switch checked={useMemory} onCheckedChange={setUseMemory} />
            </div>
            <Label className="text-xs">Validation methods</Label>
            <div className="space-y-2">
              {METRICS.map((metric) => (
                <div key={metric} className="flex items-center space-x-2">
                  <Checkbox
                    id={`metric-${metric}`}
                    checked={metrics.includes(metric)}
                    onCheckedChange={(checked) => {
                      setMetrics((prev) =>
                        checked
                          ? [...prev, metric]
                          : prev.filter((m) => m !== metric),
                      );
                    }}
                  />
                  <Label
                    htmlFor={`metric-${metric}`}
                    className="text-xs font-normal cursor-pointer"
                  >
                    {metric}
                  </Label>
                </div>
              ))}
            </div>

            {metrics.includes("nli_eval") && (
              <div className="border rounded-md p-3 space-y-2">
                <div className="text-xs font-semibold">Guardrail NLI Config</div>
                <p className="text-xs text-gray-500">
                  Uses workflow output as answer and expected output as evidence by
                  default.
                </p>
                <Label className="text-xs">NLI model</Label>
                <Select value={nliModelName} onValueChange={setNliModelName}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select NLI model" />
                  </SelectTrigger>
                  <SelectContent>
                    {NLI_MODEL_OPTIONS.map((model) => (
                      <SelectItem key={model.value} value={model.value}>
                        {model.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Label className="text-xs">Min entailment score (0-1)</Label>
                <Input
                  value={nliMinEntailScore}
                  onChange={(e) => setNliMinEntailScore(e.target.value)}
                />
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="nli-fail-on-contradiction"
                    checked={nliFailOnContradiction}
                    onCheckedChange={(checked) => setNliFailOnContradiction(Boolean(checked))}
                  />
                  <Label htmlFor="nli-fail-on-contradiction" className="text-xs font-normal cursor-pointer">
                    Fail on contradiction
                  </Label>
                </div>
              </div>
            )}

            {metrics.includes("provenance_eval") && (
              <div className="border rounded-md p-3 space-y-2">
                <div className="text-xs font-semibold">
                  Guardrail Provenance Config
                </div>
                <p className="text-xs text-gray-500">
                  Uses workflow output as answer and expected output as context by
                  default.
                </p>
                <Label className="text-xs">Provenance mode</Label>
                <Select
                  value={provMode}
                  onValueChange={(value: "embeddings" | "llm") => setProvMode(value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="embeddings">
                      Provenance (Embeddings)
                    </SelectItem>
                    <SelectItem value="llm">Provenance (LLM judge)</SelectItem>
                  </SelectContent>
                </Select>
                <Label className="text-xs">Min score (0-1)</Label>
                <Input
                  value={provMinScore}
                  onChange={(e) => setProvMinScore(e.target.value)}
                />
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="prov-fail-on-violation"
                    checked={provFailOnViolation}
                    onCheckedChange={(checked) => setProvFailOnViolation(Boolean(checked))}
                  />
                  <Label htmlFor="prov-fail-on-violation" className="text-xs font-normal cursor-pointer">
                    Fail on violation
                  </Label>
                </div>
                {provMode === "embeddings" && (
                  <>
                    <Label className="text-xs">Embedding provider</Label>
                    <Select
                      value={provEmbeddingType}
                      onValueChange={(
                        value: "openai" | "huggingface" | "bedrock",
                      ) => setProvEmbeddingType(value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select embedding provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="huggingface">HuggingFace</SelectItem>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                      </SelectContent>
                    </Select>
                    <Label className="text-xs">Embedding model name</Label>
                    <Input
                      value={provEmbeddingModelName}
                      onChange={(e) => setProvEmbeddingModelName(e.target.value)}
                      placeholder="all-MiniLM-L6-v2"
                    />
                  </>
                )}
                {provMode === "llm" && (
                  <>
                    <Label className="text-xs">LLM Provider</Label>
                    <Select
                      value={provLlmProviderId}
                      onValueChange={setProvLlmProviderId}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            {provider.name} ({provider.llm_model_provider} -{" "}
                            {provider.llm_model})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Label className="text-xs">Additional judge instructions</Label>
                    <p className="text-xs text-gray-500">
                      Appended to the base system prompt to fine-tune judge behaviour.
                      E.g. <em>"When no Context is available, treat the answer as supported."</em>
                    </p>
                    <Textarea
                      value={provLlmJudgeSystemPromptSuffix}
                      onChange={(e) => setProvLlmJudgeSystemPromptSuffix(e.target.value)}
                      placeholder="Optional extra instructions for the judge..."
                      rows={4}
                    />
                  </>
                )}
              </div>
            )}
          </div>
          <DialogFooter className="border-t px-6 py-4 shrink-0">
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateEvaluation}
              disabled={
                !evaluationName.trim() || selectedSuiteId === "none" || metrics.length === 0
              }
            >
              Create Evaluation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
};

export default EvaluationsPage;


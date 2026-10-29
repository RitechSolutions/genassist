import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import toast from "react-hot-toast";
import { Button } from "@/components/button";
import { Skeleton } from "@/components/skeleton";
import { extractErrorMessage } from "@/helpers/apiError";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import { listTestSuites } from "@/services/testSuites";
import { getWorkflowsMinimal } from "@/services/workflows";
import {
  createTestEvaluation,
  getTestEvaluationById,
  runTestEvaluation,
  updateTestEvaluation,
} from "@/services/testEvaluations";
import {
  buildTechniqueConfigs,
  formMetadata,
  getEditInitialData,
  type EvaluationFormData,
} from "../helpers/evaluationForm";
import { isRunConflict, runStartErrorMessage } from "../helpers/runErrors";
import { WORKFLOW_SUMMARIES_QUERY_KEY } from "../hooks/useEvaluationData";
import { CATEGORIES_QUERY_KEY } from "../hooks/useCategories";
import { previewedForEditing } from "../hooks/useChecksPreview";
import { EvaluationEditor } from "./EvaluationEditor";

interface EvaluationEditorViewProps {
  /** The evaluation to edit; a new one is made without it. */
  evaluationId?: string;
  /** Pins the workflow, as in the builder's tab. */
  lockedWorkflowId?: string;
  /** A workflow to start a new evaluation with, which can still be changed. */
  workflowId?: string;
  /** The version Save and run preselects, such as the one open in the builder; the active one when left out. */
  runVersionId?: string;
  /** Called with the saved evaluation's id. */
  onDone: (evaluationId: string) => void;
  onCancel: () => void;
}

/** The evaluation editor with what it needs loaded: the workflows, datasets, graders and the evaluation. */
export const EvaluationEditorView: React.FC<EvaluationEditorViewProps> = ({
  evaluationId,
  lockedWorkflowId,
  workflowId,
  runVersionId,
  onDone,
  onCancel,
}) => {
  const queryClient = useQueryClient();
  const reference = useQuery({
    queryKey: ["evaluation-editor-reference"],
    queryFn: async () => {
      const [workflows, suites, providers] = await Promise.all([
        getWorkflowsMinimal(),
        listTestSuites(),
        getLLMProvidersMinimal(),
      ]);
      return {
        workflows: workflows ?? [],
        suites: suites ?? [],
        providers: (providers ?? []).filter((provider) => provider.is_active === 1),
      };
    },
    staleTime: 0,
    refetchOnWindowFocus: false,
  });
  // Older methods become checks first, since the editor shows checks only. Loaded once per open.
  const evaluation = useQuery({
    queryKey: ["evaluation-editor", evaluationId],
    queryFn: async () => {
      const loaded = await getTestEvaluationById(evaluationId ?? "");
      return loaded ? previewedForEditing(loaded) : null;
    },
    enabled: Boolean(evaluationId),
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const submit = async (data: EvaluationFormData, options?: { run?: boolean; targetWorkflowId?: string }) => {
    const payload = {
      name: data.name.trim(),
      suite_id: data.suiteId,
      workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
      techniques: data.metrics,
      technique_configs: buildTechniqueConfigs(data),
      input_metadata: formMetadata(data),
    };
    let savedId: string;
    if (evaluationId) {
      try {
        // "" clears the description and category; undefined would keep the old ones.
        const updated = await updateTestEvaluation(evaluationId, {
          ...payload,
          description: data.description.trim(),
          category: data.category,
        });
        if (!updated) {
          toast.error("You don't have permission to edit evaluations.");
          return;
        }
      } catch (error) {
        toast.error(
          isRunConflict(error)
            ? "This evaluation is running. Wait for it to finish before editing."
            : extractErrorMessage(error, "Failed to update evaluation"),
        );
        return;
      }
      savedId = evaluationId;
      toast.success("Evaluation updated");
    } else {
      const created = await createTestEvaluation({
        ...payload,
        description: data.description.trim() || undefined,
        category: data.category || undefined,
      });
      if (!created?.id) {
        toast.error("You don't have permission to create evaluations.");
        return;
      }
      savedId = created.id;
      toast.success("Evaluation created");
    }
    // Its workflow may have changed, so every list and the summaries are read again.
    void queryClient.invalidateQueries({ queryKey: WORKFLOW_SUMMARIES_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: ["workflow-evaluations"] });
    void queryClient.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
    if (options?.run) {
      try {
        const started = await runTestEvaluation(savedId, options.targetWorkflowId);
        if (started) toast.success("Evaluation started");
        else toast.error("Saved, but you don't have permission to run evaluations.");
      } catch (error) {
        toast.error(runStartErrorMessage(error));
      }
    }
    onDone(savedId);
  };

  // A failed reload keeps what loaded before, so only a first load that failed replaces the form.
  const failed =
    (reference.isError && !reference.data) ||
    (evaluation.isError && !evaluation.data) ||
    (Boolean(evaluationId) && evaluation.data === null);
  if (failed) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onCancel} aria-label="Back">
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <p className="text-sm text-destructive">
          {evaluation.data === null ? "This evaluation could not be found." : "The editor could not be loaded."}
        </p>
      </div>
    );
  }

  if (!reference.data || (evaluationId && !evaluation.data)) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const { workflows, suites, providers } = reference.data;
  const initialData = evaluation.data
    ? getEditInitialData(evaluation.data, providers)
    : workflowId
      ? { workflowId }
      : undefined;

  return (
    <EvaluationEditor
      key={evaluationId ?? "new"}
      mode={evaluationId ? "edit" : "create"}
      initialData={initialData}
      suites={suites}
      workflows={workflows}
      providers={providers}
      lockedWorkflowId={lockedWorkflowId}
      runVersionId={runVersionId}
      onSubmit={submit}
      onCancel={onCancel}
    />
  );
};

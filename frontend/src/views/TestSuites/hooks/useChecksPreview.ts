import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import { previewEvaluationChecks } from "@/services/testEvaluations";
import { needsConversion } from "../helpers/checks";

type Previews = Map<string, TestEvaluationConfig>;

/** Older methods read as checks; nothing is saved until the editor saves, and a run converts its own copy. */
export const useChecksPreview = (evaluations: TestEvaluationConfig[]): Previews => {
  // The edit time is in the key, so a changed evaluation is read again.
  const pending = evaluations
    .filter((evaluation) => evaluation.id && needsConversion(evaluation.techniques))
    .map((evaluation) => `${evaluation.id}@${evaluation.updated_at}`)
    .sort();
  const { data } = useQuery({
    queryKey: ["evaluation-checks-preview", pending],
    queryFn: () => previewEvaluationChecks(pending.map((key) => key.split("@")[0])),
    enabled: pending.length > 0,
    staleTime: Infinity,
  });
  return useMemo(() => new Map((data?.evaluations ?? []).map((evaluation) => [evaluation.id, evaluation])), [data]);
};

/** The evaluation with its older methods as checks, or as it is. */
export const withPreview = (evaluation: TestEvaluationConfig, previews: Previews): TestEvaluationConfig => {
  const preview = needsConversion(evaluation.techniques) ? previews.get(evaluation.id) : undefined;
  return preview
    ? { ...evaluation, techniques: preview.techniques, technique_configs: preview.technique_configs }
    : evaluation;
};

/** The evaluation the editor opens: its older methods as checks, saved only when the editor saves. */
export const previewedForEditing = async (evaluation: TestEvaluationConfig): Promise<TestEvaluationConfig> => {
  if (!evaluation.id || !needsConversion(evaluation.techniques)) return evaluation;
  try {
    const result = await previewEvaluationChecks([evaluation.id]);
    const preview = result?.evaluations?.find((item) => item.id === evaluation.id);
    return preview ? withPreview(evaluation, new Map([[preview.id, preview]])) : evaluation;
  } catch {
    return evaluation;
  }
};

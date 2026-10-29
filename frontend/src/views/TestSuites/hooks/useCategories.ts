import { useQuery } from "@tanstack/react-query";
import { listEvaluationCategories } from "@/services/testEvaluations";

/** Read again after a dataset or evaluation is saved or imported. */
export const CATEGORIES_QUERY_KEY = ["evaluation-categories"];

const NO_CATEGORIES: string[] = [];

/** The categories datasets and evaluations use, shared by the pickers and filters. */
export const useCategories = (): string[] => {
  const { data } = useQuery({
    queryKey: CATEGORIES_QUERY_KEY,
    queryFn: async () => (await listEvaluationCategories()) ?? NO_CATEGORIES,
    staleTime: 60_000,
  });
  return data ?? NO_CATEGORIES;
};

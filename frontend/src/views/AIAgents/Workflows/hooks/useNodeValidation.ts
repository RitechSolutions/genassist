import { useMemo } from "react";
import { getEmptyRequiredFields } from "../utils/nodeValidation";
import { NodeData } from "../types/nodes";
import { useQuery } from "@tanstack/react-query";
import { getAllNodeSchemas } from "@/services/workflows";

export function useNodeValidation(nodeType: string, nodeData: NodeData) {
  const { data, isLoading } = useQuery({
    queryKey: ["nodeSchemas"],
    queryFn: getAllNodeSchemas,
  });

  const schema = data?.[nodeType] ?? null;

  // Compute missing fields when data or schema changes
  const missingFields = useMemo(() => {
    if (!schema) return [];
    return getEmptyRequiredFields(nodeData, schema);
  }, [schema, nodeData]);

  return {
    isLoading,
    hasValidationError: missingFields.length > 0,
    missingFields,
  };
}

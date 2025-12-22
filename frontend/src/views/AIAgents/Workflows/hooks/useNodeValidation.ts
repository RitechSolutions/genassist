import { useState, useEffect, useMemo } from "react";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getEmptyRequiredFields } from "../utils/nodeValidation";
import { NodeData } from "../types/nodes";
import { useNodeSchema } from "@/context/NodeSchemaContext";

export function useNodeValidation(nodeType: string, nodeData: NodeData) {
  const { getSchema, loading } = useNodeSchema();
  const [schema, setSchema] = useState<FieldSchema[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadSchema() {
      if (loading) {
        setIsLoading(true);
        return;
      }

      try {
        const cachedSchema = getSchema(nodeType);

        if (cachedSchema) {
          setSchema(cachedSchema);
          setIsLoading(false);
        } else {
          console.error(`Schema not found for node type: ${nodeType}`);
          setSchema(null);
          setIsLoading(false);
        }
      } catch (err) {
        console.error("Error loading node schema", err);
        setSchema(null);
        setIsLoading(false);
      }
    }

    loadSchema();
  }, [nodeType, loading, getSchema]);

  // Compute missing fields when data or schema changes
  const missingFields = useMemo(() => {
    if (!schema) return [];
    return getEmptyRequiredFields(nodeData, schema);
  }, [schema, nodeData]);

  const hasValidationError = missingFields.length > 0;

  return {
    isLoading,
    hasValidationError,
    missingFields,
  };
}

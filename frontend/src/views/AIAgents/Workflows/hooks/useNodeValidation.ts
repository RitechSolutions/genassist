import { useState, useEffect, useMemo } from "react";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getEmptyRequiredFields } from "../utils/nodeValidation";
import { NodeData } from "../types/nodes";
import { useNodeSchema } from "@/context/NodeSchemaContext";

export function useNodeValidation(nodeType: string, nodeData: NodeData) {
  const { getSchema, loading, ensureLoaded, schemas } = useNodeSchema();
  const [schema, setSchema] = useState<FieldSchema[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadSchema() {
      setIsLoading(true);

      // Trigger lazy load of schemas when needed
      await ensureLoaded();

      if (!isMounted) return;

      try {
        const cachedSchema = getSchema(nodeType);

        if (cachedSchema) {
          setSchema(cachedSchema);
        } else {
          // Schema might not exist for this node type - this is not necessarily an error
          setSchema(null);
        }
      } catch (err) {
        console.error("Error loading node schema", err);
        setSchema(null);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSchema();

    return () => {
      isMounted = false;
    };
  }, [nodeType, ensureLoaded, getSchema, schemas]);

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

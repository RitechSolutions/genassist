import { useState, useEffect, useMemo } from "react";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getNodeDialogSchema } from "@/services/workflows";
import { getEmptyRequiredFields } from "../utils/nodeValidation";
import { NodeData } from "../types/nodes";

export function useNodeValidation(nodeType: string, nodeData: NodeData) {
  const [schema, setSchema] = useState<FieldSchema[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch schema on mount or when nodeType changes
  useEffect(() => {
    let isMounted = true;

    async function fetchSchema() {
      setIsLoading(true);
      try {
        const fetchedSchema = await getNodeDialogSchema(nodeType);
        if (isMounted) {
          setSchema(fetchedSchema);
        }
      } catch (error) {
        console.error("Error fetching node dialog schema", error);
        if (isMounted) {
          setSchema(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchSchema();

    return () => {
      isMounted = false;
    };
  }, [nodeType]);

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

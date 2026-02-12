import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getAllNodeSchemas } from "@/services/workflows";
import { isAuthenticated } from "@/services/auth";

interface NodeSchemaContextType {
  schemas: Map<string, FieldSchema[]>;
  loading: boolean;
  error: string | null;
  getSchema: (nodeType: string) => FieldSchema[] | null;
  hasSchema: (nodeType: string) => boolean;
  refreshSchemas: () => Promise<void>;
  ensureLoaded: () => Promise<void>;
}

const NodeSchemaContext = createContext<NodeSchemaContextType | undefined>(
  undefined
);

interface NodeSchemaProviderProps {
  children: ReactNode;
}

export const NodeSchemaProvider: React.FC<NodeSchemaProviderProps> = ({
  children,
}) => {
  const [schemas, setSchemas] = useState<Map<string, FieldSchema[]>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const fetchPromiseRef = useRef<Promise<void> | null>(null);

  const fetchSchemas = useCallback(async () => {
    // If already fetched, don't fetch again
    if (hasFetchedRef.current) return;

    // If a fetch is in progress, return that promise
    if (fetchPromiseRef.current) return fetchPromiseRef.current;

    const fetchPromise = (async () => {
      try {
        setLoading(true);

        const schemasResponse = await getAllNodeSchemas();
        const schemaMap = new Map<string, FieldSchema[]>(
          Object.entries(schemasResponse)
        );

        setSchemas(schemaMap);
        setError(null);
        hasFetchedRef.current = true;
      } catch (err) {
        setError("Failed to load node schemas");
      } finally {
        setLoading(false);
        fetchPromiseRef.current = null;
      }
    })();

    fetchPromiseRef.current = fetchPromise;
    return fetchPromise;
  }, []);

  // Lazy load - only fetch when needed
  const ensureLoaded = useCallback(async () => {
    if (!hasFetchedRef.current && isAuthenticated()) {
      await fetchSchemas();
    }
  }, [fetchSchemas]);

  const getSchema = (nodeType: string): FieldSchema[] | null => {
    return schemas.get(nodeType) || null;
  };

  const hasSchema = (nodeType: string): boolean => {
    return schemas.has(nodeType);
  };

  const refreshSchemas = async (): Promise<void> => {
    hasFetchedRef.current = false;
    await fetchSchemas();
  };

  const value: NodeSchemaContextType = {
    schemas,
    loading,
    error,
    getSchema,
    hasSchema,
    refreshSchemas,
    ensureLoaded,
  };

  return (
    <NodeSchemaContext.Provider value={value}>
      {children}
    </NodeSchemaContext.Provider>
  );
};

export const useNodeSchema = (): NodeSchemaContextType => {
  const context = useContext(NodeSchemaContext);
  if (context === undefined) {
    throw new Error("useNodeSchema must be used within a NodeSchemaProvider");
  }
  return context;
};

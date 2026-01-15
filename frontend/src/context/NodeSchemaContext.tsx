import React, {
  createContext,
  useContext,
  useState,
  useEffect,
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSchemas = async () => {
    try {
      setLoading(true);

      const schemasResponse = await getAllNodeSchemas();
      const schemaMap = new Map<string, FieldSchema[]>(
        Object.entries(schemasResponse)
      );

      setSchemas(schemaMap);
      setError(null);
    } catch (err) {
      setError("Failed to load node schemas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // check if the user is authenticated
    if (isAuthenticated()) {
      fetchSchemas();
    }
  }, []);

  const getSchema = (nodeType: string): FieldSchema[] | null => {
    return schemas.get(nodeType) || null;
  };

  const hasSchema = (nodeType: string): boolean => {
    return schemas.has(nodeType);
  };

  const refreshSchemas = async (): Promise<void> => {
    await fetchSchemas();
  };

  const value: NodeSchemaContextType = {
    schemas,
    loading,
    error,
    getSchema,
    hasSchema,
    refreshSchemas,
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

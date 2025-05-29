import { useCallback } from 'react';
import { useReactFlow, Connection } from 'reactflow';
import { validateSchemaCompatibility } from '../types/schemas';
import { BaseNodeData, NodeCompatibility, NodeHandler } from '../types/nodes';

// Helper function to check if two compatibility types are compatible
const areCompatible = (source: NodeCompatibility, target: NodeCompatibility): boolean => {
  // 'any' is compatible with everything
  if (target === 'any') return true;
  if (source === 'any') return true;

  // Direct match
  if (source === target) return true;

  // Special cases
  if (source === 'llm' && target === 'text') return true;
  if (source === 'tools' && target === 'text') return true;
  if (source === 'json' && target === 'text') return true;

  return false;
};

// Helper function to find handler by id
const findHandler = (handlers: NodeHandler[], id: string): NodeHandler | undefined => {
  return handlers.find(handler => handler.id === id);
};

export const useSchemaValidation = () => {
  const { getNode } = useReactFlow();

  const validateConnection = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return false;

    const sourceNode = getNode(connection.source);
    const targetNode = getNode(connection.target);

    if (!sourceNode || !targetNode) return false;

    const sourceData = sourceNode.data as BaseNodeData;
    const targetData = targetNode.data as BaseNodeData;

    // Find the handlers involved in this connection
    const sourceHandler = findHandler(sourceData.handlers, connection.sourceHandle);
    const targetHandler = findHandler(targetData.handlers, connection.targetHandle);

    if (!sourceHandler || !targetHandler) return false;

    // Check compatibility types
    if (!areCompatible(sourceHandler.compatibility, targetHandler.compatibility)) {
      console.warn('Compatibility validation failed:', {
        source: sourceHandler.compatibility,
        target: targetHandler.compatibility
      });
      return false;
    }

    // If either handler doesn't have a schema, allow the connection
    if (!sourceHandler.schema || !targetHandler.schema) return true;

    // Validate schema compatibility
    const validation = validateSchemaCompatibility(
      sourceHandler.schema,
      targetHandler.schema
    );

    if (!validation.isValid) {
      console.warn('Schema validation failed:', validation.errors);
      return false;
    }

    return true;
  }, [getNode]);

  return {
    validateConnection
  };
}; 
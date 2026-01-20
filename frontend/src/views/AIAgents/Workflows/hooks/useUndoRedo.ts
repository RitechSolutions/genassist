import { useCallback, useRef, useState } from "react";
import { Node, Edge, NodeChange, EdgeChange } from "reactflow";

interface HistoryState {
  nodes: Node[];
  edges: Edge[];
}

interface UseUndoRedoOptions {
  maxHistorySize?: number;
  debounceTime?: number;
}

interface UseUndoRedoReturn {
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  takeSnapshot: () => void;
  clear: () => void;
}

/**
 * Hook to manage undo/redo functionality for React Flow nodes and edges
 * Tracks history of node/edge states and provides undo/redo operations
 */
export const useUndoRedo = (
  nodes: Node[],
  edges: Edge[],
  setNodes: (nodes: Node[]) => void,
  setEdges: (edges: Edge[]) => void,
  options: UseUndoRedoOptions = {}
): UseUndoRedoReturn => {
  const { maxHistorySize = 50, debounceTime = 500 } = options;

  // History stacks
  const [past, setPast] = useState<HistoryState[]>([]);
  const [future, setFuture] = useState<HistoryState[]>([]);

  // Debounce timer
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isUndoRedoRef = useRef(false);

  /**
   * Take a snapshot of the current state and add it to history
   */
  const takeSnapshot = useCallback(() => {
    // Don't record if we're in the middle of undo/redo
    if (isUndoRedoRef.current) return;

    // Clear any pending debounce
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Debounce the snapshot to batch rapid changes (like dragging)
    debounceTimerRef.current = setTimeout(() => {
      const snapshot: HistoryState = {
        nodes: JSON.parse(JSON.stringify(nodes)),
        edges: JSON.parse(JSON.stringify(edges)),
      };

      setPast((prev) => {
        const newPast = [...prev, snapshot];
        // Limit history size
        if (newPast.length > maxHistorySize) {
          return newPast.slice(1);
        }
        return newPast;
      });

      // Clear future when a new change is made
      setFuture([]);
    }, debounceTime);
  }, [nodes, edges, maxHistorySize, debounceTime]);

  /**
   * Undo the last change
   */
  const undo = useCallback(() => {
    if (past.length === 0) return;

    isUndoRedoRef.current = true;

    // Get the last state from history
    const newPast = [...past];
    const previousState = newPast.pop()!;

    // Save current state to future
    const currentState: HistoryState = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };

    setPast(newPast);
    setFuture((prev) => [...prev, currentState]);

    // Restore previous state
    setNodes(previousState.nodes);
    setEdges(previousState.edges);

    // Reset flag after a brief delay to allow state to settle
    setTimeout(() => {
      isUndoRedoRef.current = false;
    }, 100);
  }, [past, nodes, edges, setNodes, setEdges]);

  /**
   * Redo the last undone change
   */
  const redo = useCallback(() => {
    if (future.length === 0) return;

    isUndoRedoRef.current = true;

    // Get the next state from future
    const newFuture = [...future];
    const nextState = newFuture.pop()!;

    // Save current state to history
    const currentState: HistoryState = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };

    setFuture(newFuture);
    setPast((prev) => [...prev, currentState]);

    // Restore next state
    setNodes(nextState.nodes);
    setEdges(nextState.edges);

    // Reset flag after a brief delay to allow state to settle
    setTimeout(() => {
      isUndoRedoRef.current = false;
    }, 100);
  }, [future, nodes, edges, setNodes, setEdges]);

  /**
   * Clear all history
   */
  const clear = useCallback(() => {
    setPast([]);
    setFuture([]);
  }, []);

  return {
    undo,
    redo,
    canUndo: past.length > 0,
    canRedo: future.length > 0,
    takeSnapshot,
    clear,
  };
};

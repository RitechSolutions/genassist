import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Edge, Node } from "reactflow";
import { isEqual } from "lodash";
import { stripTransientGraphFields } from "../utils/graphNormalization";

interface HistoryState {
  nodes: Node[];
  edges: Edge[];
}

interface UseUndoRedoOptions {
  maxHistorySize?: number;
  debounceTime?: number;
  // Puts back node data that JSON cloning strips out on undo/redo 
  hydrateNodes?: (nodes: Node[]) => Node[];
}

interface UseUndoRedoReturn {
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  takeSnapshot: () => void;
  // Seeds a fresh baseline and drops both stacks; used when a new workflow loads 
  resetHistory: (state: HistoryState) => void;
  // Drops both stacks but rebaselines to the live canvas without suppressing the next edit
  clear: () => void;
}

const normalizeState = (state: HistoryState): HistoryState =>
  stripTransientGraphFields(state.nodes, state.edges);

const cloneState = (state: HistoryState): HistoryState =>
  JSON.parse(JSON.stringify(normalizeState(state))) as HistoryState;

const trimHistory = (
  history: HistoryState[],
  maxHistorySize: number
): HistoryState[] => {
  if (history.length <= maxHistorySize) return history;
  return history.slice(history.length - maxHistorySize);
};

/**
 * Undo/redo timeline for React Flow nodes and edges. Records the pre-change
 * baseline on a debounce so rapid edits collapse into one history step
 */
export const useUndoRedo = (
  nodes: Node[],
  edges: Edge[],
  setNodes: Dispatch<SetStateAction<Node[]>>,
  setEdges: Dispatch<SetStateAction<Edge[]>>,
  options: UseUndoRedoOptions = {}
): UseUndoRedoReturn => {
  const { maxHistorySize = 50, debounceTime = 500, hydrateNodes } = options;

  const [past, setPast] = useState<HistoryState[]>([]);
  const [future, setFuture] = useState<HistoryState[]>([]);
  const [hasPendingSnapshot, setHasPendingSnapshot] = useState(false);

  const latestStateRef = useRef<HistoryState>({ nodes, edges });
  const pastRef = useRef<HistoryState[]>([]);
  const futureRef = useRef<HistoryState[]>([]);
  const lastSnapshotRef = useRef<HistoryState | null>(null);
  const pendingUndoTargetRef = useRef<HistoryState | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suppressNextSnapshotRef = useRef(false);

  // Keep latest state available to timers/callbacks without stale closures
  latestStateRef.current = { nodes, edges };

  const setPastHistory = useCallback((nextPast: HistoryState[]) => {
    pastRef.current = nextPast;
    setPast(nextPast);
  }, []);

  const setFutureHistory = useCallback((nextFuture: HistoryState[]) => {
    futureRef.current = nextFuture;
    setFuture(nextFuture);
  }, []);

  const clearDebounceTimer = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
  }, []);

  const clearPendingSnapshot = useCallback(() => {
    clearDebounceTimer();
    pendingUndoTargetRef.current = null;
    setHasPendingSnapshot(false);
  }, [clearDebounceTimer]);

  const restoreState = useCallback(
    (state: HistoryState) => {
      const clonedState = cloneState(state);
      lastSnapshotRef.current = clonedState;
      // Skip the snapshot effect tick this restore is about to trigger
      suppressNextSnapshotRef.current = true;

      setNodes(
        hydrateNodes ? hydrateNodes(clonedState.nodes) : clonedState.nodes
      );
      setEdges(clonedState.edges);
    },
    [hydrateNodes, setEdges, setNodes]
  );

  const takeSnapshot = useCallback(() => {
    if (suppressNextSnapshotRef.current) {
      suppressNextSnapshotRef.current = false;
      clearPendingSnapshot();
      return;
    }

    const lastSnapshot = lastSnapshotRef.current;

    // First change seeds the baseline rather than recording a step
    if (!lastSnapshot) {
      lastSnapshotRef.current = cloneState(latestStateRef.current);
      return;
    }

    if (!pendingUndoTargetRef.current) {
      // Selection clicks, edge-class rewrites, and re-measure echoes change
      // state identity without content, no undo window for those
      if (isEqual(cloneState(latestStateRef.current), lastSnapshot)) {
        return;
      }
      pendingUndoTargetRef.current = cloneState(lastSnapshot);

      // A new edit starts a fresh branch, drop redo now
      if (futureRef.current.length > 0) {
        setFutureHistory([]);
      }
    }

    clearDebounceTimer();
    setHasPendingSnapshot(true);

    debounceTimerRef.current = setTimeout(() => {
      const undoTarget = pendingUndoTargetRef.current;

      if (!undoTarget) {
        setHasPendingSnapshot(false);
        debounceTimerRef.current = null;
        return;
      }

      const latestState = cloneState(latestStateRef.current);

      // Edits that net out to the baseline shouldn't record a step
      if (
        lastSnapshotRef.current &&
        isEqual(latestState, lastSnapshotRef.current)
      ) {
        pendingUndoTargetRef.current = null;
        setHasPendingSnapshot(false);
        debounceTimerRef.current = null;
        return;
      }

      setPastHistory(
        trimHistory([...pastRef.current, cloneState(undoTarget)], maxHistorySize)
      );
      lastSnapshotRef.current = latestState;
      pendingUndoTargetRef.current = null;
      setHasPendingSnapshot(false);
      debounceTimerRef.current = null;
    }, debounceTime);
  }, [
    clearDebounceTimer,
    clearPendingSnapshot,
    debounceTime,
    maxHistorySize,
    setFutureHistory,
    setPastHistory,
  ]);

  const undo = useCallback(() => {
    let pendingUndoTarget = pendingUndoTargetRef.current;

    if (!pendingUndoTarget && pastRef.current.length === 0) return;

    const currentState =
      suppressNextSnapshotRef.current && lastSnapshotRef.current
        ? cloneState(lastSnapshotRef.current)
        : cloneState(latestStateRef.current);


    if (pendingUndoTarget && isEqual(pendingUndoTarget, currentState)) {
      clearPendingSnapshot();
      pendingUndoTarget = null;
    }

    const previousState =
      pendingUndoTarget ?? pastRef.current[pastRef.current.length - 1];

    if (!previousState) return;

    clearPendingSnapshot();

    if (!pendingUndoTarget) {
      setPastHistory(pastRef.current.slice(0, -1));
    }

    setFutureHistory([...futureRef.current, currentState]);
    restoreState(previousState);
  }, [clearPendingSnapshot, restoreState, setFutureHistory, setPastHistory]);

  const redo = useCallback(() => {
    const nextState = futureRef.current[futureRef.current.length - 1];

    if (!nextState) return;

    clearPendingSnapshot();

    const currentState =
      suppressNextSnapshotRef.current && lastSnapshotRef.current
        ? cloneState(lastSnapshotRef.current)
        : cloneState(latestStateRef.current);

    setFutureHistory(futureRef.current.slice(0, -1));
    setPastHistory(
      trimHistory([...pastRef.current, currentState], maxHistorySize)
    );
    restoreState(nextState);
  }, [
    clearPendingSnapshot,
    maxHistorySize,
    restoreState,
    setFutureHistory,
    setPastHistory,
  ]);

  const resetHistory = useCallback(
    (state: HistoryState) => {
      clearPendingSnapshot();
      lastSnapshotRef.current = cloneState(state);
      suppressNextSnapshotRef.current = true;
      setPastHistory([]);
      setFutureHistory([]);
    },
    [clearPendingSnapshot, setFutureHistory, setPastHistory]
  );

  const clear = useCallback(() => {
    clearPendingSnapshot();
    lastSnapshotRef.current = cloneState(latestStateRef.current);
    suppressNextSnapshotRef.current = false;
    setPastHistory([]);
    setFutureHistory([]);
  }, [clearPendingSnapshot, setFutureHistory, setPastHistory]);

  useEffect(() => {
    return () => {
      clearDebounceTimer();
    };
  }, [clearDebounceTimer]);

  return {
    undo,
    redo,
    canUndo: past.length > 0 || hasPendingSnapshot,
    canRedo: future.length > 0,
    takeSnapshot,
    resetHistory,
    clear,
  };
};

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { Node, Edge } from "reactflow";
// Types for workflow execution state
export interface NodeExecutionResult {
  status: "success" | "error" | "pending";
  output: Record<string, unknown>;
  timestamp: number;
  nodeType: string;
  nodeName: string;
}

export interface WorkflowExecutionState {
  // Session data from chat input nodes
  session: Record<string, unknown>;

  // Source node outputs (predecessors)
  source: Record<string, unknown>;

  // All node outputs by node ID
  nodeOutputs: Record<string, NodeExecutionResult>;

  // Execution metadata
  lastExecutionId?: string;
  lastExecutionTime?: number;
}

export interface WorkflowExecutionContextType {
  state: WorkflowExecutionState;

  // Current workflow structure
  nodes: Node[];
  edges: Edge[];

  // Actions
  updateNodeOutput: (
    nodeId: string,
    output: Record<string, unknown> | string,
    nodeType: string,
    nodeName: string
  ) => void;
  clearNodeOutput: (nodeId: string) => void;
  clearAllOutputs: () => void;
  setWorkflowStructure: (nodes: Node[], edges: Edge[]) => void;
  loadExecutionState: (executionState: WorkflowExecutionState) => void;

  // Getters
  getNodeOutput: (nodeId: string) => NodeExecutionResult | undefined;
  getAvailableDataForNode: (nodeId: string) => Record<string, unknown>;
  hasNodeBeenExecuted: (nodeId: string) => boolean;
}

const WorkflowExecutionContext = createContext<
  WorkflowExecutionContextType | undefined
>(undefined);

export const useWorkflowExecution = () => {
  const context = useContext(WorkflowExecutionContext);
  if (!context) {
    throw new Error(
      "useWorkflowExecution must be used within a WorkflowExecutionProvider"
    );
  }
  return context;
};

interface WorkflowExecutionProviderProps {
  children: ReactNode;
}

export const WorkflowExecutionProvider: React.FC<
  WorkflowExecutionProviderProps
> = ({ children }) => {
  const [state, setState] = useState<WorkflowExecutionState>({
    session: {},
    source: {},
    nodeOutputs: {},
  });

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const updateNodeOutput = useCallback(
    (
      nodeId: string,
      output: Record<string, unknown>,
      nodeType: string,
      nodeName: string
    ) => {
      setState((prevState) => {
        const newState = { ...prevState };

        newState.nodeOutputs[nodeId] = {
          status: "success",
          output: output,
          timestamp: Date.now(),
          nodeType,
          nodeName,
        };

        // Update session data for chat input nodes
        if (nodeType === "chatInputNode") {
          newState.session = output;
        }

        // Update source data for all nodes
        newState.source = output;
        return newState;
      });
    },
    []
  );

  const clearNodeOutput = useCallback((nodeId: string) => {
    setState((prevState) => {
      const newState = { ...prevState };
      delete newState.nodeOutputs[nodeId];

      // Rebuild session and source from remaining outputs
      const remainingOutputs = Object.values(newState.nodeOutputs);

      // Rebuild session (only from chat input nodes)
      newState.session = {};
      remainingOutputs.forEach((result) => {
        if (result.nodeType === "chatInputNode") {
          newState.session = { ...newState.session, ...result.output };
        }
      });

      // Rebuild source (from all remaining outputs)
      newState.source = {};
      remainingOutputs.forEach((result) => {
        newState.source = { ...newState.source, ...result.output };
      });

      return newState;
    });
  }, []);

  const clearAllOutputs = useCallback(() => {
    setState({
      session: {},
      source: {},
      nodeOutputs: {},
    });
  }, []);

  const setWorkflowStructure = useCallback(
    (newNodes: Node[], newEdges: Edge[]) => {
      setNodes(newNodes);
      setEdges(newEdges);
    },
    []
  );

  const loadExecutionState = useCallback(
    (executionState: WorkflowExecutionState) => {
      setState(executionState);
    },
    []
  );

  const getNodeOutput = useCallback(
    (nodeId: string) => {
      return state.nodeOutputs[nodeId];
    },
    [state.nodeOutputs]
  );

  const hasNodeBeenExecuted = useCallback(
    (nodeId: string) => {
      if (Object.keys(state.nodeOutputs).length === 0) {
        return true;
      }
      return !!state.nodeOutputs[nodeId];
    },
    [state.nodeOutputs]
  );
  const getNodeById = useCallback(
    (nodeId: string) => {
      return nodes.find((node) => node.id === nodeId);
    },
    [nodes]
  );

  const getAvailableDataForNode = useCallback(
    (nodeId: string) => {
      // Find all predecessor nodes (nodes that come before this node in the workflow)
      const findPredecessors = (targetNodeId: string): string[] => {
        const predecessors = new Set<string>();
        const visited = new Set<string>();

        const dfs = (nodeId: string) => {
          if (visited.has(nodeId)) return;
          visited.add(nodeId);

          // Find edges where this node is the target
          edges.forEach((edge) => {
            if (edge.target === nodeId) {
              predecessors.add(edge.source);
              dfs(edge.source);
            }
          });
        };

        dfs(targetNodeId);
        return Array.from(predecessors);
      };

      const predecessorIds = findPredecessors(nodeId).filter(
        (id) => id !== nodeId
      );
      const node = getNodeById(nodeId);

      if (
        predecessorIds.length === 0 &&
        node &&
        node.type === "chatInputNode"
      ) {
        return state.session;
      }

      // Build available data object
      if (predecessorIds.length === 0) {
        return null;
      }

      // Find only direct predecessors (immediate sources)
      const currentNode = getNodeById(nodeId);
      const directPredecessors = edges
        .filter((edge) => edge.target === nodeId)
        .map((edge) => edge.source)
        .filter((predecessorId) => {
          // If current node is an agent, exclude toolBuilder nodes
          if (currentNode?.type === "agentNode") {
            const predecessorNode = getNodeById(predecessorId);
            return predecessorNode?.type !== "toolBuilderNode";
          }
          return true;
        });

      // Helper function to filter out keys containing "session.direct_input"
      const filterOutput = (output: unknown): unknown => {
        if (!output || typeof output !== "object" || Array.isArray(output)) return output;
        const filtered: Record<string, unknown> = {};
        Object.entries(output as Record<string, unknown>).forEach(([key, value]) => {
          if (!key.includes("session.direct_input")) {
            filtered[key] = value;
          }
        });
        return filtered;
      };

      // Build node outputs object with all predecessor outputs
      const nodeOutputs = {};
      predecessorIds.forEach((predecessorId) => {
        const predecessorOutput = state.nodeOutputs[predecessorId];
        if (predecessorOutput && predecessorOutput.output) {
          nodeOutputs[predecessorId] = filterOutput(predecessorOutput.output);
        }
      });

      // Build source object with only direct predecessors
      let source = {};
      if (directPredecessors.length === 1) {
        const predecessorOutput = state.nodeOutputs[directPredecessors[0]];
        if (predecessorOutput && predecessorOutput.output) {
          source = filterOutput(predecessorOutput.output);
        }
      } else {
        directPredecessors.forEach((predecessorId) => {
          const predecessorOutput = state.nodeOutputs[predecessorId];
          if (predecessorOutput && predecessorOutput.output) {
            source[predecessorId] = filterOutput(predecessorOutput.output);
          }
        });
      }

      const availableData: Record<string, unknown> = {
        session: state.session,
        source: source,
        node_outputs: nodeOutputs,
        // predecessors: predecessorIds,
      };

      return availableData;
    },
    [state.session, state.nodeOutputs, edges, getNodeById]
  );

  const value: WorkflowExecutionContextType = {
    state,
    nodes,
    edges,
    updateNodeOutput,
    clearNodeOutput,
    clearAllOutputs,
    setWorkflowStructure,
    loadExecutionState,
    getNodeOutput,
    hasNodeBeenExecuted,
    getAvailableDataForNode,
  };

  return (
    <WorkflowExecutionContext.Provider value={value}>
      {children}
    </WorkflowExecutionContext.Provider>
  );
};

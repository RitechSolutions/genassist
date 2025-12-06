import { WorkflowTestResponse } from "@/services/workflows";

// Extended execution state that includes real-time tracking
export interface WorkflowExecutionState extends Omit<WorkflowTestResponse, 'execution_summary'> {
  execution_summary: {
    execution_id: string;
    thread_id: string;
    timestamp: string;
    execution_path: string[];
    input: string;
    node_outputs: Record<string, unknown>;
  };
  // Current execution status
  isExecuting: boolean;
  currentStep: number;
  totalSteps: number;
  
  // Real-time execution tracking
  executionStartTime: number;
  executionEndTime?: number;
  
  // Node execution details
  nodeExecutionStatus: Record<string, NodeExecutionStatus>;
  
  // Execution history for debugging
  executionHistory: ExecutionStep[];
  
  // Error handling
  errors: ExecutionError[];
  
  // Performance metrics
  performanceMetrics: PerformanceMetrics;
}

// Status of individual node execution
export interface NodeExecutionStatus {
  nodeId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startTime?: number;
  endTime?: number;
  duration?: number;
  input?: Record<string, any>;
  output?: Record<string, any>;
  error?: string;
  retryCount: number;
  maxRetries: number;
}

// Individual execution step for history tracking
export interface ExecutionStep {
  stepNumber: number;
  nodeId: string;
  nodeType: string;
  nodeName: string;
  timestamp: number;
  input: Record<string, any>;
  output: Record<string, any>;
  status: 'success' | 'error' | 'skipped';
  duration: number;
  metadata?: Record<string, any>;
}

// Error information for failed executions
export interface ExecutionError {
  nodeId: string;
  nodeType: string;
  error: string;
  timestamp: number;
  retryCount: number;
  context?: Record<string, any>;
}

// Performance metrics for the workflow execution
export interface PerformanceMetrics {
  totalExecutionTime: number;
  averageNodeExecutionTime: number;
  slowestNode: string;
  slowestNodeTime: number;
  fastestNode: string;
  fastestNodeTime: number;
  totalNodesExecuted: number;
  successRate: number;
}

// Actions that can be performed on the execution state
export interface WorkflowExecutionActions {
  // Start a new execution
  startExecution: (input: Record<string, unknown>) => void;
  
  // Stop current execution
  stopExecution: () => void;
  
  // Update node output
  updateNodeOutput: (nodeId: string, output: Record<string, unknown>) => void;
  
  // Mark node as completed
  markNodeCompleted: (nodeId: string, output: Record<string, unknown>, nodeType: string, nodeName: string) => void;
  
  // Mark node as failed
  markNodeFailed: (nodeId: string, error: string, nodeType: string, nodeName: string) => void;
  
  // Retry failed node
  retryNode: (nodeId: string) => void;
  
  // Get node output
  getNodeOutput: (nodeId: string) => Record<string, unknown> | undefined;
  
  // Get all available outputs for a node
  getAvailableOutputs: (nodeId: string) => Record<string, unknown>;
  
  // Clear execution state
  clearExecution: () => void;
  
  // Export execution state
  exportExecutionState: () => WorkflowExecutionState;
}

// Context type for the workflow execution
export interface WorkflowExecutionContextType {
  state: WorkflowExecutionState | null;
  actions: WorkflowExecutionActions;
  isLoading: boolean;
  error: string | null;
}

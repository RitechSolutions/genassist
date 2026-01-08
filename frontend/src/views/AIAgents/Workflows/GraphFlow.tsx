import React, { useCallback, useState, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Panel,
  ReactFlowInstance,
  NodeMouseHandler,
  MarkerType,
  reconnectEdge,
} from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/button";
import { ChevronLeft, FolderOpen, PanelLeft } from "lucide-react";
import { isEqual } from "lodash";
import { getNodeTypes } from "./nodeTypes";
import { getEdgeTypes } from "./edgeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { NodeData } from "./types/nodes";
import { Workflow } from "@/interfaces/workflow.interface";
import WorkflowTestDialog from "./components/WorkflowTestDialog";
import NodePanel from "./components/panels/NodePanel";
import BottomPanel from "./components/panels/BottomPanel";
import WorkflowsSavedPanel from "./components/panels/WorkflowsSavedPanel";
import { useSchemaValidation } from "./hooks/useSchemaValidation";
import { useSidebar } from "@/components/sidebar";
import { AgentConfig, getAgentConfig, updateAgentConfig } from "@/services/api";
import { useParams } from "react-router-dom";
import { getWorkflowById, updateWorkflow } from "@/services/workflows";
import AgentTopPanel from "./components/panels/AgentTopPanel";
import { v4 as uuidv4 } from "uuid";
import { WorkflowProvider } from "./context/WorkflowContext";
import {
  WorkflowExecutionProvider,
  WorkflowExecutionState,
} from "./context/WorkflowExecutionContext";
import {
  handleDragOver,
  handleDrop,
  handleNodeDoubleClick,
} from "./utils/helpers";

// Get node types and edge types for React Flow
const nodeTypes = getNodeTypes();
const edgeTypes = getEdgeTypes();

const GraphFlowContent: React.FC = () => {
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  const [workflow, setWorkflow] = useState<Workflow>();
  const [agent, setAgent] = useState<AgentConfig>();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [showNodePanel, setShowNodePanel] = useState(false);
  const [showWorkflowPanel, setShowWorkflowPanel] = useState(false);
  const [currentTestConfig, setCurrentTestConfig] = useState<Workflow | null>(
    null
  );
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const lastSavedWorkflowRef = useRef<Workflow | null>(null);
  const [isSettling, setIsSettling] = useState(true);
  const [executionState, setExecutionState] = useState<WorkflowExecutionState | null>(null);

  const { toggleSidebar } = useSidebar();
  const { validateConnection } = useSchemaValidation();

  const { agentId } = useParams<{ agentId: string }>();
  const edgeReconnectSuccessful = useRef(true);

  // Handle double-click on nodes to focus view using helper function
  const onNodeDoubleClick: NodeMouseHandler = useCallback(
    (event, node) => {
      handleNodeDoubleClick(event, node, reactFlowInstance);
    },
    [reactFlowInstance]
  );

  // Compare workflows ignoring UI state fields
  const compareWorkflows = useCallback(
    (workflow1: Workflow | null, workflow2: Workflow | null): boolean => {
      if (!workflow1 || !workflow2) return false;

      const cleanWorkflow = (workflow: Workflow) => {
        const workflowCopy = JSON.parse(JSON.stringify(workflow));
        const { created_at, updated_at, ...remainingProps } = workflowCopy;
        return {
          ...remainingProps,
          nodes: (remainingProps.nodes || []).map(
            ({ selected, dragging, width, height, ...rest }: Node) => rest
          ),
          edges: (remainingProps.edges || []).map(
            ({ selected, ...rest }) => rest
          ),
        };
      };

      const cleanWorkflow1 = cleanWorkflow(workflow1);
      const cleanWorkflow2 = cleanWorkflow(workflow2);
      return !isEqual(cleanWorkflow1, cleanWorkflow2);
    },
    []
  );

  useEffect(() => {
    if (isSettling) {
      const timer = setTimeout(() => {
        const settledState = { ...workflow, nodes, edges } as Workflow;
        lastSavedWorkflowRef.current = JSON.parse(JSON.stringify(settledState));

        setIsSettling(false);
        setHasUnsavedChanges(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isSettling, nodes, edges, workflow]);

  useEffect(() => {
    if (isSettling || !lastSavedWorkflowRef.current) return;

    const currentWorkflowState = { ...workflow, nodes, edges } as Workflow;
    const hasChanged = compareWorkflows(
      lastSavedWorkflowRef.current,
      currentWorkflowState
    );
    setHasUnsavedChanges(hasChanged);
  }, [nodes, edges, workflow, isSettling, compareWorkflows]);

  // Clipboard for node copy/paste
  const clipboardRef = useRef<Node | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const loadWorkflow = useCallback(async (workflowId: string) => {
    const workflow = await getWorkflowById(workflowId);
    setWorkflow(workflow);
    handleWorkflowLoaded(workflow);
  }, []);

  const loadAgent = useCallback(
    async (agentId: string) => {
      const agent = await getAgentConfig(agentId);
      setAgent(agent);
      loadWorkflow(agent.workflow_id);
    },
    [loadWorkflow]
  );
  const handleAgentUpdated = useCallback(async () => {
    const agent = await getAgentConfig(agentId);
    setAgent(agent);
  }, [agentId]);

  const handleActiveWorkflowChange = useCallback(
    async (workflow: Workflow) => {
      if (agentId) {
        try {
          await updateAgentConfig(agentId, { workflow_id: workflow.id });
          await handleAgentUpdated();
        } catch (error) {
          // ignore
        }
      }
    },
    [agentId, handleAgentUpdated]
  );

  // Update node data (used for saving input values)
  const updateNodeData = useCallback(
    (nodeId: string, newData: Partial<NodeData>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: {
                ...node.data,
                ...newData,
              },
            };
          }
          return node;
        })
      );
    },
    [setNodes]
  );

  // Restore functions to nodes after loading
  const restoreNodeFunctions = (loadedNodes: Node[]): Node[] => {
    return loadedNodes.map((node) => {
      // Create a deep copy to avoid modifying the original
      const nodeCopy = { ...node, data: { ...node.data } };

      nodeCopy.data = {
        ...nodeCopy.data,
        updateNodeData,
      };

      return nodeCopy;
    });
  };

  // Handle graph data loaded from file
  const handleWorkflowLoaded = useCallback(
    (loadedWorkflow: Workflow, isUploaded = false) => {
      const nodesWithFunctions = restoreNodeFunctions(loadedWorkflow.nodes);

      // Add arrow markers to existing edges
      const edgesWithMarkers = loadedWorkflow.edges.map((edge) => ({
        ...edge,
        type: "default",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: "hsl(var(--brand-600))",
        },
        style: {
          strokeWidth: 2,
          stroke: "hsl(var(--brand-600))",
          strokeDasharray: "7,7",
        },
      }));

      setNodes(nodesWithFunctions);
      setEdges(edgesWithMarkers);
      setWorkflow(loadedWorkflow);

      if (!isUploaded) {
        setIsSettling(true);
        setHasUnsavedChanges(false);
      }
    },
    [restoreNodeFunctions, setNodes, setEdges, setWorkflow]
  );

  // Drag and drop handlers using helper functions
  const onDragOver = useCallback((event: React.DragEvent) => {
    handleDragOver(event);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      handleDrop(event, reactFlowInstance, restoreNodeFunctions, setNodes);
    },
    [reactFlowInstance, restoreNodeFunctions, setNodes]
  );

  useEffect(() => {
    if (agentId) {
      loadAgent(agentId);
    }
  }, [agentId, loadAgent]);

  // Connection handler with special handling for connections
  const onConnect = useCallback(
    (params: Connection) => {
      // Validate schema compatibility before allowing connection
      if (!validateConnection(params)) {
        return;
      }

      // Add arrow marker to the edge
      const edgeWithMarker = {
        ...params,
        type: "default",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: "hsl(var(--brand-600))",
        },
        style: {
          strokeWidth: 2,
          stroke: "hsl(var(--brand-600))",
          strokeDasharray: "7,7",
        },
      };

      setEdges((eds) => addEdge(edgeWithMarker, eds));
    },
    [setEdges, validateConnection]
  );

  const onReconnectStart = useCallback(() => {
    edgeReconnectSuccessful.current = false;
  }, []);
 
  const onReconnect = useCallback((oldEdge, newConnection) => {
    edgeReconnectSuccessful.current = true;
    setEdges((els) => reconnectEdge(oldEdge, newConnection, els));
  }, []);
 
  const onReconnectEnd = useCallback((_, edge) => {
    if (!edgeReconnectSuccessful.current) {
      setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    }
 
    edgeReconnectSuccessful.current = true;
  }, []);

  // Toggle panel functions
  const toggleNodePanel = () => {
    setShowNodePanel(!showNodePanel);
    if (showWorkflowPanel) setShowWorkflowPanel(false);
  };

  const toggleWorkflowPanel = () => {
    setShowWorkflowPanel(!showWorkflowPanel);
    if (showNodePanel) setShowNodePanel(false);
  };

  // Add updateNodeData callback to all nodes that need it
  useEffect(() => {
    setNodes((nds) => restoreNodeFunctions(nds));
  }, [setNodes]);

  // Add a new node
  const addNewNode = (
    nodeType: string,
    nodePosition?: { x: number; y: number }
  ) => {
    const id = uuidv4();
    const position = nodePosition ?? {
      x: Math.random() * 400 + 100,
      y: Math.random() * 300 + 100,
    };

    const newNode = nodeRegistry.createNode(nodeType, id, position);
    if (newNode) {
      // Add updateNodeData function to the node data if it's a node type that needs it

      const addedNodes = restoreNodeFunctions([newNode]);

      setNodes((nds) => [...nds, ...addedNodes]);
    }
  };

  useEffect(() => {
    if (executionState) {
      setWorkflow({ ...workflow, executionState });
    }
  }, [executionState]);

  const handleSaveWorkflow = async () => {
    if (!workflow) return;

    try {
      const updatedWorkflowData = {
        ...workflow,
        nodes: nodes,
        edges: edges,
      };

      await updateWorkflow(workflow.id, updatedWorkflowData);
      setWorkflow(updatedWorkflowData);
      lastSavedWorkflowRef.current = updatedWorkflowData;
      setHasUnsavedChanges(false);
      setRefreshKey((prevKey) => prevKey + 1);
    } catch (error) {
      // ignore
    }
  };
  const handleUpdateWorkflowTestInputs = (inputs: Record<string, string>) => {
    setWorkflow({ ...workflow, testInput: inputs });
  };

  // Handle test graph
  const handleTestGraph = (graphData: Workflow) => {
    setCurrentTestConfig(graphData);
    setTestDialogOpen(true);
  };

  // Handle selection change
  const onSelectionChange = useCallback(({ nodes: selectedNodes }) => {
    if (selectedNodes && selectedNodes.length === 1) {
      setSelectedNode(selectedNodes[0]);
    } else {
      setSelectedNode(null);
    }
  }, []);

  // Keyboard event handlers for copy/paste
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle copy/paste if ReactFlow canvas is focused
      const target = e.target as HTMLElement;
      const isReactFlowCanvas =
        target.closest(".react-flow__viewport") ||
        target.closest(".react-flow__pane") ||
        target.closest(".react-flow__renderer");

      if (!isReactFlowCanvas) {
        return;
      }

      // Copy (Ctrl+C or Cmd+C)
      if ((e.ctrlKey || e.metaKey) && e.key === "c") {
        if (selectedNode) {
          e.preventDefault(); // Prevent default browser copy
          clipboardRef.current = { ...selectedNode };
        }
      }
      // Paste (Ctrl+V or Cmd+V)
      if ((e.ctrlKey || e.metaKey) && e.key === "v") {
        if (clipboardRef.current) {
          e.preventDefault(); // Prevent default browser paste
          const copiedNode = clipboardRef.current;
          // Create a new node with a new ID and offset position
          const newId = uuidv4();
          const offset = 40;
          const newPosition = {
            x: (copiedNode.position?.x || 0) + offset,
            y: (copiedNode.position?.y || 0) + offset,
          };
          // Remove selected, parent, and source/target handles if present
          const { id, selected, position, ...rest } = copiedNode;
          const newNode: Node = {
            ...rest,
            id: newId,
            position: newPosition,
            data: {
              ...copiedNode.data,
              // If updateNodeData is a function, keep it
              updateNodeData: copiedNode.data?.updateNodeData,
            },
            selected: false,
          };
          setNodes((nds) => [...nds, newNode]);
          // Clear the clipboard after pasting
          clipboardRef.current = null;
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedNode, setNodes]);

  return (
    <WorkflowProvider workflow={workflow} setWorkflow={setWorkflow}>
      <WorkflowExecutionProvider>
        <div className="h-full w-full flex flex-col">
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-4 left-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md"
            onClick={toggleSidebar}
          >
            <PanelLeft className="h-4 w-4" />
            <span className="sr-only">Toggle Sidebar</span>
          </Button>
          <div className="flex-1 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              minZoom={0.1}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onInit={setReactFlowInstance}
              fitView
              onSelectionChange={onSelectionChange}
              onDragOver={onDragOver}
              onDrop={onDrop}
              onNodeDoubleClick={onNodeDoubleClick}
              onReconnect={onReconnect}
              onReconnectStart={onReconnectStart}
              onReconnectEnd={onReconnectEnd}
              proOptions={{ hideAttribution: true }} // remove React Flow watermark
            >
              <Background />
              <Controls />
              <Panel position="top-center" className="mt-2">
                <AgentTopPanel data={agent} onUpdated={handleAgentUpdated} />
              </Panel>

              <Panel position="bottom-center" className="mb-4">
                <BottomPanel
                  workflow={{
                    ...workflow,
                    nodes: nodes,
                    edges: edges,
                  }}
                  hasUnsavedChanges={hasUnsavedChanges}
                  onWorkflowLoaded={(workflow) =>
                    handleWorkflowLoaded(workflow, true)
                  }
                  onTestWorkflow={handleTestGraph}
                  onSaveWorkflow={handleSaveWorkflow}
                  onExecutionStateChange={setExecutionState}
                />
              </Panel>
              <Panel
                position="top-right"
                className="mt-20 mr-2 flex flex-col gap-2"
              >
                {!showNodePanel && !showWorkflowPanel && (
                  <>
                    <Button
                      onClick={toggleNodePanel}
                      size="icon"
                      variant="secondary"
                      className="rounded-full h-10 w-10 shadow-md"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      onClick={toggleWorkflowPanel}
                      size="icon"
                      variant="secondary"
                      className="rounded-full h-10 w-10 shadow-md"
                    >
                      <FolderOpen className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </Panel>
            </ReactFlow>

            <NodePanel
              isOpen={showNodePanel}
              onClose={toggleNodePanel}
              onAddNode={addNewNode}
            />

            <WorkflowsSavedPanel
              isOpen={showWorkflowPanel}
              onClose={toggleWorkflowPanel}
              agentId={agentId}
              activeWorkflowId={agent?.workflow_id}
              currentWorkflow={{
                ...workflow,
                nodes: nodes,
                edges: edges,
              }}
              onWorkflowSelect={handleWorkflowLoaded}
              onActiveWorkflowChange={handleActiveWorkflowChange}
              refreshKey={refreshKey}
              hasUnsavedChanges={hasUnsavedChanges}
              onSaveWorkflow={handleSaveWorkflow}
            />

            <WorkflowTestDialog
              isOpen={testDialogOpen}
              onClose={() => setTestDialogOpen(false)}
              workflowName="Current Graph"
              workflow={currentTestConfig}
              onUpdateWorkflowTestInputs={handleUpdateWorkflowTestInputs}
            />
          </div>
        </div>
      </WorkflowExecutionProvider>
    </WorkflowProvider>
  );
};

export default GraphFlowContent;

const GraphFlow: React.FC = () => {
  return (
    <WorkflowExecutionProvider>
      <GraphFlowContent />
    </WorkflowExecutionProvider>
  );
};

export { GraphFlow };

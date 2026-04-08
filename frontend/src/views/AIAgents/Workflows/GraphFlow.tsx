import React, { useCallback, useState, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
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
import ChatInputBar from "./components/panels/ChatInputBar";
import { useSchemaValidation } from "./hooks/useSchemaValidation";
import { useUndoRedo } from "./hooks/useUndoRedo";
import { AgentConfig, getAgentConfig, updateAgentConfig } from "@/services/api";
import { useParams } from "react-router-dom";
import { getWorkflowById, updateWorkflow } from "@/services/workflows";
import AgentTopPanel from "./components/panels/AgentTopPanel";
import { v4 as uuidv4 } from "uuid";
import { WorkflowProvider } from "./context/WorkflowContext";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import {
  WorkflowExecutionProvider,
  WorkflowExecutionState,
} from "./context/WorkflowExecutionContext";
import {
  handleDragOver,
  handleDrop,
  handleNodeDoubleClick,
} from "./utils/helpers";
import { Button } from "@/components/button";
import { History, ChevronLeft, X, Plus } from "lucide-react";
import CanvasContextMenu from "./components/CanvasContextMenu";
import CustomControls from "./components/CustomControls";

// Get node types and edge types for React Flow
const nodeTypes = getNodeTypes();
const edgeTypes = getEdgeTypes();

const GraphFlowContent: React.FC = () => {
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  const showChatInput = useFeatureFlagVisible(FeatureFlags.WORKFLOW.CHAT_INPUT);

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

  // Interactive state for lock/unlock functionality
  const [nodesDraggable, setNodesDraggable] = useState(true);
  const [nodesConnectable, setNodesConnectable] = useState(true);
  const [elementsSelectable, setElementsSelectable] = useState(true);

  // Context menu state
  const [contextMenuPosition, setContextMenuPosition] = useState<{ x: number; y: number } | null>(null);

  // Prevent body scroll on Agent Studio page
  useEffect(() => {
    // Always hide overflow on the body when on Agent Studio page
    document.body.style.overflow = 'hidden';
    
    // Cleanup on unmount - restore default overflow
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  const { validateConnection } = useSchemaValidation();

  // Undo/Redo functionality
  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo(
    nodes,
    edges,
    setNodes,
    setEdges
  );

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

  // Clipboard for node copy/paste (supports multi-node + edges)
  const clipboardRef = useRef<{ nodes: Node[]; edges: typeof edges } | null>(null);
  const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);

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
    setShowNodePanel(false);
    setTestDialogOpen(true);
  };

  // Handle selection change
  const onSelectionChange = useCallback(({ nodes: selNodes }) => {
    setSelectedNodes(selNodes || []);

    if (selNodes && selNodes.length >= 1) {
      // Add animated-edge class to edges connected to any selected node
      const selectedIds = new Set(selNodes.map((n: Node) => n.id));
      setEdges((eds) =>
        eds.map((edge) => {
          const isConnected =
            selectedIds.has(edge.source) || selectedIds.has(edge.target);
          return {
            ...edge,
            className: isConnected ? 'animated-edge' : '',
          };
        })
      );
    } else {
      // Remove animated-edge class from all edges
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          className: '',
        }))
      );
    }
  }, [setEdges]);

  // Take snapshot when nodes or edges change (for undo/redo)
  useEffect(() => {
    if (!isSettling) {
      takeSnapshot();
    }
  }, [nodes, edges, isSettling, takeSnapshot]);

  // Handler for adding nodes from context menu
  const handleAddNodeFromContextMenu = useCallback(
    (nodeType: string, position: { x: number; y: number }) => {
      addNewNode(nodeType, position);
      setContextMenuPosition(null);
    },
    [addNewNode]
  );

  // Handler for right-click on canvas (capture position without preventing default)
  const handleCanvasContextMenu = useCallback(
    (event: React.MouseEvent) => {
      if (reactFlowInstance) {
        const flowPosition = reactFlowInstance.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
        setContextMenuPosition(flowPosition);
      }
    },
    [reactFlowInstance]
  );

  // Keyboard event handlers for copy/paste/undo/redo
  // Copy selected nodes and their internal edges to clipboard
  const copySelectedNodes = useCallback(() => {
    if (selectedNodes.length === 0) return;

    const selectedIds = new Set(selectedNodes.map((n) => n.id));
    const connectedEdges = edges.filter(
      (edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target)
    );

    clipboardRef.current = {
      nodes: selectedNodes.map((n) => ({ ...n })),
      edges: connectedEdges.map((e) => ({ ...e })),
    };
  }, [selectedNodes, edges]);

  // Paste nodes and edges from clipboard with new IDs
  const pasteFromClipboard = useCallback(() => {
    if (!clipboardRef.current || clipboardRef.current.nodes.length === 0) return;

    const { nodes: copiedNodes, edges: copiedEdges } = clipboardRef.current;
    const offset = 40;

    const idMap = new Map<string, string>();
    copiedNodes.forEach((node) => idMap.set(node.id, uuidv4()));

    const newNodes: Node[] = copiedNodes.map((node) => {
      const { id, selected, position, ...rest } = node;
      return {
        ...rest,
        id: idMap.get(id)!,
        position: {
          x: (position?.x || 0) + offset,
          y: (position?.y || 0) + offset,
        },
        data: {
          ...node.data,
          updateNodeData: node.data?.updateNodeData,
        },
        selected: false,
      };
    });

    const newEdges = copiedEdges.map((edge) => ({
      ...edge,
      id: uuidv4(),
      source: idMap.get(edge.source)!,
      target: idMap.get(edge.target)!,
      selected: false,
      className: '',
    }));

    setNodes((nds) => [...nds, ...newNodes]);
    setEdges((eds) => [...eds, ...newEdges]);
    clipboardRef.current = null;
  }, [setNodes, setEdges]);

  // Keyboard shortcuts for canvas interactions
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isReactFlowCanvas =
        target.closest(".react-flow__viewport") ||
        target.closest(".react-flow__pane") ||
        target.closest(".react-flow__renderer");

      if (!isReactFlowCanvas) return;

      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "z") {
        e.preventDefault();
        redo();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "c") {
        e.preventDefault();
        copySelectedNodes();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "v") {
        e.preventDefault();
        pasteFromClipboard();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [copySelectedNodes, pasteFromClipboard, undo, redo]);

  return (
    <WorkflowProvider workflow={workflow} setWorkflow={setWorkflow}>
      <WorkflowExecutionProvider>
        <div className="h-full w-full flex flex-col">
          <div className="flex-1 relative">
            <CanvasContextMenu
              onAddNode={handleAddNodeFromContextMenu}
              onUndo={undo}
              onRedo={redo}
              canUndo={canUndo}
              canRedo={canRedo}
              clickPosition={contextMenuPosition}
            >
              <div
                onContextMenu={handleCanvasContextMenu}
                className="h-full w-full"
              >
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
                  nodesDraggable={nodesDraggable}
                  nodesConnectable={nodesConnectable}
                  elementsSelectable={elementsSelectable}
                  proOptions={{ hideAttribution: true }} // remove React Flow watermark
                >
                  <Background />
                  <CustomControls
                    nodesDraggable={nodesDraggable}
                    nodesConnectable={nodesConnectable}
                    elementsSelectable={elementsSelectable}
                    onNodesDraggableChange={setNodesDraggable}
                    onNodesConnectableChange={setNodesConnectable}
                    onElementsSelectableChange={setElementsSelectable}
                  />
                  <Panel position="top-center" className="mt-4">
                    <AgentTopPanel data={agent} onUpdated={handleAgentUpdated} />
                  </Panel>
                </ReactFlow>
              </div>
            </CanvasContextMenu>

            {/* Unified top-right controls (prevents overlap between ReactFlow Panel + NodePanel buttons) */}
            <div
              className={`fixed top-2 z-20 flex flex-row flex-wrap items-center justify-end gap-2 max-w-[calc(100vw-1rem)] transition-[right] duration-300 ${
                (() => {
                  if (showNodePanel && showWorkflowPanel) {
                    return "right-[calc(360px+20rem+1rem)]";
                  } else if (showNodePanel) {
                    return "right-[calc(360px+1rem)]";
                  } else if (showWorkflowPanel) {
                    return "right-[calc(20rem+1rem)]";
                  } else {
                    return "right-2";
                  }
                })()
              }`}
            >
              <BottomPanel
                workflow={{
                  ...workflow,
                  nodes: nodes,
                  edges: edges,
                }}
                hasUnsavedChanges={hasUnsavedChanges}
                onWorkflowLoaded={(workflow) => handleWorkflowLoaded(workflow, true)}
                onTestWorkflow={handleTestGraph}
                onSaveWorkflow={handleSaveWorkflow}
                onExecutionStateChange={setExecutionState}
                onToggleWorkflowPanel={toggleWorkflowPanel}
              />

              <Button
                onClick={toggleNodePanel}
                size="icon"
                variant="ghost"
                className="rounded-full h-10 w-10 shadow-md bg-white hover:bg-gray-50"
              >
                {showNodePanel ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                <span className="sr-only">
                  {showNodePanel ? "Close Node Panel" : "Open Node Panel"}
                </span>
              </Button>
            </div>

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

            {showChatInput && (
              <ChatInputBar
                onSendMessage={(message) => {
                  // Open test dialog with the message pre-filled
                  setCurrentTestConfig({
                    ...workflow,
                    nodes: nodes,
                    edges: edges,
                    testInput: { message },
                  });
                  setShowNodePanel(false);
                  setTestDialogOpen(true);
                }}
                disabled={!workflow?.nodes?.some((node) => node.type === "chatInputNode")}
              />
            )}
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

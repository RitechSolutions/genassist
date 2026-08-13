import React, { useCallback, useState, useEffect, useRef, useMemo } from "react";
import ReactFlow, {
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  Panel,
  ReactFlowInstance,
  NodeMouseHandler,
  MarkerType,
  reconnectEdge,
  useStore,
} from "reactflow";
import "reactflow/dist/style.css";
import { isEqual } from "lodash";
import { stripTransientGraphFields } from "./utils/graphNormalization";
import { getNodeTypes } from "./nodeTypes";
import { getEdgeTypes } from "./edgeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { NodeData } from "./types/nodes";
import { Workflow } from "@/interfaces/workflow.interface";
import WorkflowTestPanel, { TestRunRecord } from "./components/WorkflowTestPanel";
import WorkflowEvaluationsTab from "./components/WorkflowEvaluationsTab";
import NodePanel from "./components/panels/NodePanel";
import BottomPanel from "./components/panels/BottomPanel";
import WorkflowsSavedPanel from "./components/panels/WorkflowsSavedPanel";
import { useCanvasAssistant } from "./hooks/useCanvasAssistant";
import { useSchemaValidation } from "./hooks/useSchemaValidation";
import { useUndoRedo } from "./hooks/useUndoRedo";
import { AgentConfig, getAgentConfig, updateAgentConfig } from "@/services/api";
import { useParams, useSearchParams } from "react-router-dom";
import { getWorkflowById, updateWorkflow } from "@/services/workflows";
import AgentTopPanel from "./components/panels/AgentTopPanel";
import { v4 as uuidv4 } from "uuid";
import { WorkflowProvider } from "./context/WorkflowContext";
import { NodeActionsContext } from "./context/NodeActionsContext";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import { usePermissions } from "@/context/PermissionContext";
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
import { useSidebar } from "@/components/sidebar";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { History, ChevronLeft, X, Plus, Workflow as WorkflowIcon, Play, ClipboardCheck } from "lucide-react";
import CanvasContextMenu from "./components/CanvasContextMenu";
import CustomControls from "./components/CustomControls";
import { computeAutoArrangeLayout } from "./utils/autoArrangeLayout";
import { validateSubAgentConnection } from "./utils/subAgentGraph";
import toast from "react-hot-toast";
import WorkflowCommandPalette from "./components/WorkflowCommandPalette";
import { SetupWizardPanel, SetupWizardReopenButton } from "./components/panels/SetupWizardPanel";
import { getAllAppSettings } from "@/services/appSettings";
import { getAllDataSources } from "@/services/dataSources";
import { getAllNodeSchemas } from "@/services/workflows";
import type { AppSetting } from "@/interfaces/app-setting.interface";
import type { DataSource } from "@/interfaces/dataSource.interface";
import type { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import WorkflowMiniMap from "./components/WorkflowMiniMap";

// Get node types and edge types for React Flow
const nodeTypes = getNodeTypes();
const edgeTypes = getEdgeTypes();

const PRO_OPTIONS = { hideAttribution: true }; // remove React Flow watermark

// Skip canvas undo/redo when focus is in a field the user is typing in
const isEditableEventTarget = (target: HTMLElement): boolean =>
  target.isContentEditable ||
  !!target.closest("input, textarea, select, [contenteditable='true'], .ace_editor");

// --- Level-of-detail (LOD) ---------------------------------------------------
// When the canvas is zoomed out over a large graph, paint-heavy node/edge effects
// (drop shadows, the spinning AI-agent gradient border, edge dash animations) make
// panning/dragging janky — worst on Safari, but this helps every browser. We drop
// those effects via a `.rf-low-detail` class on the flow root (see index.css) and
// restore full detail automatically once the user zooms back in.
const LOW_DETAIL_ZOOM = 0.7; // simplify below this zoom level
const LOW_DETAIL_MIN_NODES = 15; // ...but only once the graph is big enough to matter

// Reads zoom + node count straight from the React Flow store and reports whether we
// should render in low-detail mode. Because the selector returns a boolean, this only
// triggers a re-render when the mode actually flips — not on every zoom/pan frame.
const LowDetailWatcher: React.FC<{ onChange: (lowDetail: boolean) => void }> = ({
  onChange,
}) => {
  const lowDetail = useStore(
    (s) =>
      s.nodeInternals.size >= LOW_DETAIL_MIN_NODES &&
      s.transform[2] < LOW_DETAIL_ZOOM
  );
  useEffect(() => {
    onChange(lowDetail);
  }, [lowDetail, onChange]);
  return null;
};

// When replacing a node, pick which handle on the NEW node the old node's edges
// should reconnect to. Prefer the standard "output"/"input" ids; otherwise fall
// back to the first source/target handler the node defines (some nodes use
// non-standard handle ids), and finally to the standard id as a last resort.
const pickReplacementHandle = (
  node: Node,
  handleType: "source" | "target"
): string | undefined => {
  const handlers = (node.data?.handlers ?? []) as Array<{
    id: string;
    type: string;
  }>;
  const preferred = handleType === "source" ? "output" : "input";
  if (handlers.some((h) => h.type === handleType && h.id === preferred)) {
    return preferred;
  }
  return handlers.find((h) => h.type === handleType)?.id ?? preferred;
};

const GraphFlowContent: React.FC = () => {
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  const showChatInput = useFeatureFlagVisible(FeatureFlags.WORKFLOW.CHAT_INPUT);

  // Sidebar state — when collapsed, a floating toggle button sits at the
  // top-left of the viewport; shift the tab switcher right to clear it.
  const { state: sidebarState } = useSidebar();

  const [workflow, setWorkflow] = useState<Workflow>();
  const [agent, setAgent] = useState<AgentConfig>();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [showNodePanel, setShowNodePanel] = useState(false);
  const [showWorkflowPanel, setShowWorkflowPanel] = useState(false);
  // When set, the Available Nodes sidebar is in "replace" mode: picking a node
  // there swaps this node instead of adding a new one.
  const [replaceTargetId, setReplaceTargetId] = useState<string | null>(null);
  const [currentTestConfig, setCurrentTestConfig] = useState<Workflow | null>(
    null
  );
  // Which top-level view is showing: the graph editor, the executions/test page,
  // or the evaluations list for this workflow.
  // Switching is a local toggle (not a route) so the live graph stays mounted.
  const [activeTab, setActiveTab] = useState<
    "workflow" | "executions" | "evaluations"
  >("workflow");
  // The evaluations API needs test:workflow (the builder itself only needs
  // read:llm_analyst), so a workflow editor may still lack eval access.
  const permissions = usePermissions();
  const canEvaluate =
    permissions.includes("*") || permissions.includes("test:workflow");
  // In-memory history of test runs (newest first). Lives here so it survives
  // switching between the Workflow/Executions tabs; cleared on page leave/refresh.
  const [testHistory, setTestHistory] = useState<TestRunRecord[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const lastSavedWorkflowRef = useRef<Workflow | null>(null);
  const [isSettling, setIsSettling] = useState(true);
  const [executionState, setExecutionState] = useState<WorkflowExecutionState | null>(null);

  // Interactive state for lock/unlock functionality
  const [nodesDraggable, setNodesDraggable] = useState(true);
  const [nodesConnectable, setNodesConnectable] = useState(true);
  const [elementsSelectable, setElementsSelectable] = useState(true);

  // Level-of-detail: true when zoomed out over a large graph (see LowDetailWatcher)
  const [lowDetail, setLowDetail] = useState(false);

  // Minimap auto-reveal — the minimap stays hidden until the user moves around the
  // canvas, then fades back out after a short idle (see revealMinimap below).
  const [minimapVisible, setMinimapVisible] = useState(false);
  const minimapHideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Context menu state
  const [contextMenuPosition, setContextMenuPosition] = useState<{ x: number; y: number } | null>(null);

  // Node search state (spotlight search — opened via ⌘K / Ctrl+K or "/")
  const [nodeSearchOpen, setNodeSearchOpen] = useState(false);
  const [nodeSearchQuery, setNodeSearchQuery] = useState("");
  // When true the overlay is in "agent" mode (an /agent badge + messages go to the AI assistant)
  const [nodeSearchAgentMode, setNodeSearchAgentMode] = useState(false);

  // Setup wizard — show when arriving from onboarding workflow creation
  const [searchParams, setSearchParams] = useSearchParams();
  const isSetupFlow = searchParams.get("setup") === "true";
  const [showSetupWizard, setShowSetupWizard] = useState(isSetupFlow);
  const [wizardWasShown] = useState(isSetupFlow);

  // Clean up the ?setup=true param from URL without navigation
  useEffect(() => {
    if (searchParams.get("setup") === "true") {
      searchParams.delete("setup");
      setSearchParams(searchParams, { replace: true });
    }
  }, []);

  /** Focus a node on the canvas and open its config dialog (used by setup wizard) */
  const handleNodeFocus = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node || !reactFlowInstance) return;

      // Center the viewport on the node
      reactFlowInstance.setCenter(
        node.position.x + (node.width ?? 200) / 2,
        node.position.y + (node.height ?? 100) / 2,
        { zoom: 1.2, duration: 400 }
      );

      // Select the node
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          selected: n.id === nodeId,
        }))
      );

      // After the viewport animation, click the node's settings button to open its config dialog
      setTimeout(() => {
        const nodeEl = document.querySelector(`[data-id="${nodeId}"]`);
        const settingsBtn = nodeEl?.querySelector<HTMLButtonElement>("[data-node-settings]");
        settingsBtn?.click();
      }, 450);
    },
    [nodes, reactFlowInstance, setNodes]
  );

  /** Arrange every node into a clean left-to-right layout (see utils/autoArrangeLayout). */
  const handleAutoArrange = useCallback(() => {
    const positions = computeAutoArrangeLayout({ nodes, edges });
    setNodes((nds) =>
      nds.map((n) => (positions[n.id] ? { ...n, position: positions[n.id] } : n))
    );
    // Fit the view after react-flow commits the new positions.
    requestAnimationFrame(() => reactFlowInstance?.fitView({ padding: 0.2, duration: 400 }));
  }, [nodes, edges, setNodes, reactFlowInstance]);

  // Smart defaults — dynamically auto-fill integration nodes using schemas + existing connections
  const smartDefaultsApplied = useRef(false);
  useEffect(() => {
    if (!showSetupWizard || smartDefaultsApplied.current || nodes.length === 0) return;
    smartDefaultsApplied.current = true;

    const applySmartDefaults = async () => {
      try {
        const [appSettings, dataSources, nodeSchemas] = await Promise.all([
          getAllAppSettings(),
          getAllDataSources(),
          getAllNodeSchemas(),
        ]);

        const activeSettings = appSettings.filter((s: AppSetting) => s.is_active === 1);
        const activeSources = dataSources.filter((s: DataSource) => s.is_active === 1);

        // Match a node type name to an AppSetting type (e.g. "slackMessageNode" → "Slack")
        const findMatchingSettingId = (nodeType: string): string | undefined => {
          const lower = nodeType.toLowerCase();
          for (const setting of activeSettings) {
            if (lower.includes(setting.type.toLowerCase())) {
              return setting.id;
            }
          }
          return undefined;
        };

        // Match a node type name to a connected DataSource (e.g. "gmailNode" → gmail source)
        const findMatchingDataSourceId = (nodeType: string): string | undefined => {
          const lower = nodeType.toLowerCase();
          for (const source of activeSources) {
            if (lower.includes(source.source_type.toLowerCase())) {
              return source.id;
            }
          }
          return undefined;
        };

        let updated = false;
        setNodes((nds) =>
          nds.map((node) => {
            const nodeType = node.type ?? "";
            const schema = nodeSchemas[nodeType] as FieldSchema[] | undefined;
            if (!schema) return node;

            const data = node.data as Record<string, unknown>;
            const patch: Record<string, string> = {};

            for (const field of schema) {
              // Only auto-fill empty required select fields
              if (!field.required || field.type !== "select") continue;
              const current = data[field.name];
              if (current && typeof current === "string" && current.trim() !== "") continue;

              if (field.name === "app_settings_id") {
                const id = findMatchingSettingId(nodeType);
                if (id) patch[field.name] = id;
              } else if (field.name === "dataSourceId") {
                const id = findMatchingDataSourceId(nodeType);
                if (id) patch[field.name] = id;
              }
            }

            if (Object.keys(patch).length === 0) return node;

            updated = true;
            return { ...node, data: { ...data, ...patch } };
          })
        );

        if (updated) {
          setHasUnsavedChanges(true);
        }
      } catch {
        // ignore — smart defaults are best-effort
      }
    };

    applySmartDefaults();
  }, [showSetupWizard, nodes.length]);

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
        const { nodes, edges } = stripTransientGraphFields(
          remainingProps.nodes || [],
          remainingProps.edges || []
        );
        return { ...remainingProps, nodes, edges };
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

        // The <ReactFlow fitView> prop only fits at mount — before async-loaded nodes exist — so
        // a freshly opened workflow (whose nodes can sit at large coordinates) renders off-screen.
        // Frame it now that its nodes have loaded.
        if (nodes.length > 0) reactFlowInstance?.fitView({ padding: 0.2 });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isSettling, nodes, edges, workflow, reactFlowInstance]);

  useEffect(() => {
    if (isSettling || !lastSavedWorkflowRef.current) return;

    const timer = setTimeout(() => {
      const currentWorkflowState = { ...workflow, nodes, edges } as Workflow;
      const hasChanged = compareWorkflows(
        lastSavedWorkflowRef.current,
        currentWorkflowState
      );
      setHasUnsavedChanges(hasChanged);
    }, 300);

    return () => clearTimeout(timer);
  }, [nodes, edges, workflow, isSettling, compareWorkflows]);

  // Clipboard for node copy/paste (supports multi-node + edges)
  const clipboardRef = useRef<{ nodes: Node[]; edges: typeof edges } | null>(null);
  const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);

  // Always-current snapshot of nodes, so the per-node action callbacks below can
  // read the latest node without listing `nodes` in their deps (which would
  // change their identity on every drag and re-render every node).
  const nodesRef = useRef(nodes);
  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);
  // Same trick for edges/workflow so canvas-level node actions (e.g. the Start
  // node's inline Test) can read the latest graph without re-subscribing.
  const edgesRef = useRef(edges);
  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);
  const workflowRef = useRef(workflow);
  useEffect(() => {
    workflowRef.current = workflow;
  }, [workflow]);

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

  // Canvas AI assistant
  const [conversationalTabActive, setConversationalTabActive] = useState(false);
  const [hasStartedConversation, setHasStartedConversation] = useState(false);
  const assistant = useCanvasAssistant({
    nodes,
    edges,
    setNodes,
    setEdges,
    updateNodeData,
    workflowScopeId: agentId,
  });

  // Restore functions to nodes after loading
  const restoreNodeFunctions = useCallback(
    (loadedNodes: Node[]): Node[] => {
      return loadedNodes.map((node) => {
        const hydrated = nodeRegistry.hydrateNode(node);
        return {
          ...hydrated,
          data: {
            ...hydrated.data,
            updateNodeData,
          },
        };
      });
    },
    [updateNodeData]
  );

  // Undo/Redo functionality
  const { undo, redo, canUndo, canRedo, takeSnapshot, resetHistory } =
    useUndoRedo(nodes, edges, setNodes, setEdges, {
      hydrateNodes: restoreNodeFunctions,
    });

  // Handle graph data loaded from file
  const handleWorkflowLoaded = useCallback(
    (loadedWorkflow: Workflow, isUploaded = false) => {
      const loadedNodes = loadedWorkflow.nodes || [];
      const loadedEdges = loadedWorkflow.edges || [];
      const nodesWithFunctions = restoreNodeFunctions(loadedNodes);

      // Add arrow markers to existing edges
      const edgesWithMarkers = loadedEdges.map((edge) => ({
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

      // Reset undo baseline to the loaded graph and discard any existing history
      resetHistory({ nodes: nodesWithFunctions, edges: edgesWithMarkers });
      setNodes(nodesWithFunctions);
      setEdges(edgesWithMarkers);
      setWorkflow(loadedWorkflow);

      if (!isUploaded) {
        setIsSettling(true);
        setHasUnsavedChanges(false);
      }
    },
    [resetHistory, restoreNodeFunctions, setNodes, setEdges, setWorkflow]
  );

  const loadWorkflow = useCallback(
    async (workflowId: string) => {
      const workflow = await getWorkflowById(workflowId);
      setWorkflow(workflow);
      handleWorkflowLoaded(workflow);
    },
    [handleWorkflowLoaded, setWorkflow]
  );

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

  // One gate for connect, reconnect, and assistant edges
  const checkConnection = useCallback(
    (params: Connection, ignoreEdgeId?: string): { ok: boolean; reason?: string } => {
      if (!validateConnection(params)) {
        return { ok: false };
      }
      const scopedEdges = ignoreEdgeId ? edges.filter((e) => e.id !== ignoreEdgeId) : edges;
      return validateSubAgentConnection(params, nodes, scopedEdges);
    },
    [validateConnection, nodes, edges]
  );

  // Connection handler with special handling for connections
  const onConnect = useCallback(
    (params: Connection) => {
      const check = checkConnection(params);
      if (!check.ok) {
        if (check.reason) toast.error(check.reason);
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
    [setEdges, checkConnection]
  );

  const onReconnectStart = useCallback(() => {
    edgeReconnectSuccessful.current = false;
  }, []);

  const onReconnect = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      const check = checkConnection(newConnection, oldEdge.id);
      if (!check.ok) {
        if (check.reason) toast.error(check.reason);
        edgeReconnectSuccessful.current = true;
        return;
      }
      edgeReconnectSuccessful.current = true;
      setEdges((els) => reconnectEdge(oldEdge, newConnection, els));
    },
    [setEdges, checkConnection]
  );

  const onReconnectEnd = useCallback((_, edge) => {
    if (!edgeReconnectSuccessful.current) {
      setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    }

    edgeReconnectSuccessful.current = true;
  }, []);

  // --- Minimap auto-reveal ---------------------------------------------------
  // Show the minimap the moment the user moves around the canvas, then fade it
  // back out ~1.5s after they stop. Keeps the corner clear while idle but gives
  // an overview the instant you start navigating.
  const revealMinimap = useCallback(() => {
    setMinimapVisible(true);
    if (minimapHideTimer.current) clearTimeout(minimapHideTimer.current);
    minimapHideTimer.current = setTimeout(() => setMinimapVisible(false), 1500);
  }, []);

  // onMove also fires for programmatic viewport changes (initial fitView, auto-arrange,
  // search focus, zoom buttons), which pass a null sourceEvent — ignore those so the
  // minimap only reacts to real user pans/zooms and never flashes on load.
  const handleCanvasMove = useCallback(
    (event: MouseEvent | TouchEvent | null) => {
      if (event) revealMinimap();
    },
    [revealMinimap]
  );

  // Clear any pending hide timer on unmount.
  useEffect(
    () => () => {
      if (minimapHideTimer.current) clearTimeout(minimapHideTimer.current);
    },
    []
  );

  // Toggle panel functions
  const toggleNodePanel = () => {
    setShowNodePanel(!showNodePanel);
    if (showWorkflowPanel) setShowWorkflowPanel(false);
    // Leaving/reopening the panel manually exits replace mode.
    if (replaceTargetId) setReplaceTargetId(null);
  };

  const toggleWorkflowPanel = () => {
    setShowWorkflowPanel(!showWorkflowPanel);
    if (showNodePanel) setShowNodePanel(false);
  };

  // Add updateNodeData callback to all nodes that need it
  useEffect(() => {
    setNodes((nds) => restoreNodeFunctions(nds));
  }, [restoreNodeFunctions, setNodes]);

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

  // Cap the in-memory history so a long session doesn't grow unbounded.
  const handleAddTestRun = useCallback((record: TestRunRecord) => {
    setTestHistory((prev) => [record, ...prev].slice(0, 50));
  }, []);
  const handleClearTestHistory = useCallback(() => setTestHistory([]), []);

  // Snapshot the current graph into the test config so the Executions page tests
  // exactly what's on the canvas, then switch to the Executions tab.
  const openExecutions = (graphData: Workflow) => {
    setCurrentTestConfig(graphData);
    setShowNodePanel(false);
    setShowWorkflowPanel(false);
    setActiveTab("executions");
  };

  // "Test" buttons (bottom panel, setup wizard) now open the Executions page.
  const handleTestGraph = (graphData: Workflow) => {
    openExecutions(graphData);
  };

  // Tab switch between the graph editor, executions/test page, and evaluations.
  const handleTabChange = (tab: string) => {
    if (tab === "executions") {
      // Re-snapshot the live graph on entry so the test always reflects the
      // current canvas, and close editor-only drawers.
      openExecutions({ ...workflow, nodes, edges } as Workflow);
    } else if (tab === "evaluations") {
      setShowNodePanel(false);
      setShowWorkflowPanel(false);
      setActiveTab("evaluations");
    } else {
      setActiveTab("workflow");
    }
  };

  // Handle selection change — highlight edges connected to any selected node.
  // Only edges whose className actually toggles get a new object reference; the
  // rest keep their identity so they don't re-render, and if nothing changed we
  // return the same array so React bails out of the state update entirely.
  const onSelectionChange = useCallback(({ nodes: selNodes }) => {
    setSelectedNodes(selNodes || []);

    const selectedIds = new Set((selNodes || []).map((n: Node) => n.id));
    setEdges((eds) => {
      let changed = false;
      const next = eds.map((edge) => {
        const isConnected =
          selectedIds.size >= 1 &&
          (selectedIds.has(edge.source) || selectedIds.has(edge.target));
        const nextClassName = isConnected ? 'animated-edge' : '';
        // Treat undefined/'' as equivalent so untouched edges keep their reference.
        if ((edge.className || '') === nextClassName) return edge;
        changed = true;
        return { ...edge, className: nextClassName };
      });
      return changed ? next : eds;
    });
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

  // --- Per-node actions (exposed to nodes via NodeActionsContext) ------------

  // Copy a single node to the clipboard; paste it with Cmd/Ctrl+V.
  const copyNode = useCallback((id: string) => {
    const node = nodesRef.current.find((n) => n.id === id);
    if (!node) return;
    clipboardRef.current = { nodes: [{ ...node }], edges: [] };
  }, []);

  // Duplicate a single node in place (offset, without its edges) and select it.
  const duplicateNode = useCallback(
    (id: string) => {
      setNodes((nds) => {
        const original = nds.find((n) => n.id === id);
        if (!original) return nds;
        const offset = 40;
        const { position } = original;
        const clone: Node = {
          ...original,
          id: uuidv4(),
          position: {
            x: (position?.x || 0) + offset,
            y: (position?.y || 0) + offset,
          },
          data: { ...original.data, updateNodeData },
          selected: true,
        };
        return [
          ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
          clone,
        ];
      });
    },
    [setNodes, updateNodeData]
  );

  // Replace an existing node with a fresh node of `newType`, in place: keep the
  // same position and reconnect the replaced node's incoming/outgoing edges to
  // the new node's input/output handles. Config is not carried across types.
  const replaceNode = useCallback(
    (targetId: string, newType: string) => {
      const target = nodesRef.current.find((n) => n.id === targetId);
      if (!target) return;
      const newId = uuidv4();
      const created = nodeRegistry.createNode(newType, newId, target.position);
      if (!created) return;
      const [restored] = restoreNodeFunctions([created]);

      const newSourceHandle = pickReplacementHandle(restored, "source");
      const newTargetHandle = pickReplacementHandle(restored, "target");

      setNodes((nds) => nds.map((n) => (n.id === targetId ? restored : n)));
      setEdges((eds) =>
        eds.map((edge) => {
          if (edge.source === targetId) {
            return { ...edge, source: newId, sourceHandle: newSourceHandle };
          }
          if (edge.target === targetId) {
            return { ...edge, target: newId, targetHandle: newTargetHandle };
          }
          return edge;
        })
      );
    },
    [setNodes, setEdges, restoreNodeFunctions]
  );

  // Open the Available Nodes sidebar in "replace" mode for a node.
  const requestReplaceNode = useCallback((id: string) => {
    setReplaceTargetId(id);
    setShowWorkflowPanel(false);
    setShowNodePanel(true);
  }, []);

  // The sidebar's add handler: in replace mode swap the target node; otherwise
  // add a new node as usual.
  const handlePanelAddNode = useCallback(
    (nodeType: string) => {
      if (replaceTargetId) {
        replaceNode(replaceTargetId, nodeType);
        setReplaceTargetId(null);
        setShowNodePanel(false);
      } else {
        addNewNode(nodeType);
      }
    },
    [replaceTargetId, replaceNode]
  );

  // Run the full workflow from the Executions panel. Stable (reads the latest
  // graph through refs) so the NodeActionsContext value doesn't churn on every
  // drag/edit. Mirrors openExecutions(); inlined so the deps can stay empty.
  const testWorkflowFromCanvas = useCallback(() => {
    setCurrentTestConfig({
      ...(workflowRef.current || {}),
      nodes: nodesRef.current,
      edges: edgesRef.current,
    } as Workflow);
    setShowNodePanel(false);
    setShowWorkflowPanel(false);
    setActiveTab("executions");
  }, []);

  const nodeActionsValue = useMemo(
    () => ({
      duplicateNode,
      copyNode,
      requestReplaceNode,
      testWorkflow: testWorkflowFromCanvas,
    }),
    [duplicateNode, copyNode, requestReplaceNode, testWorkflowFromCanvas]
  );

  // Keyboard shortcuts for canvas interactions
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;

      // Compare lowercase keys 
      const isUndo =
        (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey;
      const isRedo =
        (e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z";

      // Skip undo/redo if typing or inside an open dialog
      if (isUndo || isRedo) {
        if (isEditableEventTarget(target) || target.closest('[role="dialog"]')) return;
        e.preventDefault();
        if (isUndo) undo();
        else redo();
        return;
      }

      // Never hijack copy/paste while typing in a field or inside a dialog.
      if (isEditableEventTarget(target) || target.closest('[role="dialog"]'))
        return;

      const isReactFlowCanvas =
        target.closest(".react-flow__viewport") ||
        target.closest(".react-flow__pane") ||
        target.closest(".react-flow__renderer");

      if ((e.ctrlKey || e.metaKey) && e.key === "c") {
        // ⌘C copies the current selection — keep it scoped to the canvas so it
        // doesn't swallow a normal text copy elsewhere on the page.
        if (!isReactFlowCanvas) return;
        e.preventDefault();
        copySelectedNodes();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "v") {
        // ⌘V pastes clipboard nodes. Allow it from anywhere on the builder (not
        // only when the canvas has focus) so a node copied via its 3-dots menu
        // pastes even though the menu moved focus off the canvas. Only act when
        // there is actually something to paste.
        if (!clipboardRef.current) return;
        e.preventDefault();
        pasteFromClipboard();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [copySelectedNodes, pasteFromClipboard, undo, redo]);

  // ---- Node search / command palette --------------------------------------
  const closeNodeSearch = useCallback(() => {
    setNodeSearchOpen(false);
    setNodeSearchQuery("");
    setNodeSearchAgentMode(false);
  }, []);

  // Overlay mode derived from state + input text:
  //  - "agent":   /agent was picked — typed text is sent to the AI assistant
  //  - "command": input starts with "/" — show the /agent command + node list
  //  - "search":  default — spotlight matching nodes on the canvas
  const nodeSearchModeType: "agent" | "command" | "search" = nodeSearchAgentMode
    ? "agent"
    : nodeSearchQuery.startsWith("/")
    ? "command"
    : "search";

  // Text after the leading "/" in command mode (filters both the node list and /agent)
  const nodeSearchCommandFilter =
    nodeSearchModeType === "command"
      ? nodeSearchQuery.slice(1).trim().toLowerCase()
      : "";

  // IDs of nodes matching the current query (null unless in search mode with text)
  const nodeSearchMatchIds = useMemo(() => {
    const query = nodeSearchQuery.trim().toLowerCase();
    if (!nodeSearchOpen || nodeSearchModeType !== "search" || !query) return null;

    const terms = query.split(/\s+/).filter(Boolean);
    const ids = new Set<string>();
    for (const node of nodes) {
      const label = nodeRegistry.getNodeType(node.type ?? "")?.label ?? "";
      const name = typeof node.data?.name === "string" ? node.data.name : "";
      const haystack = `${name} ${label} ${node.type ?? ""}`.toLowerCase();
      if (terms.every((term) => haystack.includes(term))) {
        ids.add(node.id);
      }
    }
    return ids;
  }, [nodes, nodeSearchOpen, nodeSearchModeType, nodeSearchQuery]);

  // Nodes/edges with presentational search classNames layered on top of state.
  // Kept separate from `nodes`/`edges` so search never dirties or persists onto the workflow.
  const displayNodes = useMemo(() => {
    if (!nodeSearchMatchIds) return nodes;
    return nodes.map((node) => ({
      ...node,
      className: [
        node.className,
        nodeSearchMatchIds.has(node.id) ? "node-search-match" : "node-search-dim",
      ]
        .filter(Boolean)
        .join(" "),
    }));
  }, [nodes, nodeSearchMatchIds]);

  const displayEdges = useMemo(() => {
    if (!nodeSearchMatchIds) return edges;
    return edges.map((edge) => {
      // Keep an edge lit only when both endpoints matched; otherwise dim it.
      const connectsMatches =
        nodeSearchMatchIds.has(edge.source) && nodeSearchMatchIds.has(edge.target);
      if (connectsMatches) return edge;
      return {
        ...edge,
        className: [edge.className, "edge-search-dim"].filter(Boolean).join(" "),
      };
    });
  }, [edges, nodeSearchMatchIds]);

  const nodeSearchMatchCount = nodeSearchMatchIds?.size ?? 0;

  // Enter → fit the viewport to the matched node(s)
  const focusSearchMatches = useCallback(() => {
    if (!reactFlowInstance || !nodeSearchMatchIds || nodeSearchMatchIds.size === 0) return;
    const matched = nodes
      .filter((n) => nodeSearchMatchIds.has(n.id))
      .map((n) => ({ id: n.id }));
    reactFlowInstance.fitView({
      nodes: matched,
      duration: 500,
      padding: 0.4,
      maxZoom: 1.4,
    });
  }, [reactFlowInstance, nodeSearchMatchIds, nodes]);

  // Results shown in the overlay: existing canvas nodes that matched the query.
  const nodeSearchExistingResults = useMemo(() => {
    if (!nodeSearchMatchIds) return [];
    return nodes
      .filter((n) => nodeSearchMatchIds.has(n.id))
      .map((n) => {
        const def = nodeRegistry.getNodeType(n.type ?? "");
        const name =
          typeof n.data?.name === "string" && n.data.name.trim()
            ? n.data.name
            : def?.label ?? n.type ?? "Node";
        return {
          id: n.id,
          name,
          typeLabel: def?.label ?? n.type ?? "",
          icon: def?.icon ?? "Box",
          category: def?.category ?? "utils",
        };
      });
  }, [nodes, nodeSearchMatchIds]);

  // Registry node types offered in the results list (as "add new").
  //  - search mode:  fuzzy match to the query, capped
  //  - command mode: match the text after "/", full list
  //  - agent mode:   none
  const nodeSearchAddResults = useMemo(() => {
    if (!nodeSearchOpen) return [];

    let terms: string[];
    let cap: number;
    if (nodeSearchModeType === "command") {
      terms = nodeSearchCommandFilter.split(/\s+/).filter(Boolean);
      cap = Infinity;
    } else if (nodeSearchModeType === "search") {
      const query = nodeSearchQuery.trim().toLowerCase();
      if (!query) return [];
      terms = query.split(/\s+/).filter(Boolean);
      cap = 8;
    } else {
      return [];
    }

    const matches = nodeRegistry.getAllNodeTypes().filter((def) => {
      const haystack = `${def.label} ${def.description} ${def.type}`.toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });

    return (Number.isFinite(cap) ? matches.slice(0, cap) : matches).map((def) => ({
      type: def.type,
      label: def.label,
      description: def.description,
      icon: def.icon,
      category: def.category,
    }));
  }, [nodeSearchOpen, nodeSearchModeType, nodeSearchQuery, nodeSearchCommandFilter]);

  // Whether the /agent command is offered (respects the chat-input feature flag)
  const showAgentCommand =
    showChatInput &&
    nodeSearchModeType === "command" &&
    (nodeSearchCommandFilter === "" || "agent".includes(nodeSearchCommandFilter));

  // Focus/center the viewport on a single node picked from the results list.
  const focusNodeFromSearch = useCallback(
    (nodeId: string) => {
      if (!reactFlowInstance) return;
      reactFlowInstance.fitView({
        nodes: [{ id: nodeId }],
        duration: 500,
        padding: 0.5,
        maxZoom: 1.4,
      });
    },
    [reactFlowInstance]
  );

  // Add a new node (from the "add new" results) at the center of the viewport, then close search.
  const addNodeFromSearch = useCallback(
    (nodeType: string) => {
      const position = reactFlowInstance
        ? reactFlowInstance.screenToFlowPosition({
            x: window.innerWidth / 2,
            y: window.innerHeight / 2,
          })
        : undefined;
      addNewNode(nodeType, position);
      closeNodeSearch();
    },
    [reactFlowInstance, addNewNode, closeNodeSearch]
  );

  // Enter agent mode (picked the /agent command) — swaps the "/…" text for an /agent badge
  const enterNodeSearchAgentMode = useCallback(() => {
    setNodeSearchAgentMode(true);
    setNodeSearchQuery("");
  }, []);

  // Leave agent mode (badge removed) — back to a blank search
  const exitNodeSearchAgentMode = useCallback(() => {
    setNodeSearchAgentMode(false);
    setNodeSearchQuery("");
  }, []);

  // Send the typed message to the AI assistant, then hand off to the conversational panel.
  const sendAgentMessageFromSearch = useCallback(
    (message: string) => {
      const text = message.trim();
      if (!text) return;
      assistant.sendMessage(text);
      setHasStartedConversation(true);
      setShowNodePanel(true);
      setConversationalTabActive(true);
      closeNodeSearch();
    },
    [assistant, closeNodeSearch]
  );

  // Update the overlay query. Typing "/agent " (the command followed by a space)
  // auto-activates agent mode, turning it into a badge and keeping any trailing text.
  const handleNodeSearchQueryChange = useCallback(
    (value: string) => {
      if (!nodeSearchAgentMode && showChatInput && /^\/agent\s/i.test(value)) {
        setNodeSearchAgentMode(true);
        setNodeSearchQuery(value.replace(/^\/agent\s+/i, ""));
        return;
      }
      setNodeSearchQuery(value);
    },
    [nodeSearchAgentMode, showChatInput]
  );

  // Shortcuts: ⌘K/Ctrl+K (or "/") opens the command palette; ⌘I/Ctrl+I toggles the
  // Available Nodes panel; Esc closes the palette.
  useEffect(() => {
    const handleSearchKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isTyping = isEditableEventTarget(target);

      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setNodeSearchAgentMode(false);
        setNodeSearchQuery("");
        setNodeSearchOpen(true);
      } else if ((e.metaKey || e.ctrlKey) && (e.key === "i" || e.key === "I")) {
        e.preventDefault();
        const willOpen = !showNodePanel;
        setShowNodePanel(willOpen);
        if (willOpen) {
          // Opening the Available Nodes panel closes the workflows panel and
          // lands on the nodes tab (not the conversational tab).
          setShowWorkflowPanel(false);
          setConversationalTabActive(false);
        }
      } else if (e.key === "/" && !isTyping && !nodeSearchOpen) {
        e.preventDefault();
        setNodeSearchAgentMode(false);
        setNodeSearchQuery("/"); // open straight into the command palette
        setNodeSearchOpen(true);
      } else if (e.key === "Escape" && nodeSearchOpen) {
        e.preventDefault();
        closeNodeSearch();
      }
    };
    window.addEventListener("keydown", handleSearchKey);
    return () => window.removeEventListener("keydown", handleSearchKey);
  }, [nodeSearchOpen, closeNodeSearch, showNodePanel]);

  // Shortcut: ⌘M/Ctrl+M auto-arranges (cleans up) the node layout on the canvas.
  useEffect(() => {
    const handleArrangeKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "m" || e.key === "M")) {
        if (isEditableEventTarget(e.target as HTMLElement)) return;
        e.preventDefault();
        handleAutoArrange();
      }
    };
    window.addEventListener("keydown", handleArrangeKey);
    return () => window.removeEventListener("keydown", handleArrangeKey);
  }, [handleAutoArrange]);

  // Close search on any canvas click (pane or node)
  const handleCanvasClickClose = useCallback(() => {
    if (nodeSearchOpen) closeNodeSearch();
  }, [nodeSearchOpen, closeNodeSearch]);

  // Single memoized "current workflow" (metadata + live nodes/edges) shared by the
  // panels, instead of building a fresh object inline for each of them every render.
  const currentWorkflow = useMemo(
    () => ({ ...workflow, nodes, edges }),
    [workflow, nodes, edges]
  );

  // Evaluations tab is available only with eval access and once the workflow is
  // saved (so there's a workflow_id to scope its evaluations to).
  const evaluationsDisabledReason = !canEvaluate
    ? "Requires evaluation access"
    : !agent?.workflow_id
      ? "Save the workflow to add evaluations"
      : null;

  return (
    <WorkflowProvider workflow={workflow} setWorkflow={setWorkflow}>
      <WorkflowExecutionProvider>
        <NodeActionsContext.Provider value={nodeActionsValue}>
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
                  className={lowDetail ? "rf-low-detail" : undefined}
                  nodes={displayNodes}
                  edges={displayEdges}
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
                  onPaneClick={handleCanvasClickClose}
                  onNodeClick={handleCanvasClickClose}
                  onNodeDoubleClick={onNodeDoubleClick}
                  onReconnect={onReconnect}
                  onReconnectStart={onReconnectStart}
                  onReconnectEnd={onReconnectEnd}
                  onMove={handleCanvasMove}
                  onNodeDrag={revealMinimap}
                  onSelectionDrag={revealMinimap}
                  nodesDraggable={nodesDraggable}
                  nodesConnectable={nodesConnectable}
                  elementsSelectable={elementsSelectable}
                  proOptions={PRO_OPTIONS}
                  onlyRenderVisibleElements
                >
                  <LowDetailWatcher onChange={setLowDetail} />
                  <Background />
                  <WorkflowMiniMap visible={minimapVisible} />
                  <CustomControls
                    nodesDraggable={nodesDraggable}
                    nodesConnectable={nodesConnectable}
                    elementsSelectable={elementsSelectable}
                    onNodesDraggableChange={setNodesDraggable}
                    onNodesConnectableChange={setNodesConnectable}
                    onElementsSelectableChange={setElementsSelectable}
                    onAutoArrange={handleAutoArrange}
                  />
                  <Panel position="top-center" className="mt-4">
                    <AgentTopPanel data={agent} onUpdated={handleAgentUpdated} />
                  </Panel>
                </ReactFlow>
              </div>
            </CanvasContextMenu>

            {/* Top-left view switcher: graph editor vs. executions/test page.
                The sidebar's floating toggle button sits at the top-left corner
                when collapsed (far left, ~44px) and at the sidebar's right edge
                when expanded (overlapping the canvas edge), so keep a consistent
                gap after it in both states. */}
            <div
              className={`absolute top-2 z-30 transition-[left] duration-200 ${
                sidebarState === "collapsed" ? "left-16" : "left-8"
              }`}
            >
              <Tabs value={activeTab} onValueChange={handleTabChange}>
                {/* h-11 (44px) + glassy background matches the Save/Test pill and the
                    workflow-details card so all three top controls read as one family. */}
                <TabsList className="h-11 rounded-full bg-background/80 shadow-sm backdrop-blur-sm">
                  <TabsTrigger value="workflow" className="gap-1.5 px-3 text-xs">
                    <WorkflowIcon className="h-3.5 w-3.5" />
                    Workflow
                  </TabsTrigger>
                  <TabsTrigger value="executions" className="gap-1.5 px-3 text-xs">
                    <Play className="h-3.5 w-3.5" />
                    Executions
                  </TabsTrigger>
                  {/* Evaluations tab. Disabled (with a reason tooltip) until the
                      user has eval access and the workflow is saved; a disabled
                      trigger has pointer-events-none, so hover falls through to the
                      group wrapper and the CSS tooltip shows. */}
                  {evaluationsDisabledReason ? (
                    <span className="group relative inline-flex cursor-not-allowed">
                      <TabsTrigger
                        value="evaluations"
                        disabled
                        className="gap-1.5 px-3 text-xs"
                      >
                        <ClipboardCheck className="h-3.5 w-3.5" />
                        Evaluations
                        <span className="ml-0.5 rounded bg-emerald-50 px-1 py-0.5 text-[9px] font-semibold uppercase leading-none text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400">
                          New
                        </span>
                      </TabsTrigger>
                      <span
                        role="tooltip"
                        className="pointer-events-none absolute left-1/2 top-full z-40 mt-2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100"
                      >
                        {evaluationsDisabledReason}
                      </span>
                    </span>
                  ) : (
                    <TabsTrigger value="evaluations" className="gap-1.5 px-3 text-xs">
                      <ClipboardCheck className="h-3.5 w-3.5" />
                      Evaluations
                      <span className="ml-0.5 rounded bg-emerald-50 px-1 py-0.5 text-[9px] font-semibold uppercase leading-none text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400">
                        New
                      </span>
                    </TabsTrigger>
                  )}
                </TabsList>
              </Tabs>
            </div>

            {/* Unified top-right controls (prevents overlap between ReactFlow Panel + NodePanel buttons).
                Kept mounted (hidden on the Executions tab) so BottomPanel's unsaved-changes
                navigation guard and live execution mirroring stay active. */}
            <div
              className={`fixed top-2 z-20 flex flex-row flex-wrap items-start justify-end gap-2 max-w-[calc(100vw-1rem)] transition-[right] duration-300 ${
                activeTab !== "workflow" ? "hidden" : ""
              } ${
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
                workflow={currentWorkflow}
                hasUnsavedChanges={hasUnsavedChanges}
                onWorkflowLoaded={(workflow) => handleWorkflowLoaded(workflow, true)}
                onTestWorkflow={handleTestGraph}
                onSaveWorkflow={handleSaveWorkflow}
                onExecutionStateChange={setExecutionState}
              />

              <div className="flex flex-col gap-2">
                <Button
                  onClick={toggleNodePanel}
                  size="icon"
                  variant="ghost"
                  className="rounded-full h-10 w-10 shadow-md bg-card hover:bg-muted border border-border"
                >
                  {showNodePanel ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                  <span className="sr-only">
                    {showNodePanel ? "Close Node Panel" : "Open Node Panel"}
                  </span>
                </Button>

                <Button
                  onClick={toggleWorkflowPanel}
                  size="icon"
                  variant="ghost"
                  className="rounded-full h-10 w-10 shadow-md bg-card hover:bg-muted border border-border"
                >
                  {showWorkflowPanel ? (
                    <X className="h-4 w-4" />
                  ) : (
                    <History className="h-4 w-4" />
                  )}
                  <span className="sr-only">
                    {showWorkflowPanel
                      ? "Close Saved Versions"
                      : "Open Saved Versions"}
                  </span>
                </Button>
              </div>
            </div>

            <NodePanel
              isOpen={showNodePanel}
              onClose={toggleNodePanel}
              onAddNode={handlePanelAddNode}
              replaceMode={!!replaceTargetId}
              replaceNodeName={
                replaceTargetId
                  ? (nodes.find((n) => n.id === replaceTargetId)?.data?.name as
                      | string
                      | undefined)
                  : undefined
              }
              onCancelReplace={() => setReplaceTargetId(null)}
              messages={assistant.messages}
              isThinking={assistant.isThinking}
              activeConversationalTab={conversationalTabActive}
              onSendMessage={(message) => {
                assistant.sendMessage(message);
                setHasStartedConversation(true);
              }}
            />

            <WorkflowsSavedPanel
              isOpen={showWorkflowPanel}
              onClose={toggleWorkflowPanel}
              agentId={agentId}
              activeWorkflowId={agent?.workflow_id}
              currentWorkflow={currentWorkflow}
              onWorkflowSelect={handleWorkflowLoaded}
              onActiveWorkflowChange={handleActiveWorkflowChange}
              refreshKey={refreshKey}
              hasUnsavedChanges={hasUnsavedChanges}
              onSaveWorkflow={handleSaveWorkflow}
            />

            {/* Executions page — overlays the canvas (which stays mounted
                underneath so the graph/viewport is preserved). */}
            {activeTab === "executions" && (
              <div className="absolute inset-0 z-20 flex flex-col bg-background">
                {/* Title on the same row as the floating tabs (which sit at the
                    left); the columns start immediately below with no extra gap. */}
                <div className="flex h-14 shrink-0 items-center justify-center px-3">
                  <h2 className="text-base font-semibold leading-none tracking-tight">
                    Test Workflow: Current Graph
                  </h2>
                </div>
                <div className="min-h-0 flex-1 px-3 pb-3">
                  <WorkflowTestPanel
                    active
                    workflow={currentTestConfig}
                    history={testHistory}
                    onAddTestRun={handleAddTestRun}
                    onClearHistory={handleClearTestHistory}
                    onUpdateWorkflowTestInputs={handleUpdateWorkflowTestInputs}
                  />
                </div>
              </div>
            )}

            {/* Evaluations page — overlays the canvas (kept mounted underneath).
                The tab handles its own list/detail navigation in-place. */}
            {activeTab === "evaluations" && (
              <div className="absolute inset-0 z-20 bg-background">
                <WorkflowEvaluationsTab workflowId={agent?.workflow_id} />
              </div>
            )}

            {activeTab === "workflow" &&
              (showSetupWizard ? (
                <SetupWizardPanel
                  nodes={nodes}
                  onNodeFocus={handleNodeFocus}
                  onClose={() => setShowSetupWizard(false)}
                  onTest={() => handleTestGraph({ ...workflow, nodes, edges } as Workflow)}
                />
              ) : wizardWasShown ? (
                <SetupWizardReopenButton onClick={() => setShowSetupWizard(true)} />
              ) : null)}

            {nodeSearchOpen && (
              <WorkflowCommandPalette
                mode={nodeSearchModeType}
                query={nodeSearchQuery}
                onQueryChange={handleNodeSearchQueryChange}
                onClose={closeNodeSearch}
                onSubmit={focusSearchMatches}
                matchCount={nodeSearchMatchCount}
                existingResults={nodeSearchExistingResults}
                addResults={nodeSearchAddResults}
                onFocusNode={focusNodeFromSearch}
                onAddNode={addNodeFromSearch}
                showAgentCommand={showAgentCommand}
                onSelectAgent={enterNodeSearchAgentMode}
                onExitAgent={exitNodeSearchAgentMode}
                onSendAgentMessage={sendAgentMessageFromSearch}
              />
            )}
          </div>
        </div>
        </NodeActionsContext.Provider>
      </WorkflowExecutionProvider>
    </WorkflowProvider>
  );
};

export default GraphFlowContent;

// GraphFlowContent already wraps its subtree in a WorkflowExecutionProvider,
// and all consumers (nodes, panels, dialogs) live inside that subtree — so this
// wrapper does not add a second provider (which would be a redundant, unused instance).
const GraphFlow: React.FC = () => {
  return <GraphFlowContent />;
};

export { GraphFlow };

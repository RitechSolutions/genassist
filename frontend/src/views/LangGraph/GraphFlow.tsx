import React, {
  useCallback,
  useState,
  useEffect,
  useMemo,
  useRef,
} from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  Panel,
  ReactFlowInstance,
  useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/button";
import {
  ChevronRight,
  ChevronLeft,
  MessageCircle,
  X,
  Save,
  Upload,
  Brain,
  FileText,
  MessageSquare,
  Database,
  FolderOpen,
  Download,
  PlayCircle,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/card";
import { getNodeTypes } from "./nodeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import {
  NodeTypeDefinition,
  ChatInputNodeData,
  PromptNodeData,
  NodeData,
} from "./types/nodes";
import { createWorkflow, updateWorkflow } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import WorkflowManager from "./components/WorkflowManager";
import WorkflowTestDialog from "./components/WorkflowTestDialog";
import NodePanel from "./components/NodePanel";
import BottomPanel from "./components/BottomPanel";
import WorkflowTopPanel from "./components/WorkflowTopPanel";
import { useSchemaValidation } from "./hooks/useSchemaValidation";

// Get node types for React Flow
const nodeTypes = getNodeTypes();

const GraphFlow: React.FC = () => {
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null);

  const [workflow, setWorkflow] = useState<Workflow>();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [showNodePanel, setShowNodePanel] = useState(false);
  const [showWorkflowPanel, setShowWorkflowPanel] = useState(false);
  const [currentTestConfig, setCurrentTestConfig] = useState<Workflow | null>(
    null
  );
  const [testDialogOpen, setTestDialogOpen] = useState(false);

  const { validateConnection } = useSchemaValidation();

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

  // Connection handler with special handling for connections
  const onConnect = useCallback(
    (params: Connection) => {
      // Validate schema compatibility before allowing connection
      if (!validateConnection(params)) {
        console.warn("Connection rejected due to schema incompatibility");
        return;
      }

      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges, validateConnection]
  );

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
    setNodes((nds) =>
      nds.map((node) => {
        if (
          node.type === "chatInputNode" ||
          node.type === "llmModelNode" ||
          node.type === "promptNode" ||
          node.type === "apiToolNode" ||
          node.type === "agentNode" ||
          node.type === "knowledgeBaseNode"
        ) {
          return {
            ...node,
            data: {
              ...node.data,
              updateNodeData,
            },
          };
        }
        return node;
      })
    );
  }, [updateNodeData]);

  useEffect(() => {
    init();
  }, []);
  const init = () => {

    const newNode = nodeRegistry.createNode("chatInputNode", "1", {
      x: -219,
      y: 191,
    });
    const newNode2 = nodeRegistry.createNode("chatOutputNode", "2", {
      x: 808,
      y: 191,
    });
    newNode.data = {
      ...newNode.data,
      updateNodeData,
    };
    newNode2.data = {
      ...newNode2.data,
      updateNodeData,
    };

    setNodes((nds) => [...nds, newNode, newNode2]);
  };
  // Add a new node
  const addNewNode = (
    nodeType: string,
    nodePosition?: { x: number; y: number }
  ) => {
    console.log("Adding new node:", nodeType);
    const lastNode = nodes[nodes.length - 1];
    const id = (lastNode?.id ? parseInt(lastNode.id) + 1 : 1).toString();
    const position = nodePosition ?? {
      x: Math.random() * 400 + 100,
      y: Math.random() * 300 + 100,
    };
    console.log("Position:", position);

    const newNode = nodeRegistry.createNode(nodeType, id, position);
    if (newNode) {
      // Add updateNodeData function to the node data if it's a node type that needs it
      if (
        nodeType === "chatInputNode" ||
        nodeType === "llmModelNode" ||
        nodeType === "promptNode" ||
        nodeType === "apiToolNode" ||
        nodeType === "agentNode" ||
        nodeType === "knowledgeBaseNode"
      ) {
        newNode.data = {
          ...newNode.data,
          updateNodeData,
        };
      }
      console.log("New node:", newNode);
      setNodes((nds) => [...nds, newNode]);
    }
  };

  // Restore functions to nodes after loading
  const restoreNodeFunctions = (loadedNodes: Node[]): Node[] => {
    return loadedNodes.map((node) => {
      // Create a deep copy to avoid modifying the original
      const nodeCopy = { ...node, data: { ...node.data } };

      // Add updateNodeData to all node types that need it
      if (
        node.type === "chatInputNode" ||
        node.type === "llmModelNode" ||
        node.type === "promptNode" ||
        node.type === "apiToolNode" ||
        node.type === "agentNode" ||
        node.type === "knowledgeBaseNode"
      ) {
        nodeCopy.data = {
          ...nodeCopy.data,
          updateNodeData,
        };
      }

      // For ChatInputNodes, restore the onMessageSubmit function
      if (node.type === "chatInputNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
          onMessageSubmit: (message: string) => {
            console.log("Message submitted from restored node:", message);
          },
        };
      }

      // For LLMModelNodes, restore the updateNodeData function
      if (node.type === "llmModelNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
          onInputReceived: (text: string) => {
            console.log(
              "Input received in restored LLM node:",
              text.substring(0, 50)
            );
          },
          onOutputChange: (outputText: string) => {
            console.log(
              "Output changed in restored LLM node:",
              outputText.substring(0, 50)
            );
          },
        };
      }

      // For PromptNodes, restore the updateNodeData and onInputReceived functions
      if (node.type === "promptNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
        };
      }

      // For ChatOutputNodes, restore the updateNodeData and onInputReceived functions
      if (node.type === "chatOutputNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
          onInputReceived: (text: string) => {
            console.log(
              "Input received in restored chat output node:",
              text.substring(0, 50)
            );
          },
        };
      }

      // For APIToolNodes, restore the updateNodeData and onInputReceived functions
      if (node.type === "apiToolNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
          onInputReceived: (text: string) => {
            console.log(
              "Input received in restored API tool node:",
              text.substring(0, 50)
            );
          },
        };
      }

      // For AgentNodes, restore the updateNodeData and onInputReceived functions
      if (node.type === "agentNode") {
        nodeCopy.data = {
          ...nodeCopy.data,
          onInputReceived: (
            text: string,
            tools: Array<{
              id: string;
              name: string;
              description: string;
              category: string;
            }>
          ) => {
            console.log(
              "Input received in restored agent node:",
              text.substring(0, 50)
            );
          },
          onOutputChange: (outputText: string) => {
            console.log(
              "Output changed in restored agent node:",
              outputText.substring(0, 50)
            );
          },
        };
      }

      return nodeCopy;
    });
  };

  // Handle graph data loaded from file
  const handleWorkflowLoaded = (loadedWorkflow: Workflow) => {
    // Restore functions to nodes
    const nodesWithFunctions = restoreNodeFunctions(loadedWorkflow.nodes);

    // Load nodes and edges
    setNodes(nodesWithFunctions);
    setEdges(loadedWorkflow.edges);
    setWorkflow(loadedWorkflow);

    // Fit view to show all nodes
    setTimeout(() => {
      if (reactFlowInstance) {
        reactFlowInstance.fitView({ padding: 0.2 });
      }
    }, 100);
  };

  // Handle test graph
  const handleTestGraph = (graphData: Workflow) => {
    setCurrentTestConfig(graphData);
    setTestDialogOpen(true);
  };
  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          onInit={setReactFlowInstance}
          fitView
        >
          <Background />
          <Controls />
          <BottomPanel
            workflow={{
              ...workflow,
              nodes: nodes,
              edges: edges,
            }}
            onWorkflowLoaded={handleWorkflowLoaded}
            onTestWorkflow={handleTestGraph}
          />
          {/* Right panel toggle buttons */}
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

        <WorkflowTopPanel
          isOpen={showWorkflowPanel}
          onClose={toggleWorkflowPanel}
          currentWorkflow={{
            ...workflow,
            nodes: nodes,
            edges: edges,
          }}
          onWorkflowSelect={handleWorkflowLoaded}
          onWorkflowSave={handleWorkflowLoaded}
        />

        <WorkflowTestDialog
          isOpen={testDialogOpen}
          onClose={() => setTestDialogOpen(false)}
          workflowName="Current Graph"
          workflow={currentTestConfig}
        />
      </div>
    </div>
  );
};

export default GraphFlow;

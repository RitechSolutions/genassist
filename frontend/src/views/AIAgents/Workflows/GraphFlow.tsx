import React, { useCallback, useState, useEffect } from "react";
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
} from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/button";
import { ChevronLeft, FolderOpen, PanelLeft } from "lucide-react";
import { getNodeTypes } from "./nodeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { NodeData } from "./types/nodes";
import { Workflow } from "@/interfaces/workflow.interface";
import WorkflowTestDialog from "./components/WorkflowTestDialog";
import NodePanel from "./components/NodePanel";
import BottomPanel from "./components/BottomPanel";
import WorkflowsSavedPanel from "./components/WorkflowsSavedPanel";
import { useSchemaValidation } from "./hooks/useSchemaValidation";
import { useSidebar } from "@/components/sidebar";
import { AgentConfig, getAgentConfig } from "@/services/api";
import { useParams } from "react-router-dom";
import { getWorkflowById, updateWorkflow } from "@/services/workflows";
import AgentTopPanel from "./components/AgentTopPanel";
import { v4 as uuidv4 } from "uuid";

// Get node types for React Flow
const nodeTypes = getNodeTypes();

const GraphFlow: React.FC = () => {
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null);

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
  const { toggleSidebar } = useSidebar();
  const { validateConnection } = useSchemaValidation();

  const { agentId } = useParams<{ agentId: string }>();

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

  const initDefaultNodes = useCallback(() => {
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
  }, [updateNodeData, setNodes]);

  useEffect(() => {
    if (agentId) {
      loadAgent(agentId);
    } else {
      initDefaultNodes();
    }
  }, [agentId, loadAgent, initDefaultNodes]);

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
  }, [updateNodeData, setNodes]);

  // Add a new node
  const addNewNode = (
    nodeType: string,
    nodePosition?: { x: number; y: number }
  ) => {
    console.log("Adding new node:", nodeType);
    const id = uuidv4();
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

  };

  // Handle test graph
  const handleTestGraph = (graphData: Workflow) => {
    setCurrentTestConfig(graphData);
    setTestDialogOpen(true);
  };
  const handleSaveWorkflow = async () => {
    try {
      // const updatedWorkflow = await updateWorkflow(workflow);
      // setWorkflow(updatedWorkflow);
      await updateWorkflow(workflow.id, {
        ...workflow,
        nodes: nodes,
        edges: edges,
      });
      await loadWorkflow(workflow.id);
    } catch (error) {
      console.error("Error saving workflow:", error);
    }
  };
  return (
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
          nodeTypes={nodeTypes}
          onInit={setReactFlowInstance}
          fitView
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
              onWorkflowLoaded={handleWorkflowLoaded}
              onTestWorkflow={handleTestGraph}
              onSaveWorkflow={handleSaveWorkflow}
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


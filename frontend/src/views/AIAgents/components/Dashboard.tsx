import React, { useState, useEffect } from "react";
import {
  AgentConfig,
  deleteAgentConfig,
  getAgentConfig,
  getAllAgentConfigs,
  initializeAgent,
} from "@/services/api";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { toast } from "react-hot-toast";
import AgentList from "./AgentList";
import ManageApiKeysModal from "./Keys/ManageApiKeysModal";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";

const Dashboard: React.FC = () => {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [modalContext, setModalContext] = useState<{
    agentId: string;
    userId: string;
  } | null>(null);
  const [agentToDelete, setAgentToDelete] = useState<AgentConfig | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const navigate = useNavigate();

  const handleManageKeys = (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) {
      const a = agents.find((a) => a.id === agentId)!;
      setModalContext({ agentId, userId: a.user_id });
    }
  };

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const data = await getAllAgentConfigs();
      setAgents(data);
      setError(null);
    } catch (err) {
      setError("Failed to load agent configurations");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleDeleteClick = async (agentId: string) => {
    const agent = await getAgentConfig(agentId);
    setAgentToDelete(agent);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteAgent = async () => {
    if (!agentToDelete?.id || !deleteAgentConfig) return;

    try {
      setIsDeleting(true);
      await deleteAgentConfig(agentToDelete.id);
      await fetchAgents();
      toast.success("Agent deleted successfully");
    } catch (err) {
      toast.error("Failed to delete agent");
      setError("Failed to delete agent");
      console.error(err);
    } finally {
      setAgentToDelete(null);
      setIsDeleteDialogOpen(false);
      setIsDeleting(false);
    }
  };

  const handleUpdateAgent = async (agentId: string) => {
    try {
      const agent = agents.find((a) => a.id === agentId);
      if (agent) {
        const newState = !agent.is_active;
        // if (newState) {
        //   await initializeAgent(agentId);
        // } else {
        //   const updatedAgents = agents.map(a =>
        //     a.id === agentId ? { ...a, is_active: false } : a
        //   );
        //   setAgents(updatedAgents);
        //   return;
        // }
        await initializeAgent(agentId);
        await fetchAgents();
      }
    } catch (err) {
      setError("Failed to update agent status");
      console.error(err);
    }
  };

  const handleGetIntegrationCode = (agentId: string) => {
    navigate(`/ai-agents/integration/${agentId}`);
  };

  const handleChatAsCustomer = (agentId: string) => {
    navigate(`/ai-agents/chat-as-customer/${agentId}`);
  };

  if (loading)
    return (
      <div className="flex items-center justify-center p-8">
        Loading workflows configurations...
      </div>
    );

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 p-4 text-destructive bg-destructive/10 rounded-md">
          <AlertCircle className="h-5 w-5" />
          <p className="text-sm font-medium">{error}</p>
        </div>

        <div className="bg-white p-6 rounded-md shadow-sm">
          <h2 className="text-xl font-semibold mb-4">
            Server Connection Error
          </h2>
          <p className="mb-4">
            Unable to connect to the AI Agent server. This may be because:
          </p>
          <ul className="list-disc pl-6 mb-6 space-y-2">
            <li>The server is not running</li>
            <li>There's a network issue</li>
            <li>The server configuration is incorrect</li>
          </ul>
          <p className="mb-6">
            Please check your server configuration and try again.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8">
      <div className="max-w-7xl mx-auto">
        <AgentList
          agents={agents}
          onDelete={handleDeleteClick}
          onUpdate={handleUpdateAgent}
          onGetIntegrationCode={handleGetIntegrationCode}
          onManageKeys={handleManageKeys}
          onChatAsCustomer={handleChatAsCustomer}
        />

        {modalContext && (
          <ManageApiKeysModal
            agentId={modalContext.agentId}
            userId={modalContext.userId}
            isOpen={!!modalContext}
            onClose={() => setModalContext(null)}
          />
        )}

        <DeleteConfirmDialog
          isOpen={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
          onConfirm={handleDeleteAgent}
          isDeleting={isDeleting}
          itemName={agentToDelete?.name || ""}
          description={`This action cannot be undone. This will permanently delete agent "${agentToDelete?.name}".`}
        ></DeleteConfirmDialog>
      </div>
    </div>
  );
};

export default Dashboard;

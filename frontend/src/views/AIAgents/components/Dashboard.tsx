import React, { useState, useEffect } from "react";
import {
  deleteAgentConfig,
  getAllAgentConfigs,
  initializeAgent,
} from "@/services/api";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import AgentList from "./AgentList";
import ManageApiKeysModal from "./Keys/ManageApiKeysModal";

interface Agent {
  id: string;
  name?: string;
  description?: string;
  provider: string;
  model: string;
  system_prompt: string;
  knowledge_base_ids?: string[];
  is_active?: boolean;
  [key: string]: unknown;
  agent_id: string;
  user_id: string;
}

const Dashboard: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [modalContext, setModalContext] = useState<{
    agentId: string;
    userId: string;
  } | null>(null);

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

  const handleDeleteAgent = async (agentId: string) => {
    try {
      await deleteAgentConfig(agentId);
      await fetchAgents();
    } catch (err) {
      setError("Failed to delete agent");
      console.error(err);
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
        Loading agent configurations...
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
    <div className="dashboard">
      <AgentList
        agents={agents}
        onDelete={handleDeleteAgent}
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
    </div>
  );
};

export default Dashboard;

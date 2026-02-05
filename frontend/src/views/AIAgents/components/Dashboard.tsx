import React, { useState, useEffect, useCallback } from "react";
import { AgentListItem } from "@/interfaces/ai-agent.interface";
import {
  deleteAgentConfig,
  getAgentConfig,
  getAgentConfigsList,
  getAgentIntegrationKey,
  initializeAgent,
} from "@/services/api";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { toast } from "react-hot-toast";
import AgentList from "./AgentList";
import ManageApiKeysModal from "./Keys/ManageApiKeysModal";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const DEFAULT_PAGE_SIZE = 20;

const Dashboard: React.FC = () => {
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [modalContext, setModalContext] = useState<{
    agentId: string;
    userId: string;
    redirectOnClose?: boolean;
  } | null>(null);
  const [agentToDelete, setAgentToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const navigate = useNavigate();

  const handleManageKeys = async (agentId: string) => {
    try {
      // Fetch full agent data to get user_id
      const fullAgent = await getAgentConfig(agentId);
      setModalContext({ agentId, userId: fullAgent.user_id, redirectOnClose: false });
    } catch (err) {
      toast.error("Failed to load agent details");
    }
  };

  const isMissingApiKeyError = (err: unknown) => {
    if (!(err instanceof Error)) return false;
    return (
      err.message.includes("No active API key") ||
      err.message.includes("API key value missing")
    );
  };

  const fetchAgents = useCallback(async (currentPage: number, currentPageSize: number, append: boolean = false) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      const response = await getAgentConfigsList(currentPage, currentPageSize);
      if (append) {
        setAgents(prev => [...prev, ...response.items]);
      } else {
        setAgents(response.items);
      }
      setTotal(response.total);
      setPage(response.page);
      setHasMore(response.page < response.total_pages);
      setError(null);
    } catch (err) {
      setError("Failed to load agent configurations");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents(1, pageSize);
  }, [pageSize, fetchAgents]);

  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore) {
      const nextPage = page + 1;
      fetchAgents(nextPage, pageSize, true);
    }
  }, [loadingMore, hasMore, page, pageSize, fetchAgents]);

  const handleDeleteClick = async (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) {
      setAgentToDelete({ id: agent.id, name: agent.name });
      setIsDeleteDialogOpen(true);
    }
  };

  const handleDeleteAgent = async () => {
    if (!agentToDelete?.id || !deleteAgentConfig) return;

    try {
      setIsDeleting(true);
      await deleteAgentConfig(agentToDelete.id);
      toast.success("Agent deleted successfully.");
      // Refetch to update pagination correctly
      await fetchAgents(page, pageSize);
    } catch (err) {
      toast.error("Failed to delete agent.");
      setError("Failed to delete agent");
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
        await initializeAgent(agentId);

        // Update the local state optimistically
        const updatedAgents = agents.map((a) =>
          a.id === agentId ? { ...a, is_active: !a.is_active } : a
        );
        setAgents(updatedAgents);
      }
    } catch (err) {
      setError("Failed to update agent status");
      // Refetch to ensure UI is in sync with backend
      await fetchAgents(page, pageSize);
    }
  };

  const handleGetIntegrationCode = async (agentId: string) => {
    try {
      await getAgentIntegrationKey(agentId);
      navigate(`/ai-agents/integration/${agentId}`);
    } catch (err) {
      if (isMissingApiKeyError(err)) {
        // Fetch full agent data to get user_id for the modal
        try {
          const fullAgent = await getAgentConfig(agentId);
          setModalContext({ agentId, userId: fullAgent.user_id, redirectOnClose: true });
        } catch {
          toast.error("Failed to load agent details");
        }
        return;
      }
      toast.error("Failed to fetch an API key.");
    }
  };

  const handleApiKeyModalClose = async () => {
    if (!modalContext) return;
    const { agentId, redirectOnClose } = modalContext;
    setModalContext(null);

    if (!redirectOnClose) return;

    try {
      await getAgentIntegrationKey(agentId);
      navigate(`/ai-agents/integration/${agentId}`);
    } catch (err) {
      if (isMissingApiKeyError(err)) {
        return;
      }
      toast.error("Failed to fetch an API key.");
    }
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
          total={total}
          onDelete={handleDeleteClick}
          onUpdate={handleUpdateAgent}
          onManageKeys={handleManageKeys}
          onGetIntegrationCode={handleGetIntegrationCode}
          onRefresh={() => fetchAgents(1, pageSize)}
          loadMore={loadMore}
          hasMore={hasMore}
          loadingMore={loadingMore}
        />

        {modalContext && (
          <ManageApiKeysModal
            agentId={modalContext.agentId}
            userId={modalContext.userId}
            isOpen={!!modalContext}
            onClose={handleApiKeyModalClose}
          />
        )}

        <ConfirmDialog
          isOpen={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
          onConfirm={handleDeleteAgent}
          isInProgress={isDeleting}
          itemName={agentToDelete?.name || ""}
          description={`This action cannot be undone. This will permanently delete agent "${agentToDelete?.name}".`}
        ></ConfirmDialog>
      </div>
    </div>
  );
};

export default Dashboard;

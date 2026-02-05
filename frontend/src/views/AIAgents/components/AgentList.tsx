import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AgentListItem } from "@/interfaces/ai-agent.interface";
import { getAllKnowledgeItems } from "@/services/api";
import { Button } from "@/components/button";
import {
  Search,
  Plus,
  MoreVertical,
  Edit,
  Trash2,
  AlertCircle,
  SquareCode,
  KeyRoundIcon,
  Shield,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Switch } from "@/components/switch";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/dropdown-menu";
import { AgentFormDialog } from "./AgentForm";

const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

interface AgentListProps {
  agents: AgentListItem[];
  total: number;
  onDelete: (agentId: string) => void;
  onUpdate: (agentId: string) => void;
  onManageKeys: (agentId: string) => void;
  onGetIntegrationCode: (agentId: string) => void;
  onRefresh: () => void;
  pagination: PaginationProps;
}

const AgentList: React.FC<AgentListProps> = ({
  agents,
  total,
  onDelete,
  onUpdate,
  onManageKeys,
  onGetIntegrationCode,
  onRefresh,
  pagination,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const navigate = useNavigate();

  interface KnowledgeItem {
    id: string;
    rag_config?: {
      enabled: boolean;
    };
  }

  const activeAgents = agents.filter((agent) => agent.is_active);
  const inactiveAgents = agents.filter((agent) => !agent.is_active);
  const filteredAgents = agents.filter((agent) => {
    const agentName = agent.name;
    return agentName.toLowerCase().includes(searchTerm.toLowerCase());
  });
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);

  const [openAgentForm, setOpenAgentForm] = useState(false);

  useEffect(() => {
    const fetchKnowledgeItems = async () => {
      try {
        const items = await getAllKnowledgeItems();
        setKnowledgeItems(items as KnowledgeItem[]);
      } catch (err) {
        // ignore
      }
    };

    fetchKnowledgeItems();
  }, []);

  const handleOpenWorkflow = (agentId: string) => {
    navigate(`/ai-agents/workflow/${agentId}`);
  };

  if (!agents || agents.length === 0) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-md border border-dashed p-8 text-center animate-in fade-in-50">
        <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
          <h3 className="mt-4 text-lg font-semibold">No workflows found</h3>
          <p className="mb-4 mt-2 text-sm text-muted-foreground">
            You haven't created any workflows yet. Get started by creating your
            first agent.
          </p>
          <Button
            className="flex items-center gap-2"
            onClick={() => setOpenAgentForm(true)}
          >
            <Plus className="h-4 w-4" />
            New Workflow
          </Button>
        </div>
        <AgentFormDialog
          isOpen={openAgentForm}
          onClose={() => setOpenAgentForm(false)}
          data={null}
        />
      </div>
    );
  }

  const renderAgent = (agent: AgentListItem) => {
    const agentName = agent.name;
    const isActive = !!agent.is_active;
    const truncatedPrompt = agent.possible_queries?.join(" ") ?? "";

    return (
      <div
        key={agent.id}
        className={`px-6 py-4 hover:bg-muted/50 cursor-pointer`}
        onClick={() => {
          handleOpenWorkflow(agent.id);
        }}
      >
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <h4 className="text-base font-semibold">{agentName}</h4>
              {!isActive && (
                <span className="inline-flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
                  <AlertCircle className="h-3 w-3" />
                  Inactive
                </span>
              )}
            </div>
            <div className="space-y-1 text-sm text-muted-foreground">
              <div>
                <span className="font-medium">ID:</span> {agent.id}
              </div>
              <div>
                <span className="font-medium">Workflow ID:</span>{" "}
                {agent.workflow_id}
              </div>

              <div>
                <span className="font-medium">FAQ:</span> {truncatedPrompt}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div onClick={(e) => e.stopPropagation()}>
              <Switch
                checked={isActive}
                onCheckedChange={() => onUpdate(agent.id)}
              />
            </div>
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem asChild>
                    <Link to={`/ai-agents/workflow/${agent.id}`}>
                      <Edit className="mr-2 h-4 w-4" />
                      <span>Edit</span>
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-black"
                    onClick={() => onManageKeys(agent.id)}
                  >
                    <KeyRoundIcon className="mr-2 h-4 w-4" />
                    <span>Manage Keys</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onGetIntegrationCode(agent.id);
                    }}
                  >
                    <SquareCode className="mr-2 h-4 w-4" /> Integration
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to={`/ai-agents/security/${agent.id}`}>
                      <Shield className="mr-2 h-4 w-4" />
                      <span>Security</span>
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => onDelete(agent.id)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    <span>Delete</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleFormClose = () => {
    setOpenAgentForm(false);
    onRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Workflows</h2>
          <p className="text-zinc-400 font-normal">View and manage workflows</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search agents..."
              className="h-10 w-[200px] rounded-md border border-input bg-white pl-8 pr-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button
            className="flex items-center gap-2"
            onClick={() => setOpenAgentForm(true)}
          >
            <Plus className="h-4 w-4" />
            New Workflow
          </Button>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <div className="p-6">
          <h3 className="text-xl font-semibold">
            {total} Workflows ({activeAgents.length} Active,{" "}
            {inactiveAgents.length} Inactive)
          </h3>
        </div>
        <div className="divide-y">
          {filteredAgents.map((agent) => {
            return renderAgent(agent);
          })}
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-between px-6 py-4 border-t">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Rows per page:</span>
              <select
                value={pagination.pageSize}
                onChange={(e) => pagination.onPageSizeChange(Number(e.target.value))}
                className="h-8 rounded-md border border-input bg-white px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>
            <div className="text-sm text-muted-foreground">
              Showing {(pagination.page - 1) * pagination.pageSize + 1}-
              {Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              disabled={pagination.page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground px-2">
              Page {pagination.page} of {pagination.totalPages || 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              disabled={pagination.page >= pagination.totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
      <AgentFormDialog
        isOpen={openAgentForm}
        onClose={handleFormClose}
        data={null}
      />
    </div>
  );
};

export default AgentList;

import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getAllKnowledgeItems } from "@/services/api";
import { Button } from "@/components/button";
import {
  Search,
  Plus,
  MoreVertical,
  Edit,
  Trash2,
  MessageSquare,
  AlertCircle,
  CodeIcon,
  KeyRoundIcon,
  MessageCircle,
} from "lucide-react";
import { Switch } from "@/components/switch";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/dropdown-menu";

interface Agent {
  id: string;
  name?: string;
  agent_id: string;
  provider: string;
  model: string;
  system_prompt: string;
  knowledge_base_ids?: string[];
  is_active?: boolean;
  [key: string]: unknown;
  user_id: string; 
}

interface AgentListProps {
  agents: Agent[];
  onDelete: (agentId: string) => void;
  onUpdate: (agentId: string) => void;
  onGetIntegrationCode: (agentId: string) => void;
  onManageKeys: (agentId: string) => void;
  onChatAsCustomer: (agentId: string, userId: string) => void;
}

const AgentList: React.FC<AgentListProps> = ({
  agents,
  onDelete,
  onUpdate,
  onGetIntegrationCode,
  onManageKeys,
  onChatAsCustomer,
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
    const agentName = agent.name || `${agent.provider}-${agent.model}`;
    return agentName.toLowerCase().includes(searchTerm.toLowerCase());
  });
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);

  useEffect(() => {
    const fetchKnowledgeItems = async () => {
      try {
        const items = await getAllKnowledgeItems();
        setKnowledgeItems(items);
      } catch (err) {
        console.error("Failed to load knowledge base items:", err);
      }
    };

    fetchKnowledgeItems();
  }, []);

  const handleChatWithAgent = (agentId: string) => {
    const sessionId = Math.random().toString(36).substring(2, 15);
    navigate(`/ai-agents/chat/${agentId}/${sessionId}`);
  };

  if (!agents || agents.length === 0) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-md border border-dashed p-8 text-center animate-in fade-in-50">
        <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
          <h3 className="mt-4 text-lg font-semibold">No agents found</h3>
          <p className="mb-4 mt-2 text-sm text-muted-foreground">
            You haven't created any agents yet. Get started by creating your
            first agent.
          </p>
          <Button asChild variant="default">
            <Link to="/ai-agents/new">Create agent</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold">
            Agents{" "}
            <span className="text-zinc-400 font-normal">
              ({activeAgents.length} Active, {inactiveAgents.length} Inactive)
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            View and manage agents
          </p>
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
          <Button asChild>
            <Link to="/ai-agents/new">
              <Plus className="mr-2 h-4 w-4" />
              New Agent
            </Link>
          </Button>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <div className="p-6">
          <h3 className="text-xl font-semibold">
            {filteredAgents.length} Agents ({activeAgents.length} Active,{" "}
            {inactiveAgents.length} Inactive)
          </h3>
        </div>
        <div className="divide-y">
          {filteredAgents.map((agent) => {
            const agentName = agent.name || `${agent.provider}-${agent.model}`;
            const isActive = !!agent.is_active;
            // Truncate system prompt for display
            const truncatedPrompt = agent.system_prompt
              ? agent.system_prompt.length > 80
                ? agent.system_prompt.substring(0, 80) + "..."
                : agent.system_prompt
              : "";

            return (
              <div
                key={agent.id}
                className={`px-6 py-4 ${
                  isActive ? "hover:bg-muted/50 cursor-pointer" : ""
                }`}
                onClick={() => {
                  if (isActive) {
                    handleChatWithAgent(agent.id);
                  }
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
                      {agent.knowledge_base_ids &&
                      agent.knowledge_base_ids.length > 0 ? (
                        <div>
                          <span className="font-medium">RAG:</span>{" "}
                          {agent.knowledge_base_ids.some((kbId) => {
                            const item = knowledgeItems.find(
                              (ki) => ki.id === kbId
                            );
                            return item?.rag_config?.enabled;
                          })
                            ? "Enabled"
                            : "Disabled"}
                        </div>
                      ) : (
                        <div className="text-sm text-muted-foreground">
                          No linked knowledge base.
                        </div>
                      )}
                      <div>
                        <span className="font-medium">Knowledge Base:</span>{" "}
                        {agent.knowledge_base_ids?.length || 0} items
                      </div>
                      <div>
                        <span className="font-medium">System Prompt:</span>{" "}
                        {truncatedPrompt}
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
                            <Link to={`/ai-agents/edit/${agent.id}`}>
                              <Edit className="mr-2 h-4 w-4" />
                              <span>Edit</span>
                            </Link>
                          </DropdownMenuItem>
                          {isActive ? (
                            <DropdownMenuItem asChild>
                              <Link
                                to={`/ai-agents/chat/${agent.id}/${Math.random()
                                  .toString(36)
                                  .substring(2, 15)}`}
                              >
                                <MessageSquare className="mr-2 h-4 w-4" />
                                <span>Chat</span>
                              </Link>
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              className="text-muted-foreground"
                              disabled
                            >
                              <MessageSquare className="mr-2 h-4 w-4" />
                              <span>Chat (Agent Inactive)</span>
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem
                            className="text-black"
                            onClick={() => onGetIntegrationCode(agent.id)}
                          >
                            <CodeIcon className="mr-2 h-4 w-4" />
                            <span>Get integration code</span>
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
                                onChatAsCustomer(agent.id, agent.user_id!);
                              }}
                            >
                              <MessageCircle className="mr-2 h-4 w-4" /> Chat as Customer
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
          })}
        </div>
      </div>
    </div>
  );
};

export default AgentList;
import { MessageCircleMore, CircleCheckBig, Clock, DollarSign } from "lucide-react";
import { Card } from "@/components/card";
import { useState, useEffect } from "react";
import { AgentDetailsDialog } from "./AgentDetailsDialog";
import { fetchDashboardAgents } from "@/services/dashboard";
import type { AgentStatsItem } from "@/interfaces/dashboard.interface";
import { useNavigate } from "react-router-dom";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";

interface AgentStats {
  id: string;
  name: string;
  conversationsToday: number;
  resolutionRate: number;
  avgResponseTime: string;
  costPerConversation: number;
  // Extended fields for modal
  description?: string;
  isActive?: boolean;
  welcomeMessage?: string;
  possibleQueries?: string[];
  workflowId?: string;
}

interface YourAgentsCardProps {
  agents?: AgentStats[];
  loading?: boolean;
  onViewAll?: () => void;
  onManageKeys?: (agentId: string) => void;
}

const formatResponseTime = (ms: number): string => {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
};

const transformApiAgent = (agent: AgentStatsItem): AgentStats => ({
  id: agent.id,
  name: agent.name,
  conversationsToday: agent.conversations_today,
  resolutionRate: Number(agent.resolution_rate) || 0,
  avgResponseTime: formatResponseTime(agent.avg_response_time_ms),
  costPerConversation: Number(agent.cost) || 0,
  isActive: agent.is_active,
});

export function YourAgentsCard({ agents: propAgents, loading: propLoading, onViewAll, onManageKeys }: YourAgentsCardProps) {
  const navigate = useNavigate();
  const showCostPerConversation = useFeatureFlagVisible(
    FeatureFlags.ANALYTICS.SHOW_COST_PER_CONVERSATION
  );
  const [selectedAgent, setSelectedAgent] = useState<AgentStats | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [agents, setAgents] = useState<AgentStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If agents are passed as props, use them
    if (propAgents) {
      setAgents(propAgents);
      setLoading(propLoading || false);
      return;
    }

    // Otherwise fetch from API
    const fetchAgents = async () => {
      setLoading(true);
      try {
        const response = await fetchDashboardAgents();
        if (response?.agents) {
          setAgents(response.agents.map(transformApiAgent));
        }
      } catch (error) {
        console.error("Error fetching agents:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, [propAgents, propLoading]);

  const handleAgentClick = (agent: AgentStats) => {
    setSelectedAgent(agent);
    setIsDialogOpen(true);
  };

  const handleViewAll = () => {
    if (onViewAll) {
      onViewAll();
    } else {
      navigate("/ai-agents");
    }
  };

  return (
    <Card className="bg-white border border-border rounded-xl overflow-hidden shadow-sm animate-fade-up">
      {/* Header */}
      <div className="bg-white flex items-center justify-between p-6">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-foreground">Your Agents</h3>
        </div>
        <button
          onClick={handleViewAll}
          className="text-sm font-medium text-foreground hover:underline"
        >
          View all
        </button>
      </div>

      {/* Agents List */}
      <div className="flex flex-col gap-2 px-4 pb-4">
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>No agents configured yet.</p>
            <button
              onClick={handleViewAll}
              className="mt-2 text-sm text-primary hover:underline"
            >
              Create your first agent
            </button>
          </div>
        ) : (
          agents.map((agent) => (
            <div
              key={agent.id}
              className="flex gap-3 items-center p-2 hover:bg-muted/30 rounded-lg transition-colors cursor-pointer"
              onClick={() => handleAgentClick(agent)}
            >
              <div className="flex flex-col gap-1.5 flex-1 min-w-0">
                <p className="text-sm font-semibold text-accent-foreground truncate">
                  {agent.name}
                </p>

                {/* Stats Row */}
                <div className="flex gap-3 items-center flex-wrap">
                  <div className="flex gap-1 items-center">
                    <MessageCircleMore className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">
                      {agent.conversationsToday} Today
                    </span>
                  </div>

                  <div className="flex gap-1 items-center">
                    <CircleCheckBig className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">
                      {agent.resolutionRate.toFixed(2)}% resolved
                    </span>
                  </div>

                  <div className="flex gap-1 items-center">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">
                      {agent.avgResponseTime} avg
                    </span>
                  </div>

                  {showCostPerConversation && (
                    <div className="flex gap-1 items-center">
                      <DollarSign className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">
                        ${agent.costPerConversation.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <AgentDetailsDialog
        agent={selectedAgent}
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onManageKeys={onManageKeys}
      />
    </Card>
  );
}

export default YourAgentsCard;

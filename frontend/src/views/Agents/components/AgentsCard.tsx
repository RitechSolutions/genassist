import { useState, useEffect } from "react";
import { Card } from "@/components/card";
import { ThumbsUp, Clock, Star, InfoIcon } from "lucide-react";
import { AgentDetailsDialog } from "./AgentDetailsDialog";
import { useLocation } from "react-router-dom";
import { fetchAgents } from "@/services/agents";
import { Agent } from "@/interfaces/agent.interface";
import { formatCallDuration } from "@/helpers/formatters";
import { CardHeader } from "@/components/CardHeader";

export function AgentsCard({ searchQuery }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [imageErrors, setImageErrors] = useState(new Set());

  const location = useLocation();
  const isDashboard = location.pathname === "/dashboard";

  useEffect(() => {
    const getAgents = async () => {
      const rawData = await fetchAgents();

      const sortedAgents = rawData.sort((a, b) => {
        const sentimentA = a.operator_statistics?.positive ?? 0;
        const sentimentB = b.operator_statistics?.positive ?? 0;

        if (sentimentB !== sentimentA) {
          return sentimentB - sentimentA;
        }
        return (b.operator_statistics.score ?? 0) - (a.operator_statistics.score ?? 0);
      });

      setAgents(isDashboard ? sortedAgents.slice(0, 5) : sortedAgents);
      
      setAgents(sortedAgents);
    };

    getAgents();
  }, [isDashboard]);

  function getInitials(firstName = "", lastName = "") {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  }

  const handleImageError = (agentId) => {
    setImageErrors((prevErrors) => new Set(prevErrors).add(agentId));
  };

  let filteredAgents = searchQuery
  ? agents.filter(
      (agent) =>
        agent.firstName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.lastName?.toLowerCase().includes(searchQuery.toLowerCase())
    )
  : agents;

  if (isDashboard) {
    filteredAgents = filteredAgents.slice(0, 5);
  }

  return (
    <>
      <Card className="p-6 shadow-sm transition-shadow hover:shadow-md animate-fade-up bg-white">
        <CardHeader 
          title={isDashboard ? "Top Performing Operators" : ""}
          tooltipText={isDashboard ? "Operators ranked by customer satisfaction scores and overall performance metrics" : undefined}
          linkText={isDashboard ? "View all" : undefined}
          linkHref={isDashboard ? "/operators" : undefined}
        />

        <div className="space-y-6">
          {filteredAgents.length > 0 ? (
            filteredAgents.map((agent, index) => (
              <div
                key={index}
                className="flex items-center gap-4 p-3 rounded-lg transition-colors hover:bg-secondary/50 cursor-pointer"
                onClick={() => {
                  setSelectedAgent(agent);
                  setIsModalOpen(true);
                }}
              >
                {!imageErrors.has(index) && agent.avatar ? (
                  <img
                    src={agent.avatar}
                    alt={`${agent.firstName} ${agent.lastName}`}
                    className="w-10 h-10 rounded-full object-cover border border-gray-300"
                    onError={() => handleImageError(index)}
                  />
                ) : (
                  <div className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-300 text-gray-700 font-bold">
                    {getInitials(agent.firstName, agent.lastName)}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium truncate">
                    {agent.firstName} {agent.lastName}
                  </h3>
                  <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <ThumbsUp className="w-4 h-4" />
                      <span>{agent.operator_statistics?.positive ?? 0}%</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      <span>{formatCallDuration(agent.operator_statistics?.totalCallDuration)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Star className="w-4 h-4 text-yellow-400" />
                      <span>{agent.operator_statistics?.score ?? 0}</span>
                    </div>
                  </div>
                </div>
                <div className="text-sm font-medium">
                  {agent.operator_statistics?.callCount ?? 0} calls
                </div>
              </div>
            ))
          ) : (
            <p className="text-center text-gray-500">No operators found</p>
          )}
        </div>
      </Card>

      <AgentDetailsDialog
        agent={selectedAgent}
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
      />
    </>
  );
}

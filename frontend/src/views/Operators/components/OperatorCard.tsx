import { useState, useEffect } from "react";
import { Card } from "@/components/card";
import { ThumbsUp, Clock, Star, InfoIcon } from "lucide-react";
import { OperatorDetailsDialog } from "./OperatorDetailsDialog";
import { useLocation } from "react-router-dom";
import { fetchOperators } from "@/services/operators";
import { Operator } from "@/interfaces/operator.interface";
import { formatCallDuration } from "@/helpers/formatters";
import { CardHeader } from "@/components/CardHeader";

export function OperatorsCard({ searchQuery, refreshKey }) {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Operator | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [imageErrors, setImageErrors] = useState(new Set());

  const location = useLocation();
  const isDashboard = location.pathname === "/dashboard";

  useEffect(() => {
    const getOperators = async () => {
      const rawData = await fetchOperators();

      const sortedOperators = rawData.sort((a, b) => {
        const sentimentA = a.operator_statistics?.positive ?? 0;
        const sentimentB = b.operator_statistics?.positive ?? 0;

        if (sentimentB !== sentimentA) {
          return sentimentB - sentimentA;
        }
        return (b.operator_statistics.score ?? 0) - (a.operator_statistics.score ?? 0);
      });

      setOperators(isDashboard ? sortedOperators.slice(0, 5) : sortedOperators);
      
      setOperators(sortedOperators);
    };

    getOperators();
  }, [isDashboard, refreshKey]);

  function getInitials(firstName = "", lastName = "") {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  }

  const handleImageError = (agentId) => {
    setImageErrors((prevErrors) => new Set(prevErrors).add(agentId));
  };

  let filteredAgents = searchQuery
  ? operators.filter(
      (agent) =>
        agent.firstName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.lastName?.toLowerCase().includes(searchQuery.toLowerCase())
    )
  : operators;

  if (isDashboard) {
    filteredAgents = filteredAgents.slice(0, 5);
  }

  return (
    <>
      <Card className="p-4 shadow-sm animate-fade-up bg-white">
        <CardHeader 
          title={isDashboard ? "Top Performing Operators" : ""}
          tooltipText={isDashboard ? "Operators ranked by customer satisfaction scores and overall performance metrics" : undefined}
          linkText={isDashboard ? "View all" : undefined}
          linkHref={isDashboard ? "/operators" : undefined}
        />

        <div className="space-y-2">
          {filteredAgents.length > 0 ? (
            filteredAgents.map((agent, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-2 rounded-lg transition-colors hover:bg-muted/30 cursor-pointer"
                onClick={() => {
                  setSelectedAgent(agent);
                  setIsModalOpen(true);
                }}
              >
                {!imageErrors.has(index) && agent.avatar ? (
                  <img
                    src={agent.avatar}
                    alt={`${agent.firstName} ${agent.lastName}`}
                    className="w-10 h-10 rounded-full object-cover shrink-0"
                    onError={() => handleImageError(index)}
                  />
                ) : (
                  <div className="w-10 h-10 flex items-center justify-center rounded-full bg-muted text-muted-foreground text-sm font-semibold shrink-0">
                    {getInitials(agent.firstName, agent.lastName)}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-accent-foreground truncate">
                    {agent.firstName} {agent.lastName}
                  </h3>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <div className="flex items-center gap-1">
                      <ThumbsUp className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">{agent.operator_statistics?.positive ?? 0}%</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">{formatCallDuration(agent.operator_statistics?.totalCallDuration)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 text-yellow-400" />
                      <span className="text-xs text-muted-foreground">{agent.operator_statistics?.score ?? 0}</span>
                    </div>
                  </div>
                </div>
                <div className="text-xs font-medium text-muted-foreground shrink-0">
                  {agent.operator_statistics?.callCount ?? 0} calls
                </div>
              </div>
            ))
          ) : (
            <p className="text-center text-muted-foreground text-sm py-8">No operators found</p>
          )}
        </div>
      </Card>

      <OperatorDetailsDialog
        operator={selectedAgent}
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
      />
    </>
  );
}

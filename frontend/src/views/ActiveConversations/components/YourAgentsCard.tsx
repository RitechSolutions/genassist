import { MessageCircleMore, CircleCheckBig, Clock, DollarSign } from "lucide-react";
import { Card } from "@/components/card";
import { useState } from "react";
import { AgentDetailsDialog } from "./AgentDetailsDialog";

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

const mockAgents: AgentStats[] = [
  {
    id: "1",
    name: "Customer Support Agent",
    conversationsToday: 55,
    resolutionRate: 98.95,
    avgResponseTime: "1.1s",
    costPerConversation: 2.86,
    description: "Handles customer inquiries and provides support across multiple channels",
    isActive: true,
    welcomeMessage: "Hello! I'm here to help you with any questions or issues you may have. How can I assist you today?",
    possibleQueries: [
      "How do I reset my password?",
      "What's the status of my order?",
      "How can I contact customer support?",
      "Do you offer refunds?"
    ],
    workflowId: "workflow-1",
  },
  {
    id: "2",
    name: "Sales Assistant",
    conversationsToday: 55,
    resolutionRate: 98.95,
    avgResponseTime: "1.1s",
    costPerConversation: 2.86,
    description: "Engages with potential customers and helps them find the right products",
    isActive: true,
    welcomeMessage: "Hi there! I'm your sales assistant. Let me help you find the perfect solution for your needs.",
    possibleQueries: [
      "What are your pricing plans?",
      "Can you show me a product demo?",
      "What features are included?",
      "Do you offer enterprise solutions?"
    ],
    workflowId: "workflow-2",
  },
  {
    id: "3",
    name: "Data Analyst Agent",
    conversationsToday: 55,
    resolutionRate: 98.95,
    avgResponseTime: "1.1s",
    costPerConversation: 2.86,
    description: "Analyzes data and provides insights based on your queries",
    isActive: false,
    welcomeMessage: "Welcome! I can help you analyze data and generate insights. What would you like to explore?",
    possibleQueries: [
      "Show me last month's sales trends",
      "What's the customer retention rate?",
      "Generate a performance report",
      "Compare Q1 vs Q2 metrics"
    ],
    workflowId: "workflow-3",
  },
  {
    id: "4",
    name: "Email Automation Agent",
    conversationsToday: 55,
    resolutionRate: 98.95,
    avgResponseTime: "1.1s",
    costPerConversation: 2.86,
    description: "Automates email workflows and manages customer communications",
    isActive: true,
    welcomeMessage: "Hello! I manage email automation workflows. How can I help you set up or manage your email campaigns?",
    possibleQueries: [
      "Send a welcome email to new users",
      "Schedule a follow-up campaign",
      "Create an abandoned cart email",
      "Set up a newsletter"
    ],
    workflowId: "workflow-4",
  },
];

export function YourAgentsCard({ agents = mockAgents, loading, onViewAll, onManageKeys }: YourAgentsCardProps) {
  const [selectedAgent, setSelectedAgent] = useState<AgentStats | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleAgentClick = (agent: AgentStats) => {
    setSelectedAgent(agent);
    setIsDialogOpen(true);
  };

  return (
    <Card className="bg-white border border-border rounded-xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="bg-white flex items-center justify-between p-6">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-foreground">Your Agents</h3>
        </div>
        <button
          onClick={onViewAll}
          className="text-sm font-medium text-foreground hover:underline"
        >
          View all
        </button>
      </div>

      {/* Agents List */}
      <div className="flex flex-col gap-1 px-2 pb-3">
        {loading ? (
          <div className="space-y-2 p-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : (
          agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-white rounded-lg px-4 py-3 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer"
              onClick={() => handleAgentClick(agent)}
            >
              <div className="flex flex-col gap-2 flex-1">
                <p className="text-base font-medium text-foreground">{agent.name}</p>
                
                {/* Stats Row */}
                <div className="flex gap-4 items-center">
                  <div className="flex gap-1 items-center">
                    <MessageCircleMore className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs text-card-foreground">
                      {agent.conversationsToday} Today
                    </span>
                  </div>
                  
                  <div className="flex gap-1 items-center">
                    <CircleCheckBig className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs text-card-foreground">
                      {agent.resolutionRate}% resolved
                    </span>
                  </div>
                  
                  <div className="flex gap-1 items-center">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs text-card-foreground">
                      {agent.avgResponseTime} avg
                    </span>
                  </div>
                  
                  <div className="flex gap-1 items-center">
                    <DollarSign className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs text-card-foreground">
                      ${agent.costPerConversation}
                    </span>
                  </div>
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

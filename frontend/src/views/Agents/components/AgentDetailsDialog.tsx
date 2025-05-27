import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { AgentAvatar } from "@/views/Agents/components/AgentAvatar";
import { KpiMetrics } from "@/views/Agents/components/KpiMetrics";
import { PerformanceMetrics } from "@/views/Agents/components/PerformanceMetrics";
import { SentimentDistribution } from "@/components/metrics/SentimentDistribution";
import { LatestCallDetails } from "@/views/Agents/components/LatestCallDetails";
import { Agent, AgentDetailsDialogProps } from "@/interfaces/agent.interface";
import { useState, useEffect } from "react";
import { fetchTranscripts } from "@/services/transcripts";
import { getLatestTranscript, createConversationAnalysis } from "../utils/agentAnalysis";

export function AgentDetailsDialog({ agent, isOpen, onOpenChange }: AgentDetailsDialogProps) {
  const [agentWithLatestCall, setAgentWithLatestCall] = useState<Agent | null>(null);
  
  useEffect(() => {
    if (!agent) return;
    
    const callCount = agent.operator_statistics?.callCount ?? 0;
    
    const fetchLatestTranscriptData = async () => {
      if (callCount < 2 || agent.latest_conversation_analysis) {
        setAgentWithLatestCall({...agent});
        return;
      }
      
      try {
        const transcripts = await fetchTranscripts();
        const latestTranscript = getLatestTranscript(transcripts);
        
        if (!latestTranscript) {
          setAgentWithLatestCall({...agent});
          return;
        }
        
        const conversationAnalysis = createConversationAnalysis(latestTranscript, agent);
        setAgentWithLatestCall({
          ...agent,
          latest_conversation_analysis: conversationAnalysis
        });
      } catch {
        setAgentWithLatestCall({...agent});
      }
    };
    
    fetchLatestTranscriptData();
  }, [agent]);

  if (!agent || !agentWithLatestCall) return null;
  
  const callCount = agent.operator_statistics?.callCount ?? 0;
  const shouldShowLatestCall = callCount >= 2;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-4">
            <AgentAvatar 
              firstName={agent.firstName} 
              lastName={agent.lastName} 
              avatarUrl={agent.avatar} 
              size="lg" 
            />
            <div>
              <h2 className="text-xl font-semibold">
                {agent.firstName} {agent.lastName}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">Operator Profile</p>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          <KpiMetrics agent={agent} />
          
          <PerformanceMetrics agent={agent} />
          
          <SentimentDistribution 
            positive={agent.operator_statistics?.positive ?? 0}
            neutral={agent.operator_statistics?.neutral ?? 0}
            negative={agent.operator_statistics?.negative ?? 0}
          />
          
          {shouldShowLatestCall && (
            <LatestCallDetails agent={agentWithLatestCall} />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
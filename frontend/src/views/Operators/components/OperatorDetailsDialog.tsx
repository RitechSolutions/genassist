import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { OperatorAvatar } from "@/views/Operators/components/OperatorAvatar";
import { KpiMetrics } from "@/views/Operators/components/KpiMetrics";
import { PerformanceMetrics } from "@/views/Operators/components/PerformanceMetrics";
import { SentimentDistribution } from "@/components/metrics/SentimentDistribution";
import { LatestCallDetails } from "@/views/Operators/components/LatestCallDetails";
import { Operator, OperatorDetailsDialogProps } from "@/interfaces/operator.interface";
import { useState, useEffect } from "react";
import { fetchTranscripts } from "@/services/transcripts";
import { getLatestTranscript, createConversationAnalysis } from "../utils/operatorAnalysis";

export function OperatorDetailsDialog({ operator, isOpen, onOpenChange }: OperatorDetailsDialogProps) {
  const [operatorWithLatestCall, setOperatorWithLatestCall] = useState<Operator | null>(null);
  
  useEffect(() => {
    if (!operator) return;
    
    const callCount = operator.operator_statistics?.callCount ?? 0;
    
    const fetchLatestTranscriptData = async () => {
      if (callCount < 2 || operator.latest_conversation_analysis) {
        setOperatorWithLatestCall({...operator});
        return;
      }
      
      // Without an id we cannot scope the lookup, and an unfiltered fetch would
      // surface some other operator's conversation as this operator's latest.
      if (!operator.id) {
        setOperatorWithLatestCall({...operator});
        return;
      }

      try {
        const { items: transcripts } = await fetchTranscripts({
          operator_id: operator.id,
          limit: 1,
          order_by: "created_at",
          sort_direction: "desc",
        });
        const latestTranscript = getLatestTranscript(transcripts);
        
        if (!latestTranscript) {
          setOperatorWithLatestCall({...operator});
          return;
        }
        
        const conversationAnalysis = createConversationAnalysis(latestTranscript, operator);
        setOperatorWithLatestCall({
          ...operator,
          latest_conversation_analysis: conversationAnalysis
        });
      } catch {
        setOperatorWithLatestCall({...operator});
      }
    };
    
    fetchLatestTranscriptData();
  }, [operator]);

  if (!operator || !operatorWithLatestCall) return null;
  
  const callCount = operator.operator_statistics?.callCount ?? 0;
  const shouldShowLatestCall = callCount >= 2;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl 2xl:max-w-[960px] min-[1920px]:max-w-[1120px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-4">
            <OperatorAvatar 
              firstName={operator.firstName} 
              lastName={operator.lastName} 
              avatarUrl={operator.avatar} 
              size="lg" 
            />
            <div>
              <h2 className="text-xl font-semibold">
                {operator.firstName} {operator.lastName}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">Operator Profile</p>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          <KpiMetrics operator={operator} />
          
          <PerformanceMetrics operator={operator} />
          
          <SentimentDistribution 
            positive={operator.operator_statistics?.positive ?? 0}
            neutral={operator.operator_statistics?.neutral ?? 0}
            negative={operator.operator_statistics?.negative ?? 0}
          />
          
          {shouldShowLatestCall && (
            <LatestCallDetails operator={operatorWithLatestCall} />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
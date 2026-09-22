import { Phone } from "lucide-react";
import { formatCallDuration, formatTimeAgo } from "@/helpers/formatters";
import { Operator } from "@/interfaces/operator.interface";

interface LatestCallDetailsProps {
  operator: Operator;
}

export function LatestCallDetails({ operator }: LatestCallDetailsProps) {
  if (!operator.latest_conversation_analysis) return null;

  const callDuration = formatCallDuration(operator.latest_conversation_analysis.duration);

  const agentRatio = operator.latest_conversation_analysis.agent_ratio ?? 0;
  const customerRatio = operator.latest_conversation_analysis.customer_ratio ?? 100 - agentRatio;

  const customerSatisfaction = operator.latest_conversation_analysis.analysis?.customer_satisfaction !== undefined
    ? `${operator.latest_conversation_analysis.analysis.customer_satisfaction * 10}%`
    : operator.operator_statistics?.avg_customer_satisfaction || "N/A";

  return (
    <div className="bg-primary/5 p-4 rounded-lg">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Phone className="w-4 h-4" />
        Latest Call Details
      </h3>
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Duration:</span>
          <span>{callDuration}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Time:</span>
          <span>
            {formatTimeAgo(operator.latest_conversation_analysis.created_at || operator.created_at)}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Customer Satisfaction:</span>
          <span>{customerSatisfaction}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Speaking Ratio:</span>
          <span>
            Operator {agentRatio}% / Customer {customerRatio}%
          </span>
        </div>
      </div>
    </div>
  );
} 
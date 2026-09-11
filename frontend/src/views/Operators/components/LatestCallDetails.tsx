import { MessageSquare } from "lucide-react";
import { formatCallDuration, formatTimeAgo, parsePercentValue } from "@/helpers/formatters";
import { Operator } from "@/interfaces/operator.interface";

interface LatestCallDetailsProps {
  operator: Operator;
}

export function LatestCallDetails({ operator }: LatestCallDetailsProps) {
  if (!operator.latest_conversation_analysis) return null;

  const callDuration = formatCallDuration(operator.latest_conversation_analysis.duration);

  const { agent_ratio: agentRatioRaw, customer_ratio: customerRatioRaw } =
    operator.latest_conversation_analysis;

  // Conversations are created with 0/0 placeholders and only get real ratios once
  // the transcript is scored, so 0/0 means "not computed yet", not "nobody spoke".
  const hasSpeakingRatio =
    (typeof agentRatioRaw === "number" && agentRatioRaw > 0) ||
    (typeof customerRatioRaw === "number" && customerRatioRaw > 0);

  const agentRatio =
    typeof agentRatioRaw === "number" ? agentRatioRaw : 100 - (customerRatioRaw ?? 0);
  const customerRatio =
    typeof customerRatioRaw === "number" ? customerRatioRaw : 100 - (agentRatioRaw ?? 0);

  // Conversation-level satisfaction is 0-10; the operator average is already a percent.
  const conversationSatisfaction = parsePercentValue(
    operator.latest_conversation_analysis.analysis?.customer_satisfaction
  );
  const averageSatisfaction = parsePercentValue(
    operator.operator_statistics?.avg_customer_satisfaction
  );

  const customerSatisfaction =
    conversationSatisfaction !== null
      ? `${Math.round(conversationSatisfaction * 10 * 10) / 10}%`
      : averageSatisfaction !== null
        ? `${averageSatisfaction}%`
        : "N/A";

  return (
    <div className="bg-primary/5 p-4 rounded-lg">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <MessageSquare className="w-4 h-4" />
        Latest Conversation Details
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
            {hasSpeakingRatio
              ? `Operator ${agentRatio}% / Customer ${customerRatio}%`
              : "N/A"}
          </span>
        </div>
      </div>
    </div>
  );
} 
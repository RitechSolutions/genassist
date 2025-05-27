import { Clock, Star, Phone } from "lucide-react";
import { MetricCard } from "@/components/metrics/MetricCard";
import { formatCallDuration } from "@/helpers/formatters";
import { Agent } from "@/interfaces/agent.interface";

interface PerformanceMetricsProps {
  agent: Agent;
}

export function PerformanceMetrics({ agent }: PerformanceMetricsProps) {
  const callCount = agent.operator_statistics?.callCount ?? 0;
  const callDuration = formatCallDuration(agent.operator_statistics?.totalCallDuration);
  const rating = agent.operator_statistics?.score ?? 0;
  
  return (
    <div className="grid grid-cols-3 gap-4">
      <MetricCard
        icon={<Phone className="w-5 h-5" />}
        value={callCount}
        label="Total Calls"
      />
      
      <MetricCard
        icon={<Clock className="w-5 h-5" />}
        value={callDuration}
        label="Total Calls"
      />
      
      <MetricCard
        icon={<Star className="w-5 h-5" />}
        value={rating}
        label="Average Rating"
        iconColor="text-yellow-400"
      />
    </div>
  );
} 
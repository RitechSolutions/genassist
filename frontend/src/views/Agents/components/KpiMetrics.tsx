import { ThumbsUp, Clock4, CircleCheckBig } from "lucide-react";
import { MetricCard } from "@/components/metrics/MetricCard";
import { Agent } from "@/interfaces/agent.interface";

interface KpiMetricsProps {
  agent: Agent;
}

export function KpiMetrics({ agent }: KpiMetricsProps) {
  const stats = agent.operator_statistics || {};
  
  const responseTime = stats.avg_response_time 
  const satisfaction = stats.avg_customer_satisfaction;
  const serviceQuality = stats.avg_quality_of_service;
  const resolutionRate = stats.avg_resolution_rate;
  
  return (
    <div className="grid grid-cols-4 gap-3">
      <MetricCard
        icon={<Clock4 className="w-5 h-5" />}
        value={responseTime}
        label="Responsiveness"
        iconColor="text-black"
      />
      
      <MetricCard
        icon={<ThumbsUp className="w-5 h-5" />}
        value={satisfaction}
        label="Satisfaction"
        iconColor="text-green-600"
      />
      
      <MetricCard
        icon={<Clock4 className="w-5 h-5" />}
        value={serviceQuality}
        label="Service Quality"
        iconColor="text-blue-600"
      />
      
      <MetricCard
        icon={<CircleCheckBig className="w-5 h-5" />}
        value={resolutionRate}
        label="Resolution Rate"
        iconColor="text-red-600"
      />
    </div>
  );
} 
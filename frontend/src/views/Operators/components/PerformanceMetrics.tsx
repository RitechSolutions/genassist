import { Clock, Star, Phone } from "lucide-react";
import { MetricCard } from "@/components/metrics/MetricCard";
import { formatCallDuration } from "@/helpers/formatters";
import { Operator } from "@/interfaces/operator.interface";

interface PerformanceMetricsProps {
  operator: Operator;
}

export function PerformanceMetrics({ operator }: PerformanceMetricsProps) {
  const callCount = operator.operator_statistics?.callCount ?? 0;
  const callDuration = formatCallDuration(operator.operator_statistics?.totalCallDuration);
  const rating = operator.operator_statistics?.score ?? 0;
  
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
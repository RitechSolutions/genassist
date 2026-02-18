import { LucideIcon, Timer, MessageCircle, Volume2, TrendingUp } from "lucide-react";
import { ReactNode } from "react";
import { TranscriptMetrics } from "@/interfaces/transcript.interface";
import { formatDuration } from "../helpers/formatting";

type MetricCardProps = {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  className?: string;
  iconClassName?: string;
};

export function MetricCard({
  icon: Icon,
  label,
  value,
  className = "",
  iconClassName = "",
}: MetricCardProps) {
  return (
    <div className={`flex flex-col items-center p-3 bg-gray-100 rounded-lg ${className}`}>
      <Icon className={`w-5 h-5 mb-1 text-primary ${iconClassName}`} />
      <div className="text-sm font-medium">{value}</div>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

type MetricCardsProps = {
  duration: number;
  wordCount: number;
  sentiment: string;
  speakingRatio: TranscriptMetrics["speakingRatio"];
  className?: string;
};

export function MetricCards({
  duration,
  wordCount,
  sentiment,
  speakingRatio,
  className = "",
}: MetricCardsProps) {
  return (
    <div className={`grid grid-cols-2 gap-4 ${className}`}>
      <MetricCard
        icon={Timer}
        label="Duration"
        value={formatDuration(Number(duration))}
      />
      <MetricCard
        icon={MessageCircle}
        label="Words"
        value={wordCount}
      />
      <MetricCard
        icon={Volume2}
        label="Sentiment"
        value={
          <span className="px-2 py-0.5 text-xs font-normal rounded-full bg-yellow-100 text-orange-600 mb-1 capitalize">
            {sentiment}
          </span>
        }
      />
      <MetricCard
        icon={TrendingUp}
        label="Operator/Customer Ratio"
        value={`${speakingRatio.agent}% / ${speakingRatio.customer}%`}
      />
    </div>
  );
}

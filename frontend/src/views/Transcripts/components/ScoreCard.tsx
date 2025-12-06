import { LucideIcon, ThumbsUp, Clock, CheckCircle } from "lucide-react";
import { TranscriptMetrics } from "@/interfaces/transcript.interface";

type ScoreCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  className?: string;
  iconClassName?: string;
};

export function ScoreCard({
  icon: Icon,
  label,
  value,
  className = "",
  iconClassName = "",
}: ScoreCardProps) {
  return (
    <div className={`flex bg-gray-100 rounded-xl p-4 ${className}`}>
      <Icon className={`w-5 h-5 mt-1 ${iconClassName}`} />
      <div className="flex flex-col justify-start items-start ml-3">
        <span className="text-sm font-semibold leading-tight">{value}</span>
        <span className="text-sm">{label}</span>
      </div>
    </div>
  );
}

type ScoreCardsProps = {
  metrics: TranscriptMetrics;
  className?: string;
};

const formatScorePercentage = (value: number) =>
  value > 0 ? `${Math.round((value / 10) * 100)}%` : "0%";

export function ScoreCards({ metrics, className = "" }: ScoreCardsProps) {
  return (
    <div className={`grid grid-cols-2 gap-4 ${className}`}>
      <ScoreCard
        icon={ThumbsUp}
        label="Satisfaction"
        value={formatScorePercentage(metrics.customerSatisfaction)}
        iconClassName="text-green-600"
        className="w-full"
      />

      <ScoreCard
        icon={Clock}
        label="Service Quality"
        value={formatScorePercentage(metrics.serviceQuality)}
        iconClassName="text-purple-600"
        className="w-full"
      />

      <ScoreCard
        icon={CheckCircle}
        label="Resolution Rate"
        value={formatScorePercentage(metrics.resolutionRate)}
        iconClassName="text-red-600"
        className="col-span-2 w-full"
      />
    </div>
  );
}
import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { generateTimeData } from "../helpers/timeDataGenerator";
import { MetricsAPIResponse } from "@/interfaces/analytics.interface";
import { StatsOverviewCard } from "./StatsOverviewCard";

interface MetricsSectionProps {
  timeFrame: string;
  metrics: MetricsAPIResponse | null;
  loading: boolean;
  error: Error | null;
}

export const MetricsSection = ({ timeFrame, metrics, loading, error }: MetricsSectionProps) => {
  const defaultMetrics = {
    "Customer Satisfaction": "0%",
    "Resolution Rate": "0%",
    "Positive Sentiment": "0%",
    "Neutral Sentiment": "0%",
    "Negative Sentiment": "0%",
    "Efficiency": "0%",
    "Response Time": "0%",
    "Quality of Service": "0%",
    "total_analyzed_audios": 0,
  };

  const formattedData = metrics || defaultMetrics;

  // Transform metrics data for the new stats overview card
  const statsMetrics = [
    {
      label: "Active Agents",
      value: "24",
      change: 0,
      changeType: "neutral" as const,
    },
    {
      label: "Workflow Runs",
      value: "1,847",
      change: 12,
      changeType: "decrease" as const,
    },
    {
      label: "Avg Response Time",
      value: formattedData["Response Time"],
      change: 4,
      changeType: "decrease" as const,
    },
    {
      label: "Usage",
      value: "~$48.00",
      change: 16,
      changeType: "increase" as const,
    },
  ];

  if (loading) {
    return <div className="text-center py-8">Loading analytics data...</div>;
  }

  if (error) {
    return <div className="text-center py-8 text-red-500">Error loading analytics data</div>;
  }

  return (
    <>
      <StatsOverviewCard metrics={statsMetrics} />

      <div className="mt-6 sm:mt-8">
        <PerformanceChart timeSeriesData={generateTimeData(timeFrame)} />
      </div>
    </>
  );
}; 
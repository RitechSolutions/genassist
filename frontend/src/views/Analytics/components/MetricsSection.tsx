import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { generateTimeData } from "../helpers/timeDataGenerator";
import { MetricsAPIResponse } from "@/interfaces/analytics.interface";
import { StatsOverviewCard } from "./StatsOverviewCard";
import { getAllAgentConfigs } from "@/services/api";
import { useState, useEffect } from "react";
import { formatResponseTime } from "../helpers/timeFormatter";

interface MetricsSectionProps {
  timeFrame: string;
  metrics: MetricsAPIResponse | null;
  loading: boolean;
  error: Error | null;
}

export const MetricsSection = ({
  timeFrame,
  metrics,
  loading,
  error,
}: MetricsSectionProps) => {
  const [activeAgentsCount, setActiveAgentsCount] = useState<number>(0);

  useEffect(() => {
    const getActiveAgentsCount = async () => {
      try {
        const agents = await getAllAgentConfigs();
        const activeCount = agents.filter((agent) => agent.is_active).length;
        setActiveAgentsCount(activeCount);
      } catch (err) {
        // ignore error, keep default value
      }
    };

    getActiveAgentsCount();
  }, []);

  const defaultMetrics = {
    "Response Time": "0%",
  };

  const formattedData = metrics || defaultMetrics;

  // Transform metrics data for the new stats overview card
  const statsMetrics = [
    {
      label: "Active Agents",
      value: activeAgentsCount.toString(),
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
      value: formatResponseTime(formattedData["Response Time"]),
      change: 4,
      changeType: "decrease" as const,
    },
    // {
    //   label: "Usage",
    //   value: "~$48.00",
    //   change: 16,
    //   changeType: "increase" as const,
    // },
  ];

  if (loading) {
    return <div className="text-center py-8">Loading analytics data...</div>;
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        Error loading analytics data
      </div>
    );
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
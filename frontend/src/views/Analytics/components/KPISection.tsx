import { useState, useEffect } from "react";
import { fetchMetrics, FetchedMetricsData } from "@/services/metrics";
import { StatsOverviewCard } from "./StatsOverviewCard";

import { usePermissions, useIsLoadingPermissions } from "@/context/PermissionContext";

interface KPISectionProps {
  timeFilter: string;
}

export function KPISection({ timeFilter }: KPISectionProps) {
  const permissions = usePermissions();
  const isLoadingPermissions = useIsLoadingPermissions();
  const [metrics, setMetrics] = useState<FetchedMetricsData | null>(null);

  useEffect(() => {
    const getMetrics = async () => {
      if (isLoadingPermissions) {
        return;
      }
      if (permissions.includes("read:metrics") || permissions.includes("*") ) {
        try {
          const data = await fetchMetrics();
          setMetrics(data);
        } catch (err) {
          // ignore
        }
      }
    };
  
    getMetrics();
  }, [isLoadingPermissions, permissions]);

  const defaultMetrics = {
    "Response Time": "0m",
    "Customer Satisfaction": "0%",
    "Quality of Service": "0%",
    "Resolution Rate": "0%",
    "Efficiency": "0%",
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

  return (
    <section className="mb-5">
      <StatsOverviewCard metrics={statsMetrics} />
    </section>
  );
} 
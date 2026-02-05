import { useState, useEffect } from "react";
import { StatsOverviewCard } from "./StatsOverviewCard";

import { usePermissions, useIsLoadingPermissions } from "@/context/PermissionContext";
import { fetchDashboardSummary, getFilterDays } from "@/services/dashboard";
import type { DashboardSummaryStats } from "@/interfaces/dashboard.interface";

interface KPISectionProps {
  timeFilter: string;
}

const formatResponseTime = (ms: number): string => {
  if (ms === 0) return "0ms";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60000)}m`;
};

const formatNumber = (num: number): string => {
  return num.toLocaleString();
};

export function KPISection({ timeFilter }: KPISectionProps) {
  const permissions = usePermissions();
  const isLoadingPermissions = useIsLoadingPermissions();
  const [summaryStats, setSummaryStats] = useState<DashboardSummaryStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      if (isLoadingPermissions) {
        return;
      }

      // Check for dashboard permission or wildcard
      if (permissions.includes("read:dashboard") || permissions.includes("*")) {
        setLoading(true);
        try {
          const days = getFilterDays(timeFilter);
          const data = await fetchDashboardSummary(days);
          setSummaryStats(data);
        } catch (err) {
          console.error("Error fetching dashboard summary:", err);
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    fetchStats();
  }, [isLoadingPermissions, permissions, timeFilter]);

  // Transform summary stats for the stats overview card
  const statsMetrics = [
    {
      label: "Active Agents",
      value: summaryStats?.active_agents?.toString() || "0",
      change: 0,
      changeType: "neutral" as const,
    },
    {
      label: "Workflow Runs",
      value: formatNumber(summaryStats?.workflow_runs || 0),
      change: 0,
      changeType: "neutral" as const,
    },
    {
      label: "Avg Response Time",
      value: formatResponseTime(summaryStats?.avg_response_time_ms || 0),
      change: 0,
      changeType: "neutral" as const,
    },
  ];

  return (
    <section className="mb-5">
      <StatsOverviewCard metrics={statsMetrics} loading={loading} />
    </section>
  );
}

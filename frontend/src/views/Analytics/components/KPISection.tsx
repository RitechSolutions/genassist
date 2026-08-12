import { useState, useEffect, useRef } from "react";
import type { DateRange } from "react-day-picker";
import { StatsOverviewCard } from "./StatsOverviewCard";

import { usePermissions, useIsLoadingPermissions } from "@/context/PermissionContext";
import { fetchDashboardSummary, type DashboardSummaryRange } from "@/services/dashboard";
import type { DashboardSummaryStats } from "@/interfaces/dashboard.interface";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import { formatUsd } from "@/helpers/formatCurrency";
import { toExactActivityParams } from "@/helpers/dateRange";

interface KPISectionProps {
  dateRange: DateRange | undefined;
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
/** No dates picked means show all-time, otherwise use the exact local-day range picked */ 
function toSummaryRange(dateRange: DateRange | undefined): DashboardSummaryRange {
  const { activity_from_datetime, activity_to_datetime } = toExactActivityParams(dateRange);
  if (!activity_from_datetime || !activity_to_datetime) return { all_time: true };
  return { from_datetime: activity_from_datetime, to_datetime: activity_to_datetime };
}

export function KPISection({ dateRange }: KPISectionProps) {
  const permissions = usePermissions();
  const isLoadingPermissions = useIsLoadingPermissions();
  const showCostPerConversation = useFeatureFlagVisible(
    FeatureFlags.ANALYTICS.SHOW_COST_PER_CONVERSATION
  );
  const [summaryStats, setSummaryStats] = useState<DashboardSummaryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const fromTime = dateRange?.from?.getTime();
  const toTime = dateRange?.to?.getTime();

  useEffect(() => {
    const fetchStats = async () => {
      if (isLoadingPermissions) {
        return;
      }

      // Check for dashboard permission or wildcard
      if (permissions.includes("read:dashboard") || permissions.includes("*")) {
        const currentRequest = ++requestId.current;
        setLoading(true);
        try {
          const data = await fetchDashboardSummary(toSummaryRange(dateRange));
          if (currentRequest !== requestId.current) return; // a newer range won
          setSummaryStats(data);
          setError(data ? null : "Summary unavailable");
        } catch (err) {
          console.error("Error fetching dashboard summary:", err);
          if (currentRequest !== requestId.current) return;
          setSummaryStats(null);
          setError("Summary unavailable");
        } finally {
          if (currentRequest === requestId.current) setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    fetchStats();
  }, [isLoadingPermissions, permissions, fromTime, toTime]);

  // Transform summary stats for the stats overview card
  const statsMetrics = [
    {
      label: "Active Agents",
      value: (summaryStats?.active_agents ?? 0).toString(),
      change: 0,
      changeType: "neutral" as const,
    },
    {
      label: "Conversations",
      value: formatNumber(summaryStats?.conversations ?? 0),
      change: 0,
      changeType: "neutral" as const,
    },
    {
      label: "Avg Response Time",
      value: formatResponseTime(summaryStats?.avg_response_time_ms ?? 0),
      change: 0,
      changeType: "neutral" as const,
    },
    ...(showCostPerConversation
      ? [
          {
            label: "LLM Costs",
            value: formatUsd(summaryStats?.total_cost_usd),
            change: 0,
            changeType: "neutral" as const,
          },
        ]
      : []),
  ];

  return (
    <section className="mb-5">
      <StatsOverviewCard metrics={statsMetrics} loading={loading} error={error} />
    </section>
  );
}

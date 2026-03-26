import { useState, useEffect, useRef, useTransition } from "react";
import {
  fetchMetrics,
  type FetchedMetricsData,
  type MetricsDeltas,
} from "@/services/metrics";
import { toMetricsApiParams } from "@/helpers/analyticsParams";
import type { DateRange } from "react-day-picker";

function computeDeltas(current: FetchedMetricsData, previous: FetchedMetricsData): MetricsDeltas {
  const keys = [
    "Customer Satisfaction",
    "Resolution Rate",
    "Positive Sentiment",
    "Negative Sentiment",
    "Efficiency",
    "Quality of Service",
  ] as const;
  const result: MetricsDeltas = {};
  for (const key of keys) {
    const curr = parseFloat(current[key] as string);
    const prev = parseFloat(previous[key] as string);
    if (!isNaN(curr) && !isNaN(prev) && prev !== 0) {
      result[key] = Math.round(((curr - prev) / prev) * 100 * 10) / 10;
    }
  }
  return result;
}

export const useAnalyticsData = (
  dateRange: DateRange | undefined,
  agentId?: string,
  compareDateRange?: DateRange,
) => {
  const [metrics, setMetrics] = useState<FetchedMetricsData | null>(null);
  const [deltas, setDeltas] = useState<MetricsDeltas | null>(null);
  const [initialLoading, setInitialLoading] = useState<boolean>(true);
  const [refreshing, startRefresh] = useTransition();
  const [error, setError] = useState<Error | null>(null);
  const fetchIdRef = useRef(0);

  useEffect(() => {
    const fetchId = ++fetchIdRef.current;
    const params = toMetricsApiParams(dateRange, agentId);

    const doFetch = async () => {
      try {
        const hasCompare = compareDateRange?.from && compareDateRange?.to;
        const compareParams = hasCompare
          ? toMetricsApiParams(compareDateRange, agentId)
          : undefined;

        const [current, previous] = await Promise.all([
          fetchMetrics(params),
          compareParams ? fetchMetrics(compareParams) : Promise.resolve(null),
        ]);

        if (fetchId !== fetchIdRef.current) return;
        setMetrics(current);
        setDeltas(current && previous ? computeDeltas(current, previous) : null);
        setError(null);
      } catch (err) {
        if (fetchId !== fetchIdRef.current) return;
        setError(err instanceof Error ? err : new Error("Failed to fetch metrics"));
      } finally {
        if (fetchId === fetchIdRef.current) {
          setInitialLoading(false);
        }
      }
    };

    if (metrics === null) {
      doFetch();
    } else {
      startRefresh(() => {
        doFetch();
      });
    }
  }, [dateRange?.from?.getTime(), dateRange?.to?.getTime(), agentId, compareDateRange?.from?.getTime(), compareDateRange?.to?.getTime()]);

  return { metrics, deltas, loading: initialLoading, refreshing, error };
};

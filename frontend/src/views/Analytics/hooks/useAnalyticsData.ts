import { useState, useEffect, useRef, useTransition } from "react";
import { fetchMetrics, type FetchedMetricsData } from "@/services/metrics";
import { toMetricsApiParams } from "@/helpers/analyticsParams";
import type { DateRange } from "react-day-picker";

export const useAnalyticsData = (dateRange: DateRange | undefined, agentId?: string) => {
  const [metrics, setMetrics] = useState<FetchedMetricsData | null>(null);
  const [initialLoading, setInitialLoading] = useState<boolean>(true);
  const [refreshing, startRefresh] = useTransition();
  const [error, setError] = useState<Error | null>(null);
  const fetchIdRef = useRef(0);

  useEffect(() => {
    const fetchId = ++fetchIdRef.current;
    const params = toMetricsApiParams(dateRange, agentId);

    const doFetch = async () => {
      try {
        const data = await fetchMetrics(params);
        if (fetchId !== fetchIdRef.current) return;
        setMetrics(data);
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
  }, [dateRange?.from?.getTime(), dateRange?.to?.getTime(), agentId]);

  return { metrics, loading: initialLoading, refreshing, error };
};

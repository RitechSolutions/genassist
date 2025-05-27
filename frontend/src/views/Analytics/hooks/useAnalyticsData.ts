import { useState, useEffect } from "react";
import { fetchMetrics } from "@/services/metrics";
import { MetricsAPIResponse } from "@/interfaces/analytics.interface";

export const useAnalyticsData = () => {
  const [metrics, setMetrics] = useState<MetricsAPIResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const getMetrics = async () => {
      try {
        setLoading(true);
        const data = await fetchMetrics();
        setMetrics(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Failed to fetch metrics"));
      } finally {
        setLoading(false);
      }
    };

    getMetrics();
  }, []);

  return { metrics, loading, error };
}; 
import { useCallback, useEffect, useState } from "react";
import { listLocalFineTuneJobs } from "@/services/localFineTune";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";

export function useLocalFineTuneJobs(refreshKey: number) {
  const [jobs, setJobs] = useState<LocalFineTuneJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listLocalFineTuneJobs();
      setJobs(data);
      setError(null);
    } catch {
      setError("Failed to fetch jobs");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchJobs();
  }, [refreshKey, fetchJobs]);

  return { jobs, setJobs, loading, error, refetch: fetchJobs };
}

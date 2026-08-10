import { useCallback, useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { listFineTuneJobs, syncFineTuneJobs } from "@/services/openaiFineTune";
import type { FineTuneJob } from "@/interfaces/fineTune.interface";

export function useFineTuneJobs(refreshKey: number) {
  const [jobs, setJobs] = useState<FineTuneJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      // Fast cached load — no sync. Press "Sync" to refresh status from OpenAI.
      const data = await listFineTuneJobs();
      setJobs(data);
      setError(null);
    } catch {
      setError("Failed to fetch jobs");
      toast.error("Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  const sync = useCallback(async () => {
    try {
      setSyncing(true);
      const data = await syncFineTuneJobs();
      setJobs(data);
      setError(null);
      toast.success("Jobs synced");
    } catch {
      toast.error("Failed to sync jobs");
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    void fetchJobs();
  }, [refreshKey, fetchJobs]);

  return { jobs, setJobs, loading, syncing, error, refetch: fetchJobs, sync };
}

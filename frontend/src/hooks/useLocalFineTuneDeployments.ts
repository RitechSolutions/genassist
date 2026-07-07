import { useCallback, useEffect, useState } from "react";
import { listDeployments } from "@/services/localFineTune";
import type { LocalFineTuneDeployment } from "@/interfaces/localFineTune.interface";

export function useLocalFineTuneDeployments(refreshKey: number) {
  const [deployments, setDeployments] = useState<LocalFineTuneDeployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDeployments = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listDeployments();
      setDeployments(data);
      setError(null);
    } catch {
      setError("Failed to fetch deployments");
      setDeployments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDeployments();
  }, [refreshKey, fetchDeployments]);

  return { deployments, setDeployments, loading, error, refetch: fetchDeployments };
}
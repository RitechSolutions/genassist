import { useCallback, useEffect, useState } from "react";

import {
  fetchReportedFeedback,
  FeedbackStatus,
  ReportedFeedbackItem,
} from "@/services/reportedFeedback";
import { usePermissions } from "@/context/PermissionContext";

interface UseReportedFeedbackOptions {
  skip?: number;
  limit?: number;
  status?: FeedbackStatus | "all";
  from_date?: string;
  to_date?: string;
  workflow_id?: string;
}

export const useReportedFeedback = (
  options: UseReportedFeedbackOptions = {},
) => {
  const { skip = 0, limit = 20, status = "all", from_date, to_date, workflow_id } =
    options;

  const [data, setData] = useState<ReportedFeedbackItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const permissions = usePermissions();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const { items, total: backendTotal } = await fetchReportedFeedback({
        skip,
        limit,
        status,
        from_date,
        to_date,
        workflow_id,
      });
      setData(items);
      setTotal(typeof backendTotal === "number" ? backendTotal : items.length);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err
          : new Error("Failed to fetch reported feedback"),
      );
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [skip, limit, status, from_date, to_date, workflow_id]);

  useEffect(() => {
    if (
      !permissions.includes("*") &&
      !permissions.includes("read:conversation")
    ) {
      return;
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchData]);

  return { data, total, loading, error, refetch: fetchData };
};

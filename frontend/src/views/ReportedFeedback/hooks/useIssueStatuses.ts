import { useQuery } from "@tanstack/react-query";

import { fetchIssueStatuses } from "@/services/issueStatuses";

/** The configured issue statuses in position order, retired ones included. */
export const useIssueStatuses = () =>
  useQuery({
    queryKey: ["issue-statuses"],
    queryFn: fetchIssueStatuses,
    staleTime: 5 * 60_000,
  });

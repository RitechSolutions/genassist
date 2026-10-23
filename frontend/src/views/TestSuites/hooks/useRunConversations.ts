import { useQuery } from "@tanstack/react-query";
import type { TestRun } from "@/interfaces/testSuite.interface";
import { getRunConversations } from "@/services/testSuites";

/** What changes a run's results: its status, and each conversation it finishes. */
export const runResultsVersion = (run: TestRun | null | undefined): string =>
  `${run?.status ?? ""}:${run?.progress?.conversations_done ?? 0}`;

/** A run's results by conversation, loaded once for each state of the run. */
export const useRunConversations = (run: TestRun | null | undefined) => {
  const runId = run?.id;
  const version = runResultsVersion(run);
  const query = useQuery({
    // Keyed on the run's state, so a failed reload is not retried in a loop.
    queryKey: ["run-conversations", runId, version],
    queryFn: () => getRunConversations(runId ?? ""),
    enabled: Boolean(runId),
    staleTime: Infinity,
    // The results shown so far stay up while the next ones load, never another run's.
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[1] === runId ? previous : undefined),
  });
  return { ...query, data: query.data ?? undefined };
};

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { QuestionRunStatus } from "@/interfaces/testSuite.interface";
import { getQuestionRunStatus } from "@/services/testSuites";
import {
  type FollowedRun,
  IDLE_RUN,
  NOTHING_FOLLOWED,
  afterFailedCheck,
  afterStatusAnswer,
  followedRunAfter,
  nextStatusCheckMs,
  statusProblemNote,
} from "../helpers/questionRun";

/**
 * The dataset's question-writing run, asked for again while it is in progress.
 * `onEnded` is called once when a run this page saw in progress has ended.
 */
export const useQuestionRun = (
  datasetId: string | undefined,
  onEnded: (run: QuestionRunStatus) => void,
) => {
  const queryClient = useQueryClient();
  const queryKey = useMemo(() => ["question-run", datasetId], [datasetId]);

  // A failed check is kept as a count next to the last answer, so the next check can be paced by it.
  const readStatus = useCallback(async (): Promise<FollowedRun> => {
    try {
      const answer = await getQuestionRunStatus(datasetId as string);
      return afterStatusAnswer(answer ?? IDLE_RUN);
    } catch {
      return afterFailedCheck(queryClient.getQueryData<FollowedRun>(queryKey));
    }
  }, [datasetId, queryClient, queryKey]);

  const { data } = useQuery({
    queryKey,
    queryFn: readStatus,
    enabled: Boolean(datasetId),
    staleTime: 0,
    refetchInterval: (query) => nextStatusCheckMs(query.state.data),
  });
  const followed = data ?? NOTHING_FOLLOWED;
  const run = followed.run ?? IDLE_RUN;

  const onEndedRef = useRef(onEnded);
  useEffect(() => {
    onEndedRef.current = onEnded;
  }, [onEnded]);

  // Remembered by id, so another dataset's run is never taken for this one's.
  const followedRunId = useRef<string | null>(null);
  useEffect(() => {
    const next = followedRunAfter(followedRunId.current, run);
    followedRunId.current = next.followedId;
    if (next.hasJustEnded) onEndedRef.current(run);
  }, [run]);

  /** Shows a run the server just answered with, without waiting for the next check. */
  const showRun = useCallback(
    (started: QuestionRunStatus) => queryClient.setQueryData(queryKey, afterStatusAnswer(started)),
    [queryClient, queryKey],
  );

  return { run, statusProblem: statusProblemNote(followed), showRun };
};

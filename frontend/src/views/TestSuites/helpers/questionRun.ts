import type {
  QuestionRunStatus,
  WriteQuestionsEstimate,
} from "@/interfaces/testSuite.interface";

/** How often the run's progress is asked for while it is in progress. */
export const QUESTION_RUN_POLL_MS = 5000;

export const NO_ARTICLES_NOTE = "This knowledge base has no stored articles to read.";

export const IDLE_RUN: QuestionRunStatus = {
  status: "idle",
  articles_total: 0,
  articles_done: 0,
  articles_failed: 0,
  messages_added: 0,
  messages_dropped: 0,
};

/** A line of text about a run, and whether it reports a problem. */
export interface RunNote {
  text: string;
  isProblem: boolean;
}

export const isRunInProgress = (run?: QuestionRunStatus | null): boolean =>
  run?.status === "queued" || run?.status === "running";

/** The name of the knowledge base a run writes from; null when it is not among the listed ones. */
export const knowledgeBaseNameOf = (
  run: QuestionRunStatus,
  knowledgeBases: { id: string; name: string }[],
): string | null =>
  knowledgeBases.find((knowledgeBase) => knowledgeBase.id === run.knowledge_base_id)?.name ?? null;

/** The typed number of articles: null for all of them, undefined when it is not a whole number above zero. */
export const sampleSizeOf = (text: string): number | null | undefined => {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const isWholeNumber = /^\d+$/.test(trimmed);
  const value = Number(trimmed);
  return isWholeNumber && value > 0 ? value : undefined;
};

const counted = (count: number, word: string): string =>
  `${count.toLocaleString("en-US")} ${word}${count === 1 ? "" : "s"}`;

const messageCounts = (run: QuestionRunStatus): string =>
  `${counted(run.messages_added, "question")} added, ${run.messages_dropped.toLocaleString("en-US")} left out.`;

export const describeEstimate = (estimate: WriteQuestionsEstimate): string => {
  if (estimate.articles === 0) return NO_ARTICLES_NOTE;
  const writing = counted(estimate.writing_calls, "writing call");
  const checking = counted(estimate.judging_calls_at_most, "checking call");
  return `${counted(estimate.articles, "article")}. Up to ${writing} and ${checking} to the model.`;
};

/** What to show under the form about the articles of the picked knowledge base; null before one is picked. */
export const estimateNote = (
  knowledgeBaseId: string,
  isCounting: boolean,
  hasFailed: boolean,
  estimate?: WriteQuestionsEstimate | null,
): RunNote | null => {
  if (!knowledgeBaseId) return null;
  if (hasFailed) return { text: "The articles could not be counted.", isProblem: true };
  if (isCounting || !estimate) return { text: "Counting the articles...", isProblem: false };
  return { text: describeEstimate(estimate), isProblem: estimate.articles === 0 };
};

/** A run can start once both picks are made, the number is valid and there are articles to read. */
export const canStartRun = (
  knowledgeBaseId: string,
  providerId: string,
  sampleSize: number | null | undefined,
  estimate?: WriteQuestionsEstimate | null,
): boolean => {
  const hasPicks = Boolean(knowledgeBaseId) && Boolean(providerId);
  const hasArticles = (estimate?.articles ?? 0) > 0;
  return hasPicks && sampleSize !== undefined && hasArticles;
};

/** Share of the run's articles that are finished, 0 to 100. */
export const progressPercent = (run: QuestionRunStatus): number => {
  if (!run.articles_total) return 0;
  const finished = run.articles_done + run.articles_failed;
  return Math.min(100, Math.round((finished / run.articles_total) * 100));
};

export const describeProgress = (run: QuestionRunStatus): string => {
  if (run.status === "queued") return "Waiting for its turn to start.";
  if (!run.articles_total) return "Reading the knowledge base.";
  const finished = (run.articles_done + run.articles_failed).toLocaleString("en-US");
  return `${finished} of ${counted(run.articles_total, "article")} done. ${messageCounts(run)}`;
};

/** How a finished run ended; null while there is no finished run. */
export const describeOutcome = (run: QuestionRunStatus): RunNote | null => {
  if (run.status === "succeeded") {
    const failed = run.articles_failed ? ` ${counted(run.articles_failed, "article")} failed.` : "";
    return { text: `Done. ${messageCounts(run)}${failed}`, isProblem: false };
  }
  const endedEarly = run.status === "stopped" || run.status === "failed";
  if (!endedEarly) return null;
  const reason = run.error ?? "The run did not finish.";
  const kept = run.messages_added > 0 ? ` ${messageCounts(run)}` : "";
  return { text: `${reason}${kept}`, isProblem: true };
};

/** How long to wait before asking again after a status check that failed. */
export const QUESTION_RUN_RETRY_MS = 30000;

export const START_FAILED = "The run could not be started. Try again.";
export const START_REFUSED = "You are not allowed to start a run on this dataset.";
export const LIST_RELOAD_FAILED =
  "The run has ended, but the list could not be reloaded. Reload the page to see the new questions.";
export const STATUS_UNKNOWN_NOTE: RunNote = {
  text: "The run's progress could not be read. Checking again shortly.",
  isProblem: true,
};
export const STATUS_LOST_NOTE: RunNote = {
  text: "The run's progress could not be read. Reload the page to check again.",
  isProblem: true,
};

/** After this many failed status checks in a row the page stops asking. */
export const MAX_FAILED_STATUS_CHECKS = 10;

/** What the page knows about the dataset's run: the last answer, and the checks that failed since. */
export interface FollowedRun {
  run: QuestionRunStatus | null;
  failedChecks: number;
}

export const NOTHING_FOLLOWED: FollowedRun = { run: null, failedChecks: 0 };

export const afterStatusAnswer = (answer: QuestionRunStatus): FollowedRun => ({
  run: answer,
  failedChecks: 0,
});

/** Keeps the last answer and counts the failure. */
export const afterFailedCheck = (previous?: FollowedRun | null): FollowedRun => ({
  run: previous?.run ?? null,
  failedChecks: (previous?.failedChecks ?? 0) + 1,
});

/** A list the form picks from, with how its loading went. */
export interface PickListState {
  isLoading: boolean;
  hasFailed: boolean;
  count: number;
}

/** What a picker shows before a choice is made. */
export const listPlaceholder = (list: PickListState, pickText: string, emptyText: string): string => {
  if (list.isLoading) return "Loading...";
  if (list.count > 0) return pickText;
  return list.hasFailed ? "Could not be loaded" : emptyText;
};

/** The count a run may start on: the answer of the last count only, never an older one. */
export const usableEstimate = (
  isCounting: boolean,
  hasFailed: boolean,
  estimate?: WriteQuestionsEstimate | null,
): WriteQuestionsEstimate | null => (isCounting || hasFailed ? null : estimate ?? null);

/** Whether the dialog shows the run instead of the form. */
export const showsRunView = (run: QuestionRunStatus, followsRun: boolean): boolean =>
  isRunInProgress(run) || (followsRun && describeOutcome(run) !== null);

/** When to ask for the run's status again; false when there is nothing to follow or the page gave up. */
export const nextStatusCheckMs = (followed?: FollowedRun | null): number | false => {
  const run = followed?.run ?? null;
  const failedChecks = followed?.failedChecks ?? 0;
  if (failedChecks === 0) return isRunInProgress(run) ? QUESTION_RUN_POLL_MS : false;
  const hasGivenUp = failedChecks >= MAX_FAILED_STATUS_CHECKS;
  const mayBeRunning = run === null || isRunInProgress(run);
  return !hasGivenUp && mayBeRunning ? QUESTION_RUN_RETRY_MS : false;
};

/** What to say while a followed run's status cannot be read; null when it can. */
export const statusProblemNote = (followed: FollowedRun): RunNote | null => {
  const isFollowedRunUnread = followed.failedChecks > 0 && isRunInProgress(followed.run);
  if (!isFollowedRunUnread) return null;
  return followed.failedChecks >= MAX_FAILED_STATUS_CHECKS ? STATUS_LOST_NOTE : STATUS_UNKNOWN_NOTE;
};

/** The run to keep following after seeing `run`, and whether the followed run has just ended. */
export const followedRunAfter = (
  followedId: string | null,
  run: QuestionRunStatus,
): { followedId: string | null; hasJustEnded: boolean } => {
  if (isRunInProgress(run)) return { followedId: run.run_id ?? null, hasJustEnded: false };
  const hasJustEnded = followedId !== null && run.run_id === followedId;
  return { followedId: hasJustEnded ? null : followedId, hasJustEnded };
};

/** What to say about a failed start when the server gave no reason of its own. */
export const startFallbackText = (error: unknown): string => {
  const status = (error as { response?: { status?: number } })?.response?.status;
  return status === 403 ? START_REFUSED : START_FAILED;
};

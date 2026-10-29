/** Where a reader is in a run's results: the run, one of its conversations, or a comparison. */
export interface ResultsLocation {
  runId: string;
  conversation?: string;
  /** The run compared with, "" while the comparison waits for one to be picked. */
  compareWith?: string;
}

export interface ResultsMove {
  /** Replace the current history entry instead of adding one, for moves within a view. */
  replace?: boolean;
  /** Back to the view this one was opened from, so the browser's history steps back too. */
  back?: boolean;
}

/** The location a page's URL points at, or null on the evaluation itself. */
export const locationFromParams = (params: URLSearchParams): ResultsLocation | null => {
  const runId = params.get("run");
  if (!runId) return null;
  return {
    runId,
    conversation: params.get("conversation") ?? undefined,
    compareWith: params.has("compare") ? params.get("compare") ?? "" : undefined,
  };
};

export const paramsFromLocation = (view: ResultsLocation | null): URLSearchParams => {
  const params = new URLSearchParams();
  if (!view) return params;
  params.set("run", view.runId);
  if (view.conversation) params.set("conversation", view.conversation);
  if (view.compareWith !== undefined) params.set("compare", view.compareWith);
  return params;
};

/** Whether the location is a comparison, with or without its second run picked. */
export const isComparing = (view: ResultsLocation): boolean => view.compareWith !== undefined;

/** Back from a conversation: to the comparison it was opened from, else to its run. */
export const backFromConversation = (view: ResultsLocation): ResultsLocation =>
  isComparing(view) ? { runId: view.runId, compareWith: view.compareWith } : { runId: view.runId };

import { getKnowledgeBaseSyncStatus } from '@/services/api';

export type ProviderSyncResult = {
  status?: string;
  error?: string;
  message?: string;
  articles_added?: number;
  articles_updated?: number;
  articles_deleted?: number;
  per_kb?: Array<{ status?: string; reason?: string; error?: string; note?: string }>;
};

export type ManualSyncResult = {
  status?: string;
  message?: string;
  zendesk_sync_results?: Array<{ result?: ProviderSyncResult }>;
  salesforce_sync_results?: Array<{ result?: ProviderSyncResult }>;
};

/** Answer of the endpoint that starts a manual sync: a queued run, or the result of a sync it ran itself. */
export type ManualSyncStart = ManualSyncResult & {
  run_id?: string;
};

/** The run in progress with the last outcome as previous, the last run's outcome (succeeded, failed), or idle. */
export type ManualSyncStatus = {
  status?: string;
  run_id?: string;
  result?: ManualSyncResult | null;
  error?: string | null;
  previous?: ManualSyncStatus | null;
};

export type ManualSyncOutcome =
  | { kind: 'finished'; result: ManualSyncResult }
  | { kind: 'failed'; error?: string | null }
  | { kind: 'stopped' }
  | { kind: 'unknown' }
  | { kind: 'aborted' };

export type SyncMessage = { kind: 'success' | 'error'; text: string };

export type PollStage = { untilMs: number; intervalMs: number };

export type ManualSyncTiming = {
  pollStages: PollStage[];
  finalPollIntervalMs: number;
  retryAfterFailureMs: number;
  giveUpAfterFailedMs: number;
  giveUpAfterFailedChecks: number;
};

// The longer a sync runs, the less often it is checked, to keep within the API rate limits.
export const MANUAL_SYNC_TIMING: ManualSyncTiming = {
  pollStages: [
    { untilMs: 30 * 1000, intervalMs: 2 * 1000 },
    { untilMs: 5 * 60 * 1000, intervalMs: 10 * 1000 },
  ],
  finalPollIntervalMs: 30 * 1000,
  retryAfterFailureMs: 10 * 1000,
  // The page gives up only after this long without a good check and this many failed checks in a row.
  giveUpAfterFailedMs: 60 * 1000,
  giveUpAfterFailedChecks: 3,
};

const SYNC_STOPPED_MESSAGE = 'The sync stopped before it finished. Run it again.';
const SYNC_UNKNOWN_MESSAGE = 'Could not check the sync status. Refresh the page to see if it is still running.';

const successMessage = (text: string): SyncMessage => ({ kind: 'success', text });
const errorMessage = (text: string): SyncMessage => ({ kind: 'error', text });

export const isSyncInProgress = (status?: ManualSyncStatus | null): boolean => status?.status === 'running';

const delay = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const finish = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', finish);
      resolve();
    };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener('abort', finish, { once: true });
  });

const pollIntervalAfter = (elapsedMs: number, timing: ManualSyncTiming): number => {
  const currentStage = timing.pollStages.find((stage) => elapsedMs < stage.untilMs);
  return currentStage?.intervalMs ?? timing.finalPollIntervalMs;
};

const nextCheckDelay = (elapsedMs: number, lastCheckFailed: boolean, timing: ManualSyncTiming): number => {
  const regularDelay = pollIntervalAfter(elapsedMs, timing);
  return lastCheckFailed ? Math.min(regularDelay, timing.retryAfterFailureMs) : regularDelay;
};

const readSyncStatus = async (kbId: string): Promise<ManualSyncStatus> => {
  const status = (await getKnowledgeBaseSyncStatus(kbId)) as ManualSyncStatus | null;
  if (!status) throw new Error('The sync status could not be read');
  return status;
};

// While a newer run is in progress, the followed run's outcome is the previous one.
const outcomeOfEndedRun = (status: ManualSyncStatus, trackedRunId?: string): ManualSyncOutcome => {
  const endedRun = isSyncInProgress(status) ? status.previous : status;
  const isTrackedRun = !!trackedRunId && endedRun?.run_id === trackedRunId;
  if (!endedRun || !isTrackedRun) return { kind: 'stopped' };
  if (endedRun.status === 'succeeded') return { kind: 'finished', result: endedRun.result ?? {} };
  return { kind: 'failed', error: endedRun.error };
};

/** Poll a knowledge base's manual sync until the followed run ends; the server's running mark bounds the wait. */
export const waitForManualSync = async (
  kbId: string,
  runId?: string,
  signal?: AbortSignal,
  timing: ManualSyncTiming = MANUAL_SYNC_TIMING
): Promise<ManualSyncOutcome> => {
  const startedAt = Date.now();
  let trackedRunId = runId;
  let lastGoodCheckAt = startedAt;
  let failedChecks = 0;
  for (;;) {
    if (signal?.aborted) return { kind: 'aborted' };
    try {
      const status = await readSyncStatus(kbId);
      if (signal?.aborted) return { kind: 'aborted' };
      lastGoodCheckAt = Date.now();
      failedChecks = 0;
      // Without a run id from the start, the page follows the run it finds first.
      trackedRunId = trackedRunId ?? status.run_id;
      const trackedRunEnded = !isSyncInProgress(status) || status.run_id !== trackedRunId;
      if (trackedRunEnded) return outcomeOfEndedRun(status, trackedRunId);
    } catch {
      if (signal?.aborted) return { kind: 'aborted' };
      failedChecks += 1;
      const failedLongEnough = Date.now() - lastGoodCheckAt >= timing.giveUpAfterFailedMs;
      const failedOftenEnough = failedChecks >= timing.giveUpAfterFailedChecks;
      if (failedLongEnough && failedOftenEnough) return { kind: 'unknown' };
    }
    const lastCheckFailed = failedChecks > 0;
    await delay(nextCheckDelay(Date.now() - startedAt, lastCheckFailed, timing), signal);
  }
};

/** The message for a sync that ran to its end, from the result the sync returned. */
export const describeSyncResult = (result: ManualSyncResult, kbType: string): SyncMessage => {
  if (result.status === 'error') return errorMessage(result.message ?? 'Synchronization failed.');

  const isSalesforce = kbType === 'salesforce';
  const providerLabel = isSalesforce ? 'SalesForce' : 'Zendesk';
  const providerResult = isSalesforce
    ? result.salesforce_sync_results?.[0]?.result
    : result.zendesk_sync_results?.[0]?.result;
  if (providerResult?.status === 'failed') {
    return errorMessage(providerResult.error ?? providerResult.message ?? `${providerLabel} sync failed.`);
  }

  const firstKb = providerResult?.per_kb?.[0];
  if (firstKb?.status === 'skipped') {
    return errorMessage(
      `Sync skipped: ${firstKb.reason ?? 'unknown'}. Check schedule, datasource, or ${providerLabel} connection.`
    );
  }
  if (firstKb?.status === 'error') {
    console.error(firstKb?.error ?? 'Unknown error');
    return errorMessage(`${providerLabel} sync error. See knowledge base sync status.`);
  }

  const hasArticleCounts =
    providerResult != null &&
    (providerResult.articles_added != null ||
      providerResult.articles_updated != null ||
      providerResult.articles_deleted != null);
  if (hasArticleCounts) {
    return successMessage(
      `Sync completed: ${providerResult.articles_added ?? 0} added, ${providerResult.articles_updated ?? 0} updated, ${providerResult.articles_deleted ?? 0} removed.`
    );
  }
  return successMessage('Synchronization completed successfully.');
};

/** The message for however the followed run ended; none when the page stopped following it. */
export const describeSyncOutcome = (outcome: ManualSyncOutcome, kbType: string): SyncMessage | null => {
  if (outcome.kind === 'finished') return describeSyncResult(outcome.result, kbType);
  if (outcome.kind === 'failed') return errorMessage(outcome.error || 'Synchronization failed.');
  if (outcome.kind === 'stopped') return errorMessage(SYNC_STOPPED_MESSAGE);
  if (outcome.kind === 'unknown') return errorMessage(SYNC_UNKNOWN_MESSAGE);
  return null;
};

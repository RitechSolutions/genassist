import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-hot-toast';
import { executeKnowledgeBaseSyncronizationManually, getKnowledgeBaseSyncStatus } from '@/services/api';
import {
  describeSyncOutcome,
  describeSyncResult,
  isSyncInProgress,
  waitForManualSync,
  ManualSyncStart,
  ManualSyncStatus,
  SyncMessage,
} from '../utils/manualSync';

type SyncedItem = { id?: string; type?: string } | null;

const showSyncMessage = (message: SyncMessage | null) => {
  if (message?.kind === 'success') toast.success(message.text);
  if (message?.kind === 'error') toast.error(message.text);
};

/** Starts a knowledge base's manual sync and follows it until it ends; closing the page stops following. */
export const useManualSync = (pageKbId: string | undefined, item: SyncedItem, onSyncEnded: () => Promise<void>) => {
  const [isSyncing, setIsSyncing] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const isFollowingRef = useRef(false);
  const onSyncEndedRef = useRef(onSyncEnded);
  onSyncEndedRef.current = onSyncEnded;

  const endSync = useCallback(async (message: SyncMessage | null) => {
    showSyncMessage(message);
    setIsSyncing(false);
    await onSyncEndedRef.current();
  }, []);

  const followSync = useCallback(
    async (kbId: string, kbType: string, signal?: AbortSignal, runId?: string) => {
      const pageIsClosed = !signal || signal.aborted;
      if (pageIsClosed || isFollowingRef.current) return;
      isFollowingRef.current = true;
      setIsSyncing(true);
      const outcome = await waitForManualSync(kbId, runId, signal);
      const stoppedFollowing = outcome.kind === 'aborted';
      if (stoppedFollowing) return;
      isFollowingRef.current = false;
      await endSync(describeSyncOutcome(outcome, kbType));
    },
    [endSync]
  );

  const startSync = useCallback(
    async (kbId: string, kbType: string) => {
      const signal = abortRef.current?.signal;
      setIsSyncing(true);
      try {
        const started = (await executeKnowledgeBaseSyncronizationManually(kbId)) as ManualSyncStart;
        if (signal?.aborted) return;
        const syncEndedInRequest = started.status === 'error' || started.status === 'completed';
        if (syncEndedInRequest) {
          await endSync(describeSyncResult(started, kbType));
          return;
        }
        if (started.status === 'already_running') {
          toast('A sync is already running for this knowledge base.');
        }
        await followSync(kbId, kbType, signal, started.run_id);
      } catch {
        if (signal?.aborted) return;
        toast.error('Failed to trigger synchronization.');
        setIsSyncing(false);
      }
    },
    [endSync, followSync]
  );

  // One stop switch per knowledge base page.
  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    return () => {
      controller.abort();
      isFollowingRef.current = false;
      setIsSyncing(false);
    };
  }, [pageKbId]);

  // Pick up a sync that is already in progress when the page opens.
  const itemId = item?.id;
  const itemType = item?.type;
  useEffect(() => {
    const isItemOnScreen = !!pageKbId && itemId === pageKbId;
    const canResumeOnScreenItem = isItemOnScreen && !!itemId && !!itemType;
    if (!canResumeOnScreenItem) return;
    const signal = abortRef.current?.signal;
    const resumeSyncInProgress = async () => {
      try {
        const current = (await getKnowledgeBaseSyncStatus(itemId)) as ManualSyncStatus | null;
        if (isSyncInProgress(current)) await followSync(itemId, itemType, signal, current?.run_id);
      } catch {
        /* the status is optional when the page opens */
      }
    };
    void resumeSyncInProgress();
  }, [pageKbId, itemId, itemType, followSync]);

  return { isSyncing, startSync };
};

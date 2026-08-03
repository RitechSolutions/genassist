import { useCallback, useState } from "react";

import { getCurrentUserId, getTenantId } from "@/services/auth";

/**
 * Manages dismissal for a recurring notice and persists it across renders and reloads.
 *
 * `latestAt` identifies the newest event behind the notice. After dismissal, the
 * notice stays hidden until a newer event arrives:
 *
 * const notice = useDismissibleNotice("llm-unpriced-coverage", summary?.last_unpriced_at);
 * {notice.visible && <Banner onDismiss={notice.dismiss} />}
 *
 * Only a later timestamp shows the notice again. Repricing calls can move the
 * newest-unpriced timestamp backward, but that does not represent a new event.
 *
 * Dismissals are scoped by tenant and user because logout preserves non-auth
 * localStorage keys. This prevents dismissals from carrying between users on a
 * shared browser.
 */
const STORAGE_PREFIX = "genassist_dismissed_notice";

function storageKey(notice: string): string {
  return `${STORAGE_PREFIX}:${getTenantId() || "default"}:${getCurrentUserId() ?? "anon"}:${notice}`;
}

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function isNewerThanDismissed(latestAt: string, dismissedAt: string | null): boolean {
  if (dismissedAt === null) return true;
  const latest = Date.parse(latestAt);
  const dismissed = Date.parse(dismissedAt);
  if (Number.isNaN(latest) || Number.isNaN(dismissed)) return latestAt !== dismissedAt;
  return latest > dismissed;
}

export interface DismissibleNotice {
  visible: boolean;
  dismiss: () => void;
}

export function useDismissibleNotice(notice: string, latestAt: string | null | undefined): DismissibleNotice {
  const key = storageKey(notice);
  const [dismissedAt, setDismissedAt] = useState<string | null>(() => readStored(key));

  // A signed-out-and-back-in user reads a different key. Re-read while rendering rather
  // than in an effect, so no frame shows the previous user's dismissal.
  const [renderedKey, setRenderedKey] = useState(key);
  if (renderedKey !== key) {
    setRenderedKey(key);
    setDismissedAt(readStored(key));
  }

  const dismiss = useCallback(() => {
    if (!latestAt) return;
    setDismissedAt(latestAt);
    try {
      localStorage.setItem(key, latestAt);
    } catch {
      // Storage unavailable: the notice stays dismissed for this session only
    }
  }, [key, latestAt]);

  return { visible: Boolean(latestAt) && isNewerThanDismissed(latestAt as string, dismissedAt), dismiss };
}

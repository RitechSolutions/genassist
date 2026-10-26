import { describe, expect, it } from "vitest";

import {
  QUIET_CONVERSATION_RECHECK_MS,
  RETURN_CHECK_MIN_INTERVAL_MS,
  hasBeenQuietFor,
  isConversationGone,
} from "./useChat";

const NOW_MS = 10_000_000;

describe("hasBeenQuietFor", () => {
  it("asks for a re-check once the threshold has passed since the last confirmation", () => {
    const lastConfirmedOpenAt = NOW_MS - QUIET_CONVERSATION_RECHECK_MS;
    expect(hasBeenQuietFor(lastConfirmedOpenAt, QUIET_CONVERSATION_RECHECK_MS, NOW_MS)).toBe(true);
  });

  it("skips the re-check while the conversation was confirmed open recently", () => {
    const lastConfirmedOpenAt = NOW_MS - QUIET_CONVERSATION_RECHECK_MS + 1;
    expect(hasBeenQuietFor(lastConfirmedOpenAt, QUIET_CONVERSATION_RECHECK_MS, NOW_MS)).toBe(false);
  });

  it("always asks for a check when the conversation was never confirmed open", () => {
    expect(hasBeenQuietFor(0, RETURN_CHECK_MIN_INTERVAL_MS, NOW_MS)).toBe(true);
  });

  it("re-checks a quiet conversation before the server's idle cleanup would close it", () => {
    const defaultServerIdleCleanupMs = 30 * 60 * 1000;
    expect(QUIET_CONVERSATION_RECHECK_MS).toBeLessThan(defaultServerIdleCleanupMs);
    expect(RETURN_CHECK_MIN_INTERVAL_MS).toBeLessThan(QUIET_CONVERSATION_RECHECK_MS);
  });
});

describe("isConversationGone", () => {
  it("treats finalized and unavailable conversations as gone", () => {
    expect(isConversationGone("finalized")).toBe(true);
    expect(isConversationGone("unavailable")).toBe(true);
  });

  it("keeps a conversation that is open or could not be checked", () => {
    expect(isConversationGone("available")).toBe(false);
    expect(isConversationGone("unknown")).toBe(false);
  });
});

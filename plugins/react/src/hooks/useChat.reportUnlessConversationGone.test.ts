import { describe, expect, it, vi } from "vitest";

import { ConversationGoneError } from "../utils/conversationErrors";
import { reportUnlessConversationGone } from "./useChat";

const httpError = (status: number, errorKey?: string) => ({
  response: { status, data: errorKey ? { error_key: errorKey } : {} },
});

describe("reportUnlessConversationGone", () => {
  it("stays quiet when the chat had already ended and the widget has recovered", () => {
    const onError = vi.fn();

    reportUnlessConversationGone(new ConversationGoneError(), onError);
    reportUnlessConversationGone(httpError(400, "CONVERSATION_FINALIZED"), onError);
    reportUnlessConversationGone(httpError(404, "CONVERSATION_NOT_FOUND"), onError);

    expect(onError).not.toHaveBeenCalled();
  });

  it("reports a refusal the widget did not recover from", () => {
    const onError = vi.fn();
    const missingPermission = httpError(403, "NOT_AUTHORIZED_ACCESS_RESOURCE");

    reportUnlessConversationGone(missingPermission, onError);

    expect(onError).toHaveBeenCalledWith(missingPermission);
  });

  it("does nothing when the host has no error handler", () => {
    expect(() => reportUnlessConversationGone(new Error("boom"), undefined)).not.toThrow();
  });
});

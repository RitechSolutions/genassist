import { describe, expect, it } from "vitest";

import {
  ConversationGoneError,
  isConversationFinalizedError,
  isConversationUnavailableError,
  isExpiredPassError,
} from "./conversationErrors";

const httpError = (status: number, data?: unknown) => ({ response: { status, data } });

describe("isExpiredPassError", () => {
  it("recognises the expired-token error key", () => {
    expect(isExpiredPassError(httpError(401, { error_key: "EXPIRED_TOKEN" }))).toBe(true);
  });

  it("does not depend on the localised error message", () => {
    const localised = httpError(401, { error_key: "EXPIRED_TOKEN", error: "Le jeton a expiré." });
    expect(isExpiredPassError(localised)).toBe(true);
  });

  it("still recognises the plain English message from older servers", () => {
    expect(isExpiredPassError(httpError(401, { error: "Token has expired." }))).toBe(true);
    expect(isExpiredPassError(httpError(401, "Token has expired."))).toBe(true);
  });

  it("ignores other authentication failures and other statuses", () => {
    expect(isExpiredPassError(httpError(401, { error_key: "INVALID_API_KEY" }))).toBe(false);
    expect(isExpiredPassError(httpError(403, { error_key: "EXPIRED_TOKEN" }))).toBe(false);
    expect(isExpiredPassError({ code: "ERR_NETWORK" })).toBe(false);
  });
});

describe("isConversationUnavailableError", () => {
  it.each([
    ["an expired guest token", httpError(401, { error_key: "EXPIRED_TOKEN" })],
    ["any rejected credential", httpError(401, { error_key: "COULD_NOT_VALIDATE_CREDENTIALS" })],
    ["a guest token for another conversation", httpError(403, { error_key: "NOT_AUTHORIZED" })],
    ["a deleted conversation", httpError(404, { error_key: "AGENT_NOT_FOUND" })],
    ["a missing conversation", httpError(404, { error_key: "CONVERSATION_NOT_FOUND" })],
    ["a finalized conversation", httpError(400, { error_key: "CONVERSATION_FINALIZED" })],
  ])("is true for %s", (_label, error) => {
    expect(isConversationUnavailableError(error)).toBe(true);
  });

  it.each([
    ["a reCAPTCHA refusal", httpError(403, { error_key: "RECAPTCHA_VERIFICATION_FAILED" })],
    ["a 403 without an error key", httpError(403)],
    ["an unrelated bad request", httpError(400, { error_key: "CONVERSATION_MUST_START_EMPTY" })],
    ["rate limiting", httpError(429)],
    ["a server error", httpError(500)],
    ["a network failure", { code: "ERR_NETWORK" }],
    ["a non-HTTP error", new Error("Conversation not started")],
    ["a 401 from a proxy without an error key", httpError(401, {})],
    ["a 404 page from a load balancer", httpError(404, "<html>Not Found</html>")],
    ["a 404 without an error key", httpError(404, {})],
    ["an unrelated 404 such as a missing file", httpError(404, { error_key: "FILE_NOT_FOUND" })],
    ["a missing permission on one endpoint", httpError(403, { error_key: "NOT_AUTHORIZED_ACCESS_RESOURCE" })],
  ])("is false for %s", (_label, error) => {
    expect(isConversationUnavailableError(error)).toBe(false);
  });
});

describe("isConversationFinalizedError", () => {
  it("recognises a conversation the server has finalized", () => {
    expect(isConversationFinalizedError(httpError(400, { error_key: "CONVERSATION_FINALIZED" }))).toBe(true);
  });

  it("ignores other refusals", () => {
    expect(isConversationFinalizedError(httpError(404, { error_key: "AGENT_NOT_FOUND" }))).toBe(false);
    expect(isConversationFinalizedError(httpError(401, { error_key: "EXPIRED_TOKEN" }))).toBe(false);
  });
});

describe("a request stopped locally because the chat pass expired", () => {
  it("counts as a conversation that can no longer be continued", () => {
    expect(isConversationUnavailableError(new ConversationGoneError())).toBe(true);
  });
});

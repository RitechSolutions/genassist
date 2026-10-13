/** Classifies conversation request errors by HTTP status and `error_key`, never by the localised message. */

const EXPIRED_TOKEN_KEY = "EXPIRED_TOKEN";
const CONVERSATION_FINALIZED_KEY = "CONVERSATION_FINALIZED";
const ACCESS_REFUSED_KEYS = new Set(["NOT_AUTHORIZED"]);
const LEGACY_EXPIRED_TOKEN_MESSAGE = "Token has expired";
const CONVERSATION_GONE_KEYS = new Set(["CONVERSATION_NOT_FOUND", "AGENT_NOT_FOUND"]);

/** Raised when a conversation request is stopped before sending because its guest token has expired. */
export class ConversationGoneError extends Error {
  constructor() {
    super("The conversation can no longer be continued");
    this.name = "ConversationGoneError";
  }
}

function readStatus(error: any): number | undefined {
  const status = error?.response?.status;
  return typeof status === "number" ? status : undefined;
}

function readErrorKey(error: any): string | undefined {
  const errorKey = error?.response?.data?.error_key;
  return typeof errorKey === "string" ? errorKey : undefined;
}

function hasLegacyExpiredTokenMessage(error: any): boolean {
  const data = error?.response?.data;
  if (typeof data === "string") return data.includes(LEGACY_EXPIRED_TOKEN_MESSAGE);
  const message = data?.error ?? data?.message;
  return typeof message === "string" && message.includes(LEGACY_EXPIRED_TOKEN_MESSAGE);
}

/** The request was refused because the conversation's guest token has expired. */
export function isExpiredPassError(error: unknown): boolean {
  if (readStatus(error) !== 401) return false;
  return readErrorKey(error) === EXPIRED_TOKEN_KEY || hasLegacyExpiredTokenMessage(error);
}

/** The server refused the request because the conversation has already been finalized. */
export function isConversationFinalizedError(error: unknown): boolean {
  return readStatus(error) === 400 && readErrorKey(error) === CONVERSATION_FINALIZED_KEY;
}

/** The GenAssist API says the conversation cannot be continued; bare proxy 401/404 answers do not count. */
export function isConversationUnavailableError(error: unknown): boolean {
  if (error instanceof ConversationGoneError) return true;
  const status = readStatus(error);
  const errorKey = readErrorKey(error);
  const isApiAnswer = errorKey !== undefined;

  const isCredentialRejected = status === 401 && (isApiAnswer || hasLegacyExpiredTokenMessage(error));
  const isAccessRefused = status === 403 && isApiAnswer && ACCESS_REFUSED_KEYS.has(errorKey);
  const isConversationGone = status === 404 && isApiAnswer && CONVERSATION_GONE_KEYS.has(errorKey);

  return isCredentialRejected || isAccessRefused || isConversationGone || isConversationFinalizedError(error);
}

import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import axios from "axios";

import { ChatService } from "./chatService";
import { ConversationGoneError } from "../utils/conversationErrors";
import type { ChatMessage } from "../types";

vi.mock("axios", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));

const mockedAxios = axios as unknown as { get: Mock; post: Mock; patch: Mock };

class MemoryStorage {
  private items = new Map<string, string>();
  getItem(key: string): string | null {
    return this.items.has(key) ? (this.items.get(key) as string) : null;
  }
  setItem(key: string, value: string): void {
    this.items.set(key, String(value));
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
}

const BASE_URL = "https://api.example.test";
const API_KEY = "widget-key";
const CONVERSATION_ID = "conversation-1";
const POINTER_KEY = `genassist_conversation:${API_KEY}`;
const MESSAGES_KEY = `genassist_conversation_messages:${API_KEY}:${CONVERSATION_ID}`;
const READ_STATE_KEY = `genassist_conversation_read_state:${API_KEY}:${CONVERSATION_ID}`;
const NOW_MS = Date.UTC(2026, 0, 15, 12, 0, 0);
const ONE_HOUR_SECONDS = 3600;

const encodeSegment = (value: object): string =>
  Buffer.from(JSON.stringify(value)).toString("base64url");

const buildGuestToken = (expiresAtSeconds: number): string =>
  `${encodeSegment({ alg: "HS256", typ: "JWT" })}.${encodeSegment({ exp: expiresAtSeconds })}.signature`;

const validGuestToken = () => buildGuestToken(NOW_MS / 1000 + ONE_HOUR_SECONDS);
const expiredGuestToken = () => buildGuestToken(NOW_MS / 1000 - ONE_HOUR_SECONDS);

let storage: MemoryStorage;

function saveConversation(overrides: Record<string, unknown> = {}): void {
  storage.setItem(
    POINTER_KEY,
    JSON.stringify({
      conversationId: CONVERSATION_ID,
      createTime: NOW_MS / 1000 - 600,
      isFinalized: false,
      guestToken: validGuestToken(),
      agentId: "agent-1",
      welcomeData: { imageUrl: null },
      ...overrides,
    }),
  );
  storage.setItem(MESSAGES_KEY, "[]");
  storage.setItem(READ_STATE_KEY, "{}");
}

const createService = () =>
  new ChatService(BASE_URL, undefined, API_KEY, undefined, undefined, undefined, false, false);

const httpError = (status: number, errorKey?: string) => ({
  response: { status, data: errorKey ? { error_key: errorKey } : {} },
});

beforeEach(() => {
  storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  vi.useFakeTimers();
  vi.setSystemTime(NOW_MS);
  mockedAxios.get.mockReset();
  mockedAxios.post.mockReset();
  mockedAxios.patch.mockReset();
  mockedAxios.get.mockRejectedValue(new Error("unexpected request"));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("restoring a saved conversation", () => {
  it("drops a conversation whose guest token has expired without contacting the server", () => {
    saveConversation({ guestToken: expiredGuestToken() });

    const service = createService();

    expect(service.getConversationId()).toBeNull();
    expect(service.getGuestToken()).toBeNull();
    expect(storage.getItem(POINTER_KEY)).toBeNull();
    expect(storage.getItem(MESSAGES_KEY)).toBeNull();
    expect(storage.getItem(READ_STATE_KEY)).toBeNull();
    expect(mockedAxios.get).not.toHaveBeenCalled();
  });

  it("drops a conversation that was already finalized", () => {
    saveConversation({ isFinalized: true });

    const service = createService();

    expect(service.getConversationId()).toBeNull();
    expect(storage.getItem(MESSAGES_KEY)).toBeNull();
  });

  it("keeps a conversation whose guest token is still valid", () => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });

    const service = createService();

    expect(service.getConversationId()).toBe(CONVERSATION_ID);
    expect(storage.getItem(MESSAGES_KEY)).toBe("[]");
  });
});

describe("checkConversationAvailability", () => {
  beforeEach(() => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });
  });

  it("reports available while the server has the conversation in progress", async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: { status: "in_progress", messages: [] } });

    await expect(createService().checkConversationAvailability()).resolves.toBe("available");
    expect(mockedAxios.get).toHaveBeenCalledWith(
      `${BASE_URL}/api/conversations/in-progress/poll/${CONVERSATION_ID}`,
      expect.objectContaining({ timeout: expect.any(Number) }),
    );
  });

  it("reports finalized once the server has finalized the conversation", async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: { status: "finalized", messages: [] } });

    await expect(createService().checkConversationAvailability()).resolves.toBe("finalized");
  });

  it("reports finalized when the server refuses the check because the conversation ended", async () => {
    mockedAxios.get.mockRejectedValueOnce(httpError(400, "CONVERSATION_FINALIZED"));

    await expect(createService().checkConversationAvailability()).resolves.toBe("finalized");
  });

  it("reports unknown for a bare 404 that did not come from the GenAssist API", async () => {
    mockedAxios.get.mockRejectedValueOnce(httpError(404));

    await expect(createService().checkConversationAvailability()).resolves.toBe("unknown");
  });

  it("reports unavailable when the conversation no longer exists", async () => {
    mockedAxios.get.mockRejectedValueOnce(httpError(404, "AGENT_NOT_FOUND"));

    await expect(createService().checkConversationAvailability()).resolves.toBe("unavailable");
  });

  it("reports unknown when the server cannot be reached", async () => {
    mockedAxios.get.mockRejectedValueOnce({ code: "ERR_NETWORK" });

    await expect(createService().checkConversationAvailability()).resolves.toBe("unknown");
  });

  it("answers locally once the guest token has expired during the visit", async () => {
    const service = createService();
    vi.setSystemTime(NOW_MS + 2 * ONE_HOUR_SECONDS * 1000);

    await expect(service.checkConversationAvailability()).resolves.toBe("unavailable");
    expect(mockedAxios.get).not.toHaveBeenCalled();
  });
});

describe("sendMessage into a conversation that can no longer be continued", () => {
  beforeEach(() => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });
  });

  it("clears the conversation and reports the refusal instead of showing it as finalized", async () => {
    const service = createService();
    const emitted: ChatMessage[] = [];
    service.setMessageHandler((message) => emitted.push(message));
    mockedAxios.patch.mockRejectedValueOnce(httpError(400, "CONVERSATION_FINALIZED"));

    await expect(service.sendMessage("Hello again")).rejects.toMatchObject({
      response: { status: 400 },
    });

    expect(service.getConversationId()).toBeNull();
    expect(emitted.some((message) => message.type === "finalized")).toBe(false);
  });

  it("clears the conversation when the guest token is rejected", async () => {
    const service = createService();
    mockedAxios.patch.mockRejectedValueOnce(httpError(401, "EXPIRED_TOKEN"));

    await expect(service.sendMessage("Hello again")).rejects.toBeTruthy();

    expect(service.getConversationId()).toBeNull();
  });

  it("keeps the conversation for refusals that do not end it", async () => {
    const service = createService();
    mockedAxios.patch.mockRejectedValueOnce(httpError(403, "RECAPTCHA_VERIFICATION_FAILED"));

    await expect(service.sendMessage("Hello again")).rejects.toBeTruthy();

    expect(service.getConversationId()).toBe(CONVERSATION_ID);
  });
});

describe("agent-level lookups", () => {
  it("use the widget key even while a conversation guest token is held", async () => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });
    const service = createService();
    mockedAxios.get.mockResolvedValue({ data: {} });

    await service.fetchAgentInfo();
    await service.fetchAgentChatLocales();

    for (const [, config] of mockedAxios.get.mock.calls) {
      expect(config.headers["x-api-key"]).toBe(API_KEY);
      expect(config.headers.Authorization).toBeUndefined();
    }
    expect(mockedAxios.get).toHaveBeenCalledTimes(2);
  });
});

describe("a visitor whose device clock runs two days fast", () => {
  const TWO_DAYS_MS = 2 * 24 * 60 * 60 * 1000;
  const uuidV7At = (ms: number): string => {
    const hex = ms.toString(16).padStart(12, "0") + "7abc8def0123456789ab";
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  };

  it("judges the chat pass by the server's clock, before and after a reload", async () => {
    const serverNowMs = NOW_MS - TWO_DAYS_MS;
    mockedAxios.post.mockResolvedValueOnce({
      data: {
        conversation_id: uuidV7At(serverNowMs),
        guest_token: buildGuestToken(serverNowMs / 1000 + 24 * ONE_HOUR_SECONDS),
        agent_welcome_image_url: "https://cdn.example.test/welcome.png",
      },
    });
    const service = createService();

    await service.startConversation();

    expect(service.hasExpiredGuestToken()).toBe(false);
    expect(createService().getConversationId()).toBe(uuidV7At(serverNowMs));
  });
});

describe("requests made with a chat pass that has expired", () => {
  const expire = () => vi.setSystemTime(NOW_MS + 2 * ONE_HOUR_SECONDS * 1000);
  const withGoneHandler = () => {
    const service = createService();
    const onGone = vi.fn();
    service.setConversationGoneHandler(onGone);
    return { service, onGone };
  };

  beforeEach(() => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });
  });

  it("does not send a read receipt and tells the widget the chat is gone", async () => {
    const { service, onGone } = withGoneHandler();
    expire();

    await service.markRead(5);

    expect(mockedAxios.patch).not.toHaveBeenCalled();
    expect(onGone).toHaveBeenCalledWith(CONVERSATION_ID, "unavailable");
    expect(service.getConversationId()).toBeNull();
  });

  it("stops a message before sending it", async () => {
    const { service, onGone } = withGoneHandler();
    const shown: ChatMessage[] = [];
    service.setMessageHandler((message) => shown.push(message));
    expire();

    await expect(service.sendMessage("Hello again")).rejects.toBeInstanceOf(ConversationGoneError);

    expect(mockedAxios.patch).not.toHaveBeenCalled();
    expect(shown).toHaveLength(0);
    expect(onGone).toHaveBeenCalledTimes(1);
  });

  it("stops an upload before sending it", async () => {
    const { service, onGone } = withGoneHandler();
    expire();

    await expect(service.uploadFile(CONVERSATION_ID, {} as File)).rejects.toBeInstanceOf(ConversationGoneError);

    expect(mockedAxios.post).not.toHaveBeenCalled();
    expect(onGone).toHaveBeenCalledTimes(1);
  });

  it("tells the widget when the server says the chat no longer exists", async () => {
    const { service, onGone } = withGoneHandler();
    mockedAxios.patch.mockRejectedValueOnce(httpError(404, "CONVERSATION_NOT_FOUND"));

    await service.markRead(5);

    expect(onGone).toHaveBeenCalledWith(CONVERSATION_ID, "unavailable");
  });
});

describe("loading the agent's welcome image", () => {
  it("uses the widget key, not the chat pass", async () => {
    saveConversation();
    mockedAxios.get.mockRejectedValue(httpError(404, "FILE_NOT_FOUND"));

    createService();
    await Promise.resolve();

    const [url, config] = mockedAxios.get.mock.calls[0];
    expect(url).toContain("/welcome-image");
    expect(config.headers["x-api-key"]).toBe(API_KEY);
    expect(config.headers.Authorization).toBeUndefined();
  });
});

describe("dropping a saved chat", () => {
  it("also removes the older unscoped storage record", () => {
    storage.setItem(
      "genassist_conversation",
      JSON.stringify({ conversationId: CONVERSATION_ID, guestToken: expiredGuestToken() }),
    );

    createService();

    expect(storage.getItem("genassist_conversation")).toBeNull();
  });
});

describe("refusals that must not end a live chat", () => {
  beforeEach(() => {
    saveConversation({ welcomeData: { imageUrl: "https://cdn.example.test/welcome.png" } });
  });

  it("keeps the chat when feedback is refused for a missing permission", async () => {
    const service = createService();
    const onGone = vi.fn();
    service.setConversationGoneHandler(onGone);
    mockedAxios.patch.mockRejectedValueOnce(httpError(403, "NOT_AUTHORIZED_ACCESS_RESOURCE"));

    await expect(service.addFeedback("message-1", "good")).rejects.toBeTruthy();

    expect(onGone).not.toHaveBeenCalled();
    expect(service.getConversationId()).toBe(CONVERSATION_ID);
  });

  it("ignores a late refusal that belongs to an earlier chat", async () => {
    const service = createService();
    const onGone = vi.fn();
    service.setConversationGoneHandler(onGone);
    let refuse: (reason: unknown) => void = () => {};
    mockedAxios.patch.mockImplementationOnce(() => new Promise((_, reject) => { refuse = reject; }));

    const receipt = service.markRead(5);
    service.resetChatConversation();
    refuse(httpError(404, "CONVERSATION_NOT_FOUND"));
    await receipt;

    expect(onGone).not.toHaveBeenCalled();
  });
});

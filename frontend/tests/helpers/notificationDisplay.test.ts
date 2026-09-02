import { describe, expect, it } from "vitest";
import {
  CONVERSATION_STARTED_DESCRIPTION_PREFIX,
  formatConversationStartedDescription,
  formatNotificationDescription,
  getConversationShortId,
} from "@/helpers/notificationDisplay";
import type { Notification } from "@/interfaces/notification.interface";

function makeNotification(overrides: Partial<Notification>): Notification {
  return {
    id: "n1",
    title: "Title",
    description: "",
    timestamp: "2026-01-01T00:00:00Z",
    type: "info",
    read: false,
    ...overrides,
  };
}

describe("CONVERSATION_STARTED_DESCRIPTION_PREFIX", () => {
  it("has the expected prefix text", () => {
    expect(CONVERSATION_STARTED_DESCRIPTION_PREFIX).toBe(
      "A new conversation has started",
    );
  });
});

describe("formatConversationStartedDescription", () => {
  it("appends the short id and a trailing period", () => {
    expect(formatConversationStartedDescription("#abcd")).toBe(
      "A new conversation has started #abcd.",
    );
  });
});

describe("getConversationShortId", () => {
  it("returns a lowercased #xxxx match from the description", () => {
    const n = makeNotification({ description: "Conversation #A1B2 started" });
    expect(getConversationShortId(n)).toBe("#a1b2");
  });

  it("matches a description that is exactly a short id", () => {
    const n = makeNotification({ description: "#C3D4" });
    expect(getConversationShortId(n)).toBe("#c3d4");
  });

  it("derives the short id from the conversation query param in actionUrl (preserving case)", () => {
    const n = makeNotification({
      description: "A new conversation has started",
      actionUrl: "https://app/conversations?conversation=ABCDEF12-3456-7890",
    });
    // last 4 chars of "ABCDEF1234567890" -> "7890"
    expect(getConversationShortId(n)).toBe("#7890");
  });

  it("reads the conversation id after an ampersand-delimited query param", () => {
    const n = makeNotification({
      description: "no short here",
      actionUrl: "/app?foo=1&conversation=abcd1234",
    });
    expect(getConversationShortId(n)).toBe("#1234");
  });

  it("extracts the id from a parenthesised (ID: ...) fragment", () => {
    const n = makeNotification({
      description: "New conversation (ID: 1a2b3c4d...)",
    });
    // last 4 of "1a2b3c4d" -> "3c4d"
    expect(getConversationShortId(n)).toBe("#3c4d");
  });

  it("extracts the id from a 'Conversation <id>...' fragment", () => {
    const n = makeNotification({
      description: "Conversation deadbeef... needs attention",
    });
    // last 4 of "deadbeef" -> "beef"
    expect(getConversationShortId(n)).toBe("#beef");
  });

  it("strips dashes before taking the last four characters", () => {
    const n = makeNotification({
      description: "started",
      actionUrl: "/x?conversation=aa-bb-cc-1234",
    });
    // "aabbcc1234" -> "1234"
    expect(getConversationShortId(n)).toBe("#1234");
  });

  it("returns null when nothing matches", () => {
    const n = makeNotification({ description: "Hello world" });
    expect(getConversationShortId(n)).toBeNull();
  });
});

describe("formatNotificationDescription", () => {
  it("returns the description unchanged when no short id can be derived", () => {
    const n = makeNotification({ description: "Something happened" });
    expect(formatNotificationDescription(n)).toBe("Something happened");
  });

  it("uses the started template for conversation_started notifications", () => {
    const n = makeNotification({
      typeKey: "conversation_started",
      description: "Conversation deadbeef... started",
    });
    expect(formatNotificationDescription(n)).toBe(
      "A new conversation has started #beef.",
    );
  });

  it("replaces an (ID: ...) fragment with the short id for other types", () => {
    const n = makeNotification({
      typeKey: "other",
      description: "Ticket updated (ID: 1234abcd...)",
    });
    // last 4 of "1234abcd" -> "abcd"
    expect(formatNotificationDescription(n)).toBe("Ticket updated #abcd");
  });

  it("replaces a 'Conversation <id>...' fragment with the short id for other types", () => {
    const n = makeNotification({
      typeKey: "other",
      description: "Conversation deadbeef... needs review",
    });
    expect(formatNotificationDescription(n)).toBe(
      "Conversation #beef needs review",
    );
  });

  it("leaves the description untouched when a short id exists but no replaceable fragment is present", () => {
    const n = makeNotification({
      typeKey: "other",
      description: "Alert #a1b2 fired",
    });
    expect(formatNotificationDescription(n)).toBe("Alert #a1b2 fired");
  });
});

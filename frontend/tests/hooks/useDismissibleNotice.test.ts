import { describe, expect, it, vi } from "vitest";
import { isNewerThanDismissed } from "@/hooks/useDismissibleNotice";

vi.mock("@/services/auth", () => ({ getCurrentUserId: () => null, getTenantId: () => null }));

const NOVA = JSON.stringify(["bedrock/eu.amazon.nova-2-lite-v1:0"]);
const NOVA_AND_GPT = JSON.stringify(["bedrock/eu.amazon.nova-2-lite-v1:0", "openai/gpt-4o"]);

describe("isNewerThanDismissed", () => {
  it("compares ISO timestamps as times", () => {
    expect(isNewerThanDismissed("2026-10-21T10:00:00Z", "2026-10-20T10:00:00Z")).toBe(true);
    expect(isNewerThanDismissed("2026-10-19T10:00:00Z", "2026-10-20T10:00:00Z")).toBe(false);
    expect(isNewerThanDismissed("2026-10-20T10:00:00Z", "2026-10-20T10:00:00Z")).toBe(false);
  });

  it("compares anything else as text, even values Date.parse would read as a date", () => {
    expect(isNewerThanDismissed("Model 1", "2026-10-20")).toBe(true);
    expect(isNewerThanDismissed(NOVA, "2026-10-20")).toBe(true);
    expect(isNewerThanDismissed(NOVA, NOVA)).toBe(false);
    expect(isNewerThanDismissed(NOVA_AND_GPT, NOVA)).toBe(true);
    expect(isNewerThanDismissed(NOVA, NOVA_AND_GPT)).toBe(true);
  });
});

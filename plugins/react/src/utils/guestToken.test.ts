import { describe, expect, it } from "vitest";

import { isGuestTokenExpired, readTokenExpirySeconds } from "./guestToken";

const encodeSegment = (value: object): string =>
  Buffer.from(JSON.stringify(value)).toString("base64url");

const buildToken = (payload: object): string =>
  `${encodeSegment({ alg: "HS256", typ: "JWT" })}.${encodeSegment(payload)}.signature`;

const NOW_MS = Date.UTC(2026, 0, 15, 12, 0, 0);
const NOW_SECONDS = NOW_MS / 1000;

describe("readTokenExpirySeconds", () => {
  it("reads the exp claim from the token payload", () => {
    expect(readTokenExpirySeconds(buildToken({ exp: 1_800_000_000 }))).toBe(1_800_000_000);
  });

  it("decodes base64url payloads that contain '-' and '_' characters", () => {
    const payload = { exp: 1_800_000_000, sub: "guest:>>>???" };
    const payloadSegment = encodeSegment(payload);
    expect(payloadSegment).toContain("-");
    expect(payloadSegment).toContain("_");
    expect(readTokenExpirySeconds(buildToken(payload))).toBe(1_800_000_000);
  });

  it("returns null when the token has no exp claim", () => {
    expect(readTokenExpirySeconds(buildToken({ sub: "guest" }))).toBeNull();
  });

  it("returns null for values that are not tokens", () => {
    expect(readTokenExpirySeconds("not-a-token")).toBeNull();
    expect(readTokenExpirySeconds("header.%%%.signature")).toBeNull();
  });
});

describe("isGuestTokenExpired", () => {
  it("is true once the expiry time has passed", () => {
    expect(isGuestTokenExpired(buildToken({ exp: NOW_SECONDS - 1 }), NOW_MS)).toBe(true);
  });

  it("is true exactly at the expiry time", () => {
    expect(isGuestTokenExpired(buildToken({ exp: NOW_SECONDS }), NOW_MS)).toBe(true);
  });

  it("is false while the token is still valid", () => {
    expect(isGuestTokenExpired(buildToken({ exp: NOW_SECONDS + 3600 }), NOW_MS)).toBe(false);
  });

  it("leaves tokens it cannot read to the server", () => {
    expect(isGuestTokenExpired("not-a-token", NOW_MS)).toBe(false);
    expect(isGuestTokenExpired(buildToken({ sub: "guest" }), NOW_MS)).toBe(false);
  });
});

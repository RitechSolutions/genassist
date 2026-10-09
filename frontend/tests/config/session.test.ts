import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios, { AxiosError } from "axios";

vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return { ...actual, default: { ...actual.default, post: vi.fn() } };
});

type SessionModule = typeof import("@/config/session");

const mockedPost = vi.mocked(axios.post);
const NOW_MS = Date.UTC(2026, 0, 15, 12, 0, 0);
const ONE_HOUR = 60 * 60 * 1000;
const REFRESH_URL = "http://localhost/api/auth/refresh_token";

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

const encodeSegment = (value: object): string =>
  Buffer.from(JSON.stringify(value)).toString("base64url");

const tokenExpiringIn = (ms: number, label = "t"): string =>
  `${encodeSegment({ alg: "HS256", typ: "JWT" })}.${encodeSegment({ exp: (NOW_MS + ms) / 1000, label })}.signature`;

const rejectedWith = (status: number) =>
  new AxiosError("refused", "ERR_BAD_REQUEST", undefined, undefined, { status } as never);

let session: SessionModule;
let storage: MemoryStorage;
let assignPage: ReturnType<typeof vi.fn>;

function openPage(pathname: string): void {
  assignPage = vi.fn();
  vi.stubGlobal("window", { location: { pathname, assign: assignPage } });
}

function storeLogin(accessToken: string | null, refreshToken: string | null): void {
  if (accessToken) storage.setItem("access_token", accessToken);
  if (refreshToken) storage.setItem("refresh_token", refreshToken);
  storage.setItem("isAuthenticated", "true");
}

beforeEach(async () => {
  storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  openPage("/dashboard");
  vi.useFakeTimers();
  vi.setSystemTime(NOW_MS);
  mockedPost.mockReset();
  vi.resetModules();
  session = await import("@/config/session");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("reading token expiry", () => {
  it("reads the expiry from the token", () => {
    expect(session.readTokenExpiryMs(tokenExpiringIn(ONE_HOUR))).toBe(NOW_MS + ONE_HOUR);
  });

  it("leaves tokens it cannot read to the server", () => {
    expect(session.readTokenExpiryMs("not-a-token")).toBeNull();
    expect(session.isTokenExpiringWithin("not-a-token", session.ACCESS_TOKEN_RENEWAL_MARGIN_MS)).toBe(false);
  });

  it("flags a token that expires inside the margin", () => {
    const margin = session.ACCESS_TOKEN_RENEWAL_MARGIN_MS;
    expect(session.isTokenExpiringWithin(tokenExpiringIn(60 * 1000), margin)).toBe(true);
    expect(session.isTokenExpiringWithin(tokenExpiringIn(10 * 60 * 1000), margin)).toBe(false);
  });

  it("reads the token out of an Authorization header", () => {
    expect(session.readBearerToken("Bearer abc.def.ghi")).toBe("abc.def.ghi");
    expect(session.readBearerToken(undefined)).toBeNull();
  });
});

describe("shouldRenewBeforeRequest", () => {
  it("renews when the access token is about to expire", () => {
    storeLogin(tokenExpiringIn(60 * 1000), tokenExpiringIn(ONE_HOUR));
    expect(session.shouldRenewBeforeRequest()).toBe(true);
  });

  it("renews when only the renewal token is stored", () => {
    storeLogin(null, tokenExpiringIn(ONE_HOUR));
    expect(session.shouldRenewBeforeRequest()).toBe(true);
  });

  it("does not renew a fresh access token", () => {
    storeLogin(tokenExpiringIn(30 * 60 * 1000), tokenExpiringIn(ONE_HOUR));
    expect(session.shouldRenewBeforeRequest()).toBe(false);
  });

  it("does not renew when there is no login at all", () => {
    expect(session.shouldRenewBeforeRequest()).toBe(false);
  });
});

describe("renewSession", () => {
  it("renews once for all requests waiting at the same time and stores the new login", async () => {
    const staleToken = tokenExpiringIn(60 * 1000);
    storeLogin(staleToken, tokenExpiringIn(ONE_HOUR));
    const newAccessToken = tokenExpiringIn(ONE_HOUR, "new");
    mockedPost.mockResolvedValueOnce({
      data: { access_token: newAccessToken, refresh_token: "new-refresh", token_type: "bearer" },
    });

    const outcomes = await Promise.all([
      session.renewSession(REFRESH_URL, staleToken),
      session.renewSession(REFRESH_URL, staleToken),
    ]);

    expect(mockedPost).toHaveBeenCalledTimes(1);
    expect(mockedPost).toHaveBeenCalledWith(
      REFRESH_URL,
      expect.any(URLSearchParams),
      expect.objectContaining({ timeout: 15_000 }),
    );
    expect(outcomes).toEqual([
      { status: "renewed", accessToken: newAccessToken },
      { status: "renewed", accessToken: newAccessToken },
    ]);
    expect(storage.getItem("access_token")).toBe(newAccessToken);
    expect(storage.getItem("refresh_token")).toBe("new-refresh");
  });

  it("asks the server rather than trusting the local clock about the renewal token", async () => {
    const staleToken = tokenExpiringIn(-ONE_HOUR);
    storeLogin(staleToken, tokenExpiringIn(-1000));
    const newAccessToken = tokenExpiringIn(ONE_HOUR, "new");
    mockedPost.mockResolvedValueOnce({ data: { access_token: newAccessToken } });

    await expect(session.renewSession(REFRESH_URL, staleToken)).resolves.toEqual({
      status: "renewed",
      accessToken: newAccessToken,
    });
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("ends the session and clears the whole login when the server rejects the renewal", async () => {
    const staleToken = tokenExpiringIn(60 * 1000);
    storeLogin(staleToken, tokenExpiringIn(ONE_HOUR));
    storage.setItem("permissions", '["*"]');
    storage.setItem("user_roles", "[]");
    mockedPost.mockRejectedValueOnce(rejectedWith(401));

    await expect(session.renewSession(REFRESH_URL, staleToken)).resolves.toEqual({ status: "ended" });

    expect(storage.getItem("refresh_token")).toBeNull();
    expect(storage.getItem("permissions")).toBeNull();
    expect(storage.getItem("user_roles")).toBeNull();
    expect(assignPage).toHaveBeenCalledWith("/login");
  });

  it("ends the session without a request when no renewal token is stored", async () => {
    storeLogin(null, null);

    await expect(session.renewSession(REFRESH_URL, null)).resolves.toEqual({ status: "ended" });
    expect(mockedPost).not.toHaveBeenCalled();
  });

  it("stays on a public page such as the login page when the session ends", async () => {
    openPage("/login");

    await session.renewSession(REFRESH_URL, null);

    expect(assignPage).not.toHaveBeenCalled();
  });

  it("keeps the login when the server cannot be reached", async () => {
    const accessToken = tokenExpiringIn(60 * 1000);
    storeLogin(accessToken, tokenExpiringIn(ONE_HOUR));
    mockedPost.mockRejectedValueOnce(new AxiosError("Network Error", "ERR_NETWORK"));

    await expect(session.renewSession(REFRESH_URL, accessToken)).resolves.toEqual({ status: "unavailable" });

    expect(storage.getItem("access_token")).toBe(accessToken);
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("keeps the session when the server rate-limits the renewal", async () => {
    const accessToken = tokenExpiringIn(60 * 1000);
    storeLogin(accessToken, tokenExpiringIn(ONE_HOUR));
    mockedPost.mockRejectedValueOnce(rejectedWith(429));

    await expect(session.renewSession(REFRESH_URL, accessToken)).resolves.toEqual({ status: "unavailable" });
    expect(assignPage).not.toHaveBeenCalled();
  });
});

describe("several tabs sharing one login", () => {
  it("reuses a login another tab already renewed, without a request", async () => {
    const staleToken = tokenExpiringIn(60 * 1000, "stale");
    const renewedByOtherTab = tokenExpiringIn(ONE_HOUR, "other-tab");
    storeLogin(renewedByOtherTab, "rotated-by-other-tab");

    await expect(session.renewSession(REFRESH_URL, staleToken)).resolves.toEqual({
      status: "renewed",
      accessToken: renewedByOtherTab,
    });
    expect(mockedPost).not.toHaveBeenCalled();
  });

  it("uses the other tab's login when that tab wins a renewal race", async () => {
    const staleToken = tokenExpiringIn(60 * 1000, "stale");
    storeLogin(staleToken, tokenExpiringIn(ONE_HOUR));
    const renewedByOtherTab = tokenExpiringIn(ONE_HOUR, "other-tab");
    mockedPost.mockImplementationOnce(async () => {
      storage.setItem("access_token", renewedByOtherTab);
      throw rejectedWith(401);
    });

    await expect(session.renewSession(REFRESH_URL, staleToken)).resolves.toEqual({
      status: "renewed",
      accessToken: renewedByOtherTab,
    });
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("renews inside the browser's cross-tab lock when one is available", async () => {
    const request = vi.fn((_name: string, task: () => Promise<unknown>) => task());
    vi.stubGlobal("navigator", { locks: { request } });
    const staleToken = tokenExpiringIn(60 * 1000);
    storeLogin(staleToken, tokenExpiringIn(ONE_HOUR));
    mockedPost.mockResolvedValueOnce({ data: { access_token: tokenExpiringIn(ONE_HOUR, "new") } });

    await session.renewSession(REFRESH_URL, staleToken);

    expect(request).toHaveBeenCalledWith("genassist-session-renewal", expect.any(Function));
  });
});

describe("a device with a wrong clock", () => {
  it("stops renewing early once a freshly issued token already looks expired", async () => {
    const staleToken = tokenExpiringIn(60 * 1000);
    storeLogin(staleToken, tokenExpiringIn(ONE_HOUR));
    // The server's new token looks almost expired only because this device's clock runs fast
    mockedPost.mockResolvedValueOnce({ data: { access_token: tokenExpiringIn(30 * 1000, "fresh") } });

    await session.renewSession(REFRESH_URL, staleToken);

    expect(session.shouldRenewBeforeRequest()).toBe(false);
  });
});

describe("isPublicPath", () => {
  it("treats the login, sign-up and privacy pages as public", () => {
    expect(session.isPublicPath("/login")).toBe(true);
    expect(session.isPublicPath("/login/sso-callback")).toBe(true);
    expect(session.isPublicPath("/register")).toBe(true);
    expect(session.isPublicPath("/privacy")).toBe(true);
  });

  it("treats console pages as protected", () => {
    expect(session.isPublicPath("/dashboard")).toBe(false);
    expect(session.isPublicPath("/loginsettings")).toBe(false);
  });
});

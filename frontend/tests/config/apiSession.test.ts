import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios, { AxiosError, CanceledError, type InternalAxiosRequestConfig } from "axios";

type RequestHook = (config: InternalAxiosRequestConfig) => Promise<InternalAxiosRequestConfig>;
type ResponseErrorHook = (error: unknown) => Promise<unknown>;

const client = vi.hoisted(() => {
  const hooks: { request?: RequestHook; responseError?: ResponseErrorHook } = {};
  const instance = Object.assign(vi.fn(), {
    request: vi.fn(),
    interceptors: {
      request: { use: (onRequest: RequestHook) => { hooks.request = onRequest; } },
      response: { use: (_onOk: unknown, onError: ResponseErrorHook) => { hooks.responseError = onError; } },
    },
  });
  return { hooks, instance };
});

vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: { ...actual.default, create: () => client.instance, post: vi.fn(), get: vi.fn() },
  };
});

vi.mock("@sentry/react", () => ({ captureException: vi.fn() }));

vi.stubEnv("VITE_PUBLIC_API_URL", "http://localhost/api/");
await import("@/config/api");

const mockedPost = vi.mocked(axios.post);
const NOW_MS = Date.UTC(2026, 0, 15, 12, 0, 0);
const ONE_HOUR = 60 * 60 * 1000;

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

const tokenExpiringIn = (ms: number): string =>
  `${encodeSegment({ alg: "HS256", typ: "JWT" })}.${encodeSegment({ exp: (NOW_MS + ms) / 1000 })}.signature`;

const newRequest = (headers: Record<string, string> = {}) =>
  ({ url: "http://localhost/api/dashboard/notifications", headers: { ...headers } }) as unknown as InternalAxiosRequestConfig;

const refusedForLogin = (config: InternalAxiosRequestConfig) =>
  new AxiosError("refused", "ERR_BAD_REQUEST", config, undefined, { status: 401 } as never);

let storage: MemoryStorage;
let assignPage: ReturnType<typeof vi.fn>;

const runRequestHook = (config: InternalAxiosRequestConfig) => client.hooks.request!(config);
const runResponseErrorHook = (error: unknown) => client.hooks.responseError!(error);

beforeEach(() => {
  storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  assignPage = vi.fn();
  vi.stubGlobal("window", { location: { pathname: "/dashboard", assign: assignPage } });
  vi.useFakeTimers();
  vi.setSystemTime(NOW_MS);
  mockedPost.mockReset();
  client.instance.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("before a request is sent", () => {
  it("attaches the stored login when it is still fresh", async () => {
    const accessToken = tokenExpiringIn(30 * 60 * 1000);
    storage.setItem("access_token", accessToken);
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));

    const config = await runRequestHook(newRequest());

    expect(mockedPost).not.toHaveBeenCalled();
    expect(config.headers.Authorization).toBe(`Bearer ${accessToken}`);
  });

  it("renews a login that is about to expire and sends the request with the new one", async () => {
    storage.setItem("access_token", tokenExpiringIn(60 * 1000));
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    const renewedAccessToken = tokenExpiringIn(ONE_HOUR);
    mockedPost.mockResolvedValueOnce({ data: { access_token: renewedAccessToken, token_type: "bearer" } });

    const config = await runRequestHook(newRequest());

    expect(mockedPost).toHaveBeenCalledWith(
      "http://localhost/api/auth/refresh_token",
      expect.any(URLSearchParams),
      expect.anything(),
    );
    expect(config.headers.Authorization).toBe(`Bearer ${renewedAccessToken}`);
  });

  it("cancels the request and opens the login page once the server refuses to renew", async () => {
    storage.setItem("access_token", tokenExpiringIn(-ONE_HOUR));
    storage.setItem("refresh_token", tokenExpiringIn(-1000));
    mockedPost.mockRejectedValueOnce(
      new AxiosError("refused", "ERR_BAD_REQUEST", undefined, undefined, { status: 401 } as never),
    );

    await expect(runRequestHook(newRequest())).rejects.toBeInstanceOf(CanceledError);

    expect(mockedPost).toHaveBeenCalledTimes(1);
    expect(assignPage).toHaveBeenCalledWith("/login");
  });

  it("lets a request on the login page go ahead without a login once the old session has ended", async () => {
    vi.stubGlobal("window", { location: { pathname: "/login", assign: assignPage } });
    storage.setItem("access_token", tokenExpiringIn(-ONE_HOUR));
    storage.setItem("refresh_token", tokenExpiringIn(-1000));
    mockedPost.mockRejectedValueOnce(
      new AxiosError("refused", "ERR_BAD_REQUEST", undefined, undefined, { status: 401 } as never),
    );

    const config = await runRequestHook(newRequest());

    expect(config.headers.Authorization).toBeUndefined();
    expect(storage.getItem("refresh_token")).toBeNull();
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("leaves requests that carry their own login header alone", async () => {
    storage.setItem("access_token", tokenExpiringIn(60 * 1000));
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));

    const config = await runRequestHook(newRequest({ Authorization: "Bearer explicit" }));

    expect(mockedPost).not.toHaveBeenCalled();
    expect(config.headers.Authorization).toBe("Bearer explicit");
  });
});

describe("after a request is refused for its login", () => {
  it("renews once and retries the request with the new login", async () => {
    storage.setItem("access_token", tokenExpiringIn(30 * 60 * 1000));
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    const renewedAccessToken = tokenExpiringIn(ONE_HOUR);
    mockedPost.mockResolvedValueOnce({ data: { access_token: renewedAccessToken, token_type: "bearer" } });
    client.instance.mockResolvedValueOnce({ data: "retried" });
    const config = newRequest({ Authorization: `Bearer ${storage.getItem("access_token")}` });

    await expect(runResponseErrorHook(refusedForLogin(config))).resolves.toEqual({ data: "retried" });

    expect(mockedPost).toHaveBeenCalledTimes(1);
    expect(client.instance).toHaveBeenCalledTimes(1);
    expect(config.headers.Authorization).toBe(`Bearer ${renewedAccessToken}`);
  });

  it("retries with a login renewed in the meantime instead of renewing again", async () => {
    const refusedToken = tokenExpiringIn(-1000);
    const renewedMeanwhile = tokenExpiringIn(ONE_HOUR);
    storage.setItem("access_token", renewedMeanwhile);
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    client.instance.mockResolvedValueOnce({ data: "retried" });
    const config = newRequest({ Authorization: `Bearer ${refusedToken}` });

    await expect(runResponseErrorHook(refusedForLogin(config))).resolves.toEqual({ data: "retried" });

    expect(mockedPost).not.toHaveBeenCalled();
    expect(config.headers.Authorization).toBe(`Bearer ${renewedMeanwhile}`);
  });

  it("does not retry a second time when the retried request is refused again", async () => {
    const config = newRequest();
    (config as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;
    const refusal = refusedForLogin(config);

    await expect(runResponseErrorHook(refusal)).rejects.toBe(refusal);

    expect(mockedPost).not.toHaveBeenCalled();
    expect(client.instance).not.toHaveBeenCalled();
  });

  it("keeps the login and reports the refusal when the server cannot be reached to renew", async () => {
    const accessToken = tokenExpiringIn(30 * 60 * 1000);
    storage.setItem("access_token", accessToken);
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    mockedPost.mockRejectedValueOnce(new AxiosError("Network Error", "ERR_NETWORK"));
    const refusal = refusedForLogin(newRequest({ Authorization: `Bearer ${accessToken}` }));

    await expect(runResponseErrorHook(refusal)).rejects.toBe(refusal);

    expect(storage.getItem("access_token")).toBe(accessToken);
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("treats a wrong current password on a password change as wrong credentials, not an expired login", async () => {
    vi.stubGlobal("window", { location: { pathname: "/change-password", assign: assignPage } });
    storage.setItem("access_token", tokenExpiringIn(30 * 60 * 1000));
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    storage.setItem("tenant_id", "acme");
    const passwordChange = {
      url: "auth/change-password",
      headers: {},
    } as unknown as InternalAxiosRequestConfig;
    const wrongPassword = refusedForLogin(passwordChange);

    await expect(runResponseErrorHook(wrongPassword)).rejects.toBe(wrongPassword);

    expect(mockedPost).not.toHaveBeenCalled();
    expect(client.instance).not.toHaveBeenCalled();
    expect(storage.getItem("tenant_id")).toBe("acme");
    expect(assignPage).not.toHaveBeenCalled();
  });

  it("does not renew the old session for a refused sign-in", async () => {
    vi.stubGlobal("window", { location: { pathname: "/login", assign: assignPage } });
    storage.setItem("refresh_token", tokenExpiringIn(ONE_HOUR));
    const signIn = { url: "http://localhost/api/auth/token", headers: {} } as unknown as InternalAxiosRequestConfig;
    const wrongPassword = refusedForLogin(signIn);

    await expect(runResponseErrorHook(wrongPassword)).rejects.toBe(wrongPassword);
    expect(mockedPost).not.toHaveBeenCalled();
  });

  it("ignores refusals that are not about the login", async () => {
    const forbidden = new AxiosError("forbidden", "ERR_BAD_REQUEST", newRequest(), undefined, { status: 403 } as never);

    await expect(runResponseErrorHook(forbidden)).rejects.toBe(forbidden);
    expect(mockedPost).not.toHaveBeenCalled();
  });
});

import axios, { AxiosError } from "axios";
import { jwtDecode } from "jwt-decode";

/** The access token is renewed when less than this remains, so no request is sent with an expired one. */
export const ACCESS_TOKEN_RENEWAL_MARGIN_MS = 2 * 60 * 1000;

/** Everything a login leaves in browser storage; cleared together when a session ends. */
export const AUTH_STORAGE_KEYS = [
  "access_token",
  "refresh_token",
  "token_type",
  "isAuthenticated",
  "force_upd_pass_date",
  "tenant_id",
  "permissions",
  "user_roles",
  "auth_username",
] as const;

const LOGIN_PATH = "/login";
const PUBLIC_PATHS = ["/login", "/register", "/privacy", "/unauthorized", "/onboarding"];
const RENEWAL_LOCK_NAME = "genassist-session-renewal";
const RENEWAL_TIMEOUT_MS = 15_000;

export type RenewalOutcome =
  | { status: "renewed"; accessToken: string }
  | { status: "ended" }
  | { status: "unavailable" };

interface RenewalResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  force_upd_pass_date?: string;
}

// Set when a freshly issued token already looks expired, which means this device's clock is wrong
let isLocalClockUnreliable = false;

/** Expiry of a JWT in milliseconds since the epoch, or null when it cannot be read. */
export function readTokenExpiryMs(token: string | null): number | null {
  if (!token) return null;
  try {
    const { exp } = jwtDecode<{ exp?: number }>(token);
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

/** True when the token's expiry falls within `marginMs`; tokens without a readable expiry are left to the server. */
export function isTokenExpiringWithin(
  token: string | null,
  marginMs: number,
  nowMs: number = Date.now(),
): boolean {
  const expiryMs = readTokenExpiryMs(token);
  if (expiryMs === null) return false;
  return expiryMs - nowMs <= marginMs;
}

/** The token part of an `Authorization` header such as "Bearer abc", or null. */
export function readBearerToken(authorizationHeader: unknown): string | null {
  if (typeof authorizationHeader !== "string") return null;
  const [, token] = authorizationHeader.split(" ");
  return token || null;
}

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export function clearAuthStorage(): void {
  AUTH_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
}

/** Ends a session that can no longer be renewed: clears the stored login and leaves protected pages for the login page. */
export function endSession(): void {
  clearAuthStorage();
  const isOnProtectedPage = typeof window !== "undefined" && !isPublicPath(window.location.pathname);
  if (isOnProtectedPage) window.location.assign(LOGIN_PATH);
}

export function formatAuthorizationHeader(accessToken: string): string {
  const storedType = localStorage.getItem("token_type") || "Bearer";
  const tokenType = storedType.toLowerCase() === "bearer" ? "Bearer" : storedType;
  return `${tokenType} ${accessToken}`;
}

/** Whether the stored access token must be renewed before it is attached to a request. */
export function shouldRenewBeforeRequest(nowMs: number = Date.now()): boolean {
  if (isLocalClockUnreliable || !localStorage.getItem("refresh_token")) return false;
  const accessToken = localStorage.getItem("access_token");
  const isAccessTokenMissing = !accessToken;
  return isAccessTokenMissing || isTokenExpiringWithin(accessToken, ACCESS_TOKEN_RENEWAL_MARGIN_MS, nowMs);
}

let pendingRenewal: Promise<RenewalOutcome> | null = null;

/** Renews the login once for all callers in this tab; `staleAccessToken` is the token the caller found unusable. */
export function renewSession(refreshUrl: string, staleAccessToken: string | null): Promise<RenewalOutcome> {
  if (!pendingRenewal) {
    pendingRenewal = withRenewalLock(() => requestRenewal(refreshUrl, staleAccessToken)).finally(() => {
      pendingRenewal = null;
    });
  }
  return pendingRenewal;
}

/** Lets one tab at a time renew the shared login; browsers without Web Locks renew directly. */
async function withRenewalLock(renew: () => Promise<RenewalOutcome>): Promise<RenewalOutcome> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (!locks) return renew();
  try {
    return await locks.request(RENEWAL_LOCK_NAME, renew);
  } catch {
    // The browser refused the lock (e.g. a sandboxed frame); renew without it
    return renew();
  }
}

async function requestRenewal(refreshUrl: string, staleAccessToken: string | null): Promise<RenewalOutcome> {
  const accessTokenFromOtherTab = readAccessTokenRenewedElsewhere(staleAccessToken);
  if (accessTokenFromOtherTab) return { status: "renewed", accessToken: accessTokenFromOtherTab };

  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    endSession();
    return { status: "ended" };
  }

  try {
    const renewed = await postRenewal(refreshUrl, refreshToken);
    storeRenewedTokens(renewed);
    detectUnreliableClock(renewed.access_token);
    return { status: "renewed", accessToken: renewed.access_token };
  } catch (error) {
    return handleRenewalFailure(error, staleAccessToken);
  }
}

async function postRenewal(refreshUrl: string, refreshToken: string): Promise<RenewalResponse> {
  const tenantId = localStorage.getItem("tenant_id");
  const { data } = await axios.post<RenewalResponse>(
    refreshUrl,
    new URLSearchParams({ refresh_token: refreshToken }),
    {
      timeout: RENEWAL_TIMEOUT_MS,
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        ...(tenantId ? { "x-tenant-id": tenantId } : {}),
      },
    },
  );
  return data;
}

function storeRenewedTokens(renewed: RenewalResponse): void {
  localStorage.setItem("access_token", renewed.access_token);
  localStorage.setItem("token_type", renewed.token_type || "Bearer");
  localStorage.setItem("isAuthenticated", "true");
  if (renewed.refresh_token) localStorage.setItem("refresh_token", renewed.refresh_token);
  if (renewed.force_upd_pass_date) localStorage.setItem("force_upd_pass_date", renewed.force_upd_pass_date);
}

/** A token the server has just issued cannot be close to expiry unless this device's clock is wrong. */
function detectUnreliableClock(freshAccessToken: string): void {
  if (isTokenExpiringWithin(freshAccessToken, ACCESS_TOKEN_RENEWAL_MARGIN_MS)) {
    isLocalClockUnreliable = true;
  }
}

function handleRenewalFailure(error: unknown, staleAccessToken: string | null): RenewalOutcome {
  const accessTokenFromOtherTab = readAccessTokenRenewedElsewhere(staleAccessToken);
  if (accessTokenFromOtherTab) return { status: "renewed", accessToken: accessTokenFromOtherTab };

  const status = error instanceof AxiosError ? error.response?.status : undefined;
  const isRenewalRejected = status === 401 || status === 403;
  if (!isRenewalRejected) return { status: "unavailable" };

  endSession();
  return { status: "ended" };
}

/** The stored access token when another tab replaced the one this tab found unusable. */
function readAccessTokenRenewedElsewhere(staleAccessToken: string | null): string | null {
  const storedAccessToken = localStorage.getItem("access_token");
  const wasReplaced = Boolean(storedAccessToken) && storedAccessToken !== staleAccessToken;
  return wasReplaced ? storedAccessToken : null;
}

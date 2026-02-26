import axios, { Method, AxiosRequestConfig, AxiosError } from "axios";
import { setServerDown, setServerUp } from "@/config/serverStatus";

const AUTH_KEYS = ["access_token", "refresh_token", "token_type", "isAuthenticated", "force_upd_pass_date", "tenant_id"] as const;

const clearAuthStorage = () => AUTH_KEYS.forEach((key) => localStorage.removeItem(key));

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    error ? reject(error) : resolve(token);
  });
  failedQueue = [];
};

const ensureTrailingSlash = (url: string): string =>
  url.endsWith("/") ? url : `${url}/`;

const api = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000, // Increased to 2 minutes for SQL operations
});

// Interceptor: Request
api.interceptors.request.use(
  (config) => {
    const accessToken = localStorage.getItem("access_token");
    const tokenType = localStorage.getItem("token_type") || "Bearer";
    const tenantId = localStorage.getItem("tenant_id");

    if (accessToken && !config.headers.Authorization) {
      const properTokenType = tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType;
      config.headers.Authorization = `${properTokenType} ${accessToken}`;
    }

    // Add tenant ID header if available
    if (tenantId) {
      config.headers["x-tenant-id"] = tenantId;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor: Response
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 errors with token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        }).catch(err => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem("refresh_token");

      if (!refreshToken) {
        isRefreshing = false;
        processQueue(error, null);
        clearAuthStorage();
        return Promise.reject(error);
      }

      try {
        const baseURL = await getApiUrl();
        const tenantId = localStorage.getItem("tenant_id");
        const params = new URLSearchParams({ refresh_token: refreshToken });

        const { data } = await axios.post(`${baseURL}auth/refresh_token`, params, {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            ...(tenantId ? { "x-tenant-id": tenantId } : {}),
          },
        });

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("token_type", data.token_type || "Bearer");
        localStorage.setItem("isAuthenticated", "true");
        if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
        if (data.force_upd_pass_date) localStorage.setItem("force_upd_pass_date", data.force_upd_pass_date);

        originalRequest.headers.Authorization = `${data.token_type || "Bearer"} ${data.access_token}`;
        processQueue(null, data.access_token);
        isRefreshing = false;

        return api(originalRequest);
      } catch (refreshError) {
        clearAuthStorage();
        processQueue(refreshError, null);
        isRefreshing = false;
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

const API_URL = import.meta.env.VITE_PUBLIC_API_URL
const WEBSOCKET_URL = import.meta.env.VITE_WEBSOCKET_PUBLIC_URL

/** Whether WebSocket connections are enabled (VITE_WS=true/false). Defaults to true when unset.
 *  Note: Vite reads env at dev server start / build time; restart the dev server after changing .env. */
export const isWsEnabled =
  (import.meta.env.VITE_WS ?? "true").toString().toLowerCase() === "true";

export const getApiUrl = async (): Promise<string> => {
  return ensureTrailingSlash(API_URL);
};

export const getApiUrlString = ensureTrailingSlash(API_URL);

export const getWsUrl = async (): Promise<string> => {
  if (!isWsEnabled) {
    return Promise.reject(new Error("WebSocket is disabled (VITE_WS=false)"));
  }
  return WEBSOCKET_URL;
};

export const apiRequest = async <T>(
  method: Method,
  endpoint: string,
  data?: Record<string, unknown> | URLSearchParams,
  config: Partial<AxiosRequestConfig> = {}
): Promise<T | null> => {
  const baseURL = await getApiUrl();
  // remove starting slash from endpoint
  let fullUrl = `${baseURL}${endpoint.replace(/^\//, "")}`
  // remove last slash && remove last slash also before ? or & or #
  fullUrl = fullUrl.replace(/\/$/, "").replace(/\/([?&#])/, "$1");

  try {
    const response = await api.request<T>({
      method,
      url: fullUrl,
      data,
      ...config,
    });
    // mark up on any sucessful request
    setServerUp();
    return response.data;
  } catch (error) {
    const errObj = error as AxiosError;
    const status = errObj.response?.status;
    const hasResponse = !!errObj.response;
    const code = errObj.code;

    if (status === 403) {
      setServerUp();
      return null;
    }

    // Mark server as down for 5xx errors allowed 500, 501
    if (status && status > 501) {
      setServerDown();
    } else if (hasResponse) {
      setServerUp();
    } else {
      const networkCodes = new Set([
        "ERR_NETWORK",
        "ECONNABORTED",
        "ERR_CONNECTION_REFUSED",
        "ERR_CONNECTION_RESET",
        "ERR_SOCKET_NOT_CONNECTED",
        "ENOTFOUND",
      ]);
      if (networkCodes.has(code ?? "")) {
        const healthy = await probeApiHealth();
        if (!healthy) {
          setServerDown();
        }
      } else {
        setServerUp();
      }
    }
    throw error;
  }
};

export { api };

// Simple connectivity probe used by Retry buttons
export const probeApiHealth = async (): Promise<boolean> => {
  const baseURL = await getApiUrl();
  const candidates = [
    `${baseURL.replace(/\/$/, "")}/playground/health`,
    `${baseURL.replace(/\/$/, "")}/health`,
    baseURL,
  ];
  for (const url of candidates) {
    try {
      const response = await axios.get(url, { timeout: 2000, validateStatus: () => true });
      // Treat any 5xx error as server down
      if (response.status >= 500) {
        setServerDown();
        return false;
      }
      setServerUp();
      return true;
    } catch {
      // Network error - continue trying other endpoints
    }
  }
  // All endpoints failed
  setServerDown();
  return false;
};

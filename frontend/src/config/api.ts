import axios, { Method, AxiosRequestConfig, AxiosError } from "axios";
import { setServerDown, setServerUp } from "@/config/serverStatus";

let cachedApiUrl: string | null = null;
const API_URL_STORAGE_KEY = "cachedApiUrl";

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
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
        
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("token_type");
        localStorage.removeItem("isAuthenticated");
        localStorage.removeItem("force_upd_pass_date");
        localStorage.removeItem("tenant_id");
        
        return Promise.reject(error);
      }
      
      try {
        const baseURL = await getApiUrl();
        const params = new URLSearchParams();
        params.append("refresh_token", refreshToken);
        
        const refreshResponse = await axios.post(
          `${baseURL}auth/refresh_token`,
          params,
          {
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
          }
        );
        
        const { access_token, token_type, force_upd_pass_date } = refreshResponse.data;
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("token_type", token_type || "Bearer");
        
        // Store force_upd_pass_date if provided in refresh response
        if (force_upd_pass_date) {
          localStorage.setItem("force_upd_pass_date", force_upd_pass_date);
        }
        
        localStorage.setItem("isAuthenticated", "true");
        
        // Update the Authorization header for the retry
        originalRequest.headers.Authorization = `${token_type || "Bearer"} ${access_token}`;
        
        processQueue(null, access_token);
        isRefreshing = false;
        
        // Retry the original request
        return api(originalRequest);
      } catch (refreshError) {
        // If refresh fails, clear tokens and redirect to login and authentication state
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("token_type");
        localStorage.removeItem("isAuthenticated");
        localStorage.removeItem("force_upd_pass_date");
        localStorage.removeItem("tenant_id");
        
        processQueue(refreshError, null);
        isRefreshing = false;
        
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export const clearCachedApiUrl = (): void => {
  cachedApiUrl = null;
  try {
    localStorage.removeItem(API_URL_STORAGE_KEY);
  } catch (error) {
    // ignore
  }
};

export const getApiUrl = async (): Promise<string> => {
  // Try to load from localStorage first
  try {
    const storedApiUrl = localStorage.getItem(API_URL_STORAGE_KEY);
    if (storedApiUrl) {
      cachedApiUrl = storedApiUrl;
      return storedApiUrl;
    }
  } catch (error) {
    // ignore
  }

  if (cachedApiUrl) {
    return cachedApiUrl;
  }

  const privateApi = import.meta.env.VITE_PRIVATE_API_URL;
  const publicApi = import.meta.env.VITE_PUBLIC_API_URL;

  try {
    await axios.get(privateApi, { timeout: 1000 });
    cachedApiUrl = ensureTrailingSlash(privateApi);
    try {
      localStorage.setItem(API_URL_STORAGE_KEY, cachedApiUrl);
    } catch (error) {
      // ignore
    }
    return cachedApiUrl;
  } catch (err) {
    if (
      err.code != "ECONNABORTED" &&
      err.response &&
      err.response.status == 404
    ) {
      cachedApiUrl = ensureTrailingSlash(privateApi);
      try {
        localStorage.setItem(API_URL_STORAGE_KEY, cachedApiUrl);
      } catch (error) {
        // ignore
      }
      return cachedApiUrl;
    } else {
      cachedApiUrl = ensureTrailingSlash(publicApi);
      try {
        localStorage.setItem(API_URL_STORAGE_KEY, cachedApiUrl);
      } catch (error) {
        // ignore
      }
      return cachedApiUrl;
    }
  }
};

const WEBSOCKET_URL_PUBLIC = import.meta.env.VITE_WEBSOCKET_PUBLIC_URL
const WEBSOCKET_URL_PRIVATE = import.meta.env.VITE_WEBSOCKET_PRIVATE_URL

export const getWsUrl = async (): Promise<string> => {
    const url = await getApiUrl();
    if(url.indexOf(import.meta.env.VITE_PRIVATE_API_URL) >= 0)
      return WEBSOCKET_URL_PRIVATE;
    else  
      return WEBSOCKET_URL_PUBLIC; 
};

export const apiRequest = async <T>(
  method: Method,
  endpoint: string,
  data?: Record<string, unknown> | URLSearchParams,
  config: Partial<AxiosRequestConfig> = {}
): Promise<T | null> => {
  const baseURL = await getApiUrl();
  const fullUrl = `${baseURL}${endpoint.replace(/^\//, "")}`;

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

    if (status === 503) {
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
    `${baseURL.replace(/\/$/, "")}/healthz`,
    `${baseURL.replace(/\/$/, "")}/health`,
    baseURL,
  ];
  for (const url of candidates) {
    try {
      const response = await axios.get(url, { timeout: 2000, validateStatus: () => true });
      if (response.status === 503) {
        setServerDown();
        return false;
      }
      setServerUp();
      return true;
    } catch {
      setServerDown();
    }
  }
  return false;
};

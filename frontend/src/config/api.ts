import axios, { Method, AxiosRequestConfig } from "axios";

let cachedApiUrl: string | null = null;
const API_URL_STORAGE_KEY = "cachedApiUrl";

const ensureTrailingSlash = (url: string): string =>
  url.endsWith("/") ? url : `${url}/`;

const api = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

api.interceptors.request.use(
  (config) => {
    const accessToken = localStorage.getItem("access_token");
    const tokenType = localStorage.getItem("token_type") || "Bearer";
    
    if (accessToken && !config.headers.Authorization) {
      config.headers.Authorization = `${tokenType} ${accessToken}`;
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
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");
      
      if (!refreshToken) {
        console.warn("No refresh token found");
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
        
        const { access_token, token_type } = refreshResponse.data;
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("token_type", token_type || "Bearer");
        
        // Update the Authorization header for the retry
        originalRequest.headers.Authorization = `${token_type} ${access_token}`;
        
        // Retry the original request
        return api(originalRequest);
      } catch (refreshError) {
        // If refresh fails, clear tokens and redirect to login
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("token_type");
        console.warn("Token refresh failed:", refreshError);
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
    console.log(error);
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
    console.warn("Failed to get API URL from localStorage", error);
  }

  if (cachedApiUrl) {
    return cachedApiUrl;
  }

  const privateApi = import.meta.env.VITE_PRIVATE_API_URL;
  const publicApi = import.meta.env.VITE_PUBLIC_API_URL;

  try {
    await axios.get(privateApi, { timeout: 1000 });
    cachedApiUrl = ensureTrailingSlash(privateApi);
    console.log(`Connected to Private API: ${privateApi}`);
    try {
      localStorage.setItem(API_URL_STORAGE_KEY, cachedApiUrl);
    } catch (error) {
      console.log(error);
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
        console.log(error);
      }
      return cachedApiUrl;
    } else {
      console.warn(
        `Private API failed: ${privateApi}. ${err.message} Switching to Public API...`
      );
      cachedApiUrl = ensureTrailingSlash(publicApi);
      try {
        localStorage.setItem(API_URL_STORAGE_KEY, cachedApiUrl);
        console.log(`Connecting to Public API: ${publicApi}`);

      } catch (error) {
        console.warn("Failed to save API URL to localStorage", error);
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
    return response.data;
  } catch (error) {
    if (error.response?.status === 403) {
      return null;
    }
    // Clear the cached URL on other errors, as the API might be down
    clearCachedApiUrl();
    console.error("Can't Connect to Backend:", error);
    throw error;
  }
};
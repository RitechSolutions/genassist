import axios, { Method, AxiosRequestConfig } from "axios";

const ensureTrailingSlash = (url: string): string =>
  url.endsWith("/") ? url : `${url}/`;

const api = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  const tokenType = localStorage.getItem("token_type");

  if (token && tokenType) {
    config.headers.Authorization = `${tokenType} ${token}`;
  }

  return config;
});

export const PRIVATE_WS = {
  host: "api-dev-internal-genassist.ritech.io",
  port: "8751",
};
export const PUBLIC_WS = {
  host: "api-dev-genassist.ritech.io",
  port: "8751",
};

export const getApiUrl = async (): Promise<string> => {
  const privateApi = "###_GENASSIST_API_PRIVATE_URL_###";
  const publicApi = "###_GENASSIST_API_PUBLIC_URL_###";
  console.log(`Checking Private API: ${privateApi}`);

  try {
    await axios.get(privateApi, { timeout: 1000 });
    console.log(`Connected to Private API: ${privateApi}`);
    return ensureTrailingSlash(privateApi);
  } catch (err) {
    if (
      err.code != "ECONNABORTED" &&
      err.response &&
      err.response.status == 404
    )
      return ensureTrailingSlash(privateApi);
    else {
      console.warn(
        `Private API failed: ${privateApi}. ${err.message} Switching to Public API...`
      );

      console.log(`Connecting to Public API: ${publicApi}`);
      return ensureTrailingSlash(publicApi);
    }
  }
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
  } catch (error: any) {
    if (error.response?.status === 403) {
      return null;
    }
    console.error("Can't Connect to Backend:", error);

    throw new Error(
      error.response?.data?.message || "An unexpected error occurred."
    );
  }
};

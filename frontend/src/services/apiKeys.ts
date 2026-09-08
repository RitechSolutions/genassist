import { apiRequest } from "@/config/api";
import { ApiKey } from "@/interfaces/api-key.interface";
import { PaginatedResponse } from "@/interfaces/common.interface";

export const getApiKeysPaginated = async (
  page: number = 1,
  pageSize: number = 20,
  search?: string
): Promise<PaginatedResponse<ApiKey>> => {
  const limit = Math.min(Math.max(1, pageSize), 100);
  const skip = (Math.max(1, page) - 1) * limit;
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  const trimmed = search?.trim();
  if (trimmed) params.set("search", trimmed);

  const response = await apiRequest<PaginatedResponse<ApiKey>>(
    "GET",
    `api-keys/list?${params.toString()}`
  );
  // apiRequest returns null on 403; other failures still throw.
  return (
    response ?? { items: [], total: 0, page: 1, page_size: limit, total_pages: 0 }
  );
};

export const getApiKey = async (id: string): Promise<ApiKey | null> => {
  const data = await apiRequest<ApiKey>("GET", `api-keys/${id}/`);
  if (!data) {
    return null;
  }
  return data;
};

export const createApiKey = async (apiKeyData: Partial<ApiKey> & { role_ids?: string[] }): Promise<ApiKey> => {
  type RequestData = {
    name?: string;
    is_active?: number;
    role_ids: string[];
    assigned_user_id?: string;
    user_id?: string;
    agent_id?: string;
    expires_in_days?: number;
  };

  const requestData: RequestData = {
    name: apiKeyData.name,
    is_active: apiKeyData.is_active,
    role_ids: apiKeyData.role_ids || [],
    assigned_user_id: apiKeyData.user_id,
    user_id: apiKeyData.user_id,
  };

  if (apiKeyData.agent_id) {
    requestData.agent_id = apiKeyData.agent_id;
  }

  if (typeof apiKeyData.expires_in_days === "number") {
    requestData.expires_in_days = apiKeyData.expires_in_days;
  }

  const response = await apiRequest<ApiKey>("POST", "api-keys/", requestData);
  if (!response) throw new Error("Failed to create API key");

  return response;
};

export const updateApiKey = async (
  id: string,
  apiKeyData: Partial<ApiKey>
): Promise<ApiKey> => {
  const requestData: Record<string, unknown> = {
    name: apiKeyData.name,
    is_active: Boolean(apiKeyData.is_active),
    user_id: apiKeyData.user_id,
  };

  if (apiKeyData.role_ids) {
    requestData.role_ids = apiKeyData.role_ids;
  }

  if (apiKeyData.agent_id) {
    requestData.agent_id = apiKeyData.agent_id;
  }

  if (typeof apiKeyData.expires_in_days === "number") {
    requestData.expires_in_days = apiKeyData.expires_in_days;
  }

  const response = await apiRequest<ApiKey>(
    "PATCH",
    `api-keys/${id}/`,
    requestData
  );

  if (!response) {
    throw new Error("Failed to update API key");
  }

  return response;
};

export const revokeApiKey = async (id: string): Promise<void> => {
  await apiRequest("DELETE", `api-keys/${id}/`);
};

export const rotateApiKey = async (
  id: string,
  overlapSeconds = 0
): Promise<ApiKey> => {
  const response = await apiRequest<ApiKey>("POST", `api-keys/${id}/rotate`, {
    overlap_seconds: overlapSeconds,
  });
  if (!response) {
    throw new Error("Failed to rotate API key");
  }
  return response;
};

export const revealApiKey = async (id: string): Promise<ApiKey> => {
  const response = await apiRequest<ApiKey>("POST", `api-keys/${id}/reveal`);
  if (!response) throw new Error("Failed to reveal API key");
  return response;
};

export const getApiKeys = async (userId?: string): Promise<ApiKey[]> => {
  let url = "api-keys/";

  if (userId) {
    url += `?user_id=${encodeURIComponent(userId)}`;
  }

  const data = await apiRequest<ApiKey[]>("GET", url);
  if (!data) {
    return [];
  }
  if (!Array.isArray(data)) {
    return [];
  }

  return data;
};

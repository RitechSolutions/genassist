import { apiRequest } from "@/config/api";
import { ApiKey } from "@/interfaces/api-key.interface";

export const getAllApiKeys = async (): Promise<ApiKey[]> => {
  const data = await apiRequest<ApiKey[]>("GET", "api-keys/");
  if (!data) {
    return [];
  }

  if (!Array.isArray(data)) {
    return [];
  }

  return data;
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

export const getApiKeys = async (userId?: string): Promise<ApiKey[]> => {
  let url = "api-keys/";

  if (userId) {
    url += `?user_id=${encodeURIComponent(userId)}`;
  }

  // no cache header
  const headers = { "Cache-Control": "no-cache" };

  const data = await apiRequest<ApiKey[]>("GET", url, undefined, { headers });
  if (!data) {
    return [];
  }
  if (!Array.isArray(data)) {
    return [];
  }

  return data;
};

import { apiRequest } from "@/config/api";
import { ApiKey } from "@/interfaces/api-key.interface";

export const getAllApiKeys = async (): Promise<ApiKey[]> => {
  try {
    const data = await apiRequest<ApiKey[]>("GET", "api-keys/");
    if (!data) {
      return [];
    }
    
    if (!Array.isArray(data)) {
      return [];
    }
    
    return data;
  } catch (error) {
    throw error;
  }
};

export const getApiKey = async (id: string): Promise<ApiKey | null> => {
  try {
    const data = await apiRequest<ApiKey>("GET", `api-keys/${id}/`);
    if (!data) {
      return null;
    }
    return data;
  } catch (error) {
    throw error;
  }
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

  try {
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
  } catch (error) {
    throw error;
  }
};

export const updateApiKey = async (id: string, apiKeyData: Partial<ApiKey>): Promise<ApiKey> => {
  try {
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

    const response = await apiRequest<ApiKey>("PATCH", `api-keys/${id}/`, requestData);

    if (!response) {
      throw new Error("Failed to update API key");
    }

    return response;
  } catch (error) {
    throw error;
  }
};

export const revokeApiKey = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `api-keys/${id}/`);
  } catch (error) {
    throw error;
  }
}; 

export const getApiKeys = async (userId?: string): Promise<ApiKey[]> => {
  let url = "api-keys/";
  if (userId) {
    url += `?user_id=${encodeURIComponent(userId)}`;
  }
  try {
    const data = await apiRequest<ApiKey[]>("GET", url);
    if (!data) {
      return [];
    }
    if (!Array.isArray(data)) {
      return [];
    }
    return data;
  } catch (error) {
    throw error;
  }
};
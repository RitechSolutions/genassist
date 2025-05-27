import { apiRequest } from "@/config/api";
import { ApiKey } from "@/interfaces/api-key.interface";

export const getAllApiKeys = async (): Promise<ApiKey[]> => {
  try {
    const data = await apiRequest<ApiKey[]>("GET", "api-keys/");
    if (!data) {
      console.warn("No API keys data returned from server");
      return [];
    }
    
    if (!Array.isArray(data)) {
      console.error("API keys data is not an array:", data);
      return [];
    }
    
    return data;
  } catch (error) {
    console.error("Error fetching API keys:", error);
    throw error;
  }
};

export const getApiKey = async (id: string): Promise<ApiKey | null> => {
  try {
    const data = await apiRequest<ApiKey>("GET", `api-keys/${id}`);
    if (!data) {
      console.warn("API key not found");
      return null;
    }
    return data;
  } catch (error) {
    console.error("Error fetching API key:", error);
    throw error;
  }
};


export const createApiKey = async (apiKeyData: Partial<ApiKey> & { role_ids?: string[] }): Promise<ApiKey> => {
  try {
    const requestData = {
      name: apiKeyData.name,
      is_active: apiKeyData.is_active,
      role_ids: apiKeyData.role_ids || [],
      assigned_user_id: apiKeyData.user_id,
      user_id: apiKeyData.user_id,
    };
    
    const response = await apiRequest<ApiKey>("POST", "api-keys", requestData);
    if (!response) throw new Error("Failed to create API key");

    return response;
  } catch (error) {
    console.error("Error creating API key:", error);
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

    const response = await apiRequest<ApiKey>("PATCH", `api-keys/${id}`, requestData);

    if (!response) {
      throw new Error("Failed to update API key");
    }

    return response;
  } catch (error) {
    console.error("Error occurred while updating API key:", error);
    throw error;
  }
};

export const revokeApiKey = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `api-keys/${id}`);
  } catch (error) {
    console.error("Error revoking API key:", error);
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
      console.warn("No API keys data returned from server");
      return [];
    }
    if (!Array.isArray(data)) {
      console.error("API keys data is not an array:", data);
      return [];
    }
    return data;
  } catch (error) {
    console.error("Error fetching API keys:", error);
    throw error;
  }
};
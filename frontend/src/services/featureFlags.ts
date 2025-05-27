import { apiRequest } from "@/config/api";
import { FeatureFlag, FeatureFlagFormData } from "@/interfaces/featureFlag.interface";

const API_ENDPOINT = "feature-flags";

export const getFeatureFlags = async (): Promise<FeatureFlag[]> => {
  const response = await apiRequest<FeatureFlag[]>(
    "GET",
    API_ENDPOINT
  );
  return response || [];
};

export const getFeatureFlag = async (id: string): Promise<FeatureFlag | null> => {
  return await apiRequest<FeatureFlag>(
    "GET",
    `${API_ENDPOINT}/${id}`
  );
};

export const createFeatureFlag = async (data: FeatureFlagFormData): Promise<FeatureFlag | null> => {
  const requestData = { ...data } as unknown as Record<string, unknown>;
  return await apiRequest<FeatureFlag>(
    "POST",
    API_ENDPOINT,
    requestData
  );
};

export const updateFeatureFlag = async (id: string, data: FeatureFlagFormData): Promise<FeatureFlag | null> => {
  const requestData = { ...data } as unknown as Record<string, unknown>;
  return await apiRequest<FeatureFlag>(
    "PATCH",
    `${API_ENDPOINT}/${id}`,
    requestData
  );
};

export const deleteFeatureFlag = async (id: string): Promise<void> => {
  await apiRequest(
    "DELETE",
    `${API_ENDPOINT}/${id}`
  );
};

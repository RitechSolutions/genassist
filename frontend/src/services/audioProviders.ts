import { apiRequest } from "@/config/api";
import { AudioProvider, AudioProviderMinimal, AudioProviderNodeSchemas } from "@/interfaces/audioProvider.interface";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";

export const getAllAudioProviders = async (): Promise<AudioProvider[]> => {
  return apiRequest<AudioProvider[]>("GET", "audio-providers/");
};

export const getAudioProvidersMinimal = async (): Promise<AudioProviderMinimal[]> => {
  return apiRequest<AudioProviderMinimal[]>("GET", "audio-providers/minimal");
};

export const getAudioProvidersByCapability = async (capability: string): Promise<AudioProvider[]> => {
  return apiRequest<AudioProvider[]>("GET", `audio-providers/by-capability/${capability}`);
};

export const getAudioProvider = async (id: string): Promise<AudioProvider> => {
  return apiRequest<AudioProvider>("GET", `audio-providers/${id}`);
};

export const createAudioProvider = async (
  data: Omit<AudioProvider, "id" | "created_at" | "updated_at">
): Promise<AudioProvider> => {
  return apiRequest<AudioProvider>("POST", "audio-providers", JSON.parse(JSON.stringify(data)));
};

export const updateAudioProvider = async (
  id: string,
  data: Partial<Omit<AudioProvider, "id" | "created_at" | "updated_at">>
): Promise<AudioProvider> => {
  return apiRequest<AudioProvider>("PATCH", `audio-providers/${id}`, JSON.parse(JSON.stringify(data)));
};

export const deleteAudioProvider = async (id: string): Promise<void> => {
  await apiRequest<void>("DELETE", `audio-providers/${id}`);
};

export const getAudioProviderFormSchemas = async (): Promise<DynamicFormSchema> => {
  return apiRequest<DynamicFormSchema>("GET", "audio-providers/form-schemas");
};

export const getAudioProviderNodeSchemas = async (): Promise<AudioProviderNodeSchemas> => {
  return apiRequest<AudioProviderNodeSchemas>("GET", "audio-providers/node-schemas");
};

export const testAudioProviderConnection = async (
  provider_type: string,
  capability: string,
  connection_data: Record<string, unknown>,
  provider_id?: string,
): Promise<{ success: boolean; message: string }> => {
  const params = provider_id ? `?provider_id=${provider_id}` : "";
  return apiRequest("POST", `audio-providers/test-connection${params}`, {
    provider_type,
    capability,
    connection_data,
  });
};

import { apiRequest } from "@/config/api";
import { AppSetting } from "@/interfaces/app-setting.interface";

export const getAllAppSettings = async (): Promise<AppSetting[]> => {
  try {
    const data = await apiRequest<AppSetting[]>("GET", "app-settings/");
    if (!data) {
      console.warn("No app settings data returned from server");
      return [];
    }
    
    if (!Array.isArray(data)) {
      console.error("App settings data is not an array:", data);
      return [];
    }
    
    return data;
  } catch (error) {
    console.error("Error fetching app settings:", error);
    throw error;
  }
};

export const getAppSetting = async (id: string): Promise<AppSetting | null> => {
  try {
    const data = await apiRequest<AppSetting>("GET", `app-settings/${id}`);
    if (!data) {
      console.warn("App setting not found");
      return null;
    }
    return data;
  } catch (error) {
    console.error("Error fetching app setting:", error);
    throw error;
  }
};

export const createAppSetting = async (appSettingData: Partial<AppSetting>): Promise<AppSetting> => {
  try {
    const requestData = {
      key: appSettingData.key,
      value: appSettingData.value,
      description: appSettingData.description,
      is_active: appSettingData.is_active,
      encrypted: appSettingData.encrypted
    };
    
    const response = await apiRequest<AppSetting>("POST", "app-settings", requestData);
    if (!response) throw new Error("Failed to create app setting");
    return response;
  } catch (error) {
    console.error("Error creating app setting:", error);
    throw error;
  }
};

export const updateAppSetting = async (id: string, appSettingData: Partial<AppSetting>): Promise<AppSetting> => {
  try {
    const requestData: Record<string, unknown> = {};
    
    if (appSettingData.key !== undefined) requestData.key = appSettingData.key;
    if (appSettingData.value !== undefined) requestData.value = appSettingData.value;
    if (appSettingData.description !== undefined) requestData.description = appSettingData.description;
    if (appSettingData.is_active !== undefined) requestData.is_active = appSettingData.is_active;
    if (appSettingData.encrypted !== undefined) requestData.encrypted = appSettingData.encrypted;

    const response = await apiRequest<AppSetting>("PATCH", `app-settings/${id}`, requestData);
    if (!response) {
      throw new Error("Failed to update app setting");
    }
    return response;
  } catch (error) {
    console.error("Error occurred while updating app setting:", error);
    throw error;
  }
};

export const deleteAppSetting = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `app-settings/${id}`);
  } catch (error) {
    console.error("Error deleting app setting:", error);
    throw error;
  }
}; 
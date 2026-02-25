import { apiRequest } from "@/config/api";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { FileManagerSettings } from "./fileManager";

export const getAllAppSettings = async (): Promise<AppSetting[]> => {
  try {
    const data = await apiRequest<AppSetting[]>("GET", "app-settings/");
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

export const getAppSetting = async (id: string): Promise<AppSetting | null> => {
  try {
    const data = await apiRequest<AppSetting>("GET", `app-settings/${id}`);
    if (!data) {
      return null;
    }
    return data;
  } catch (error) {
    throw error;
  }
};

export const createAppSetting = async (appSettingData: Partial<AppSetting>): Promise<AppSetting> => {
  try {
    const requestData = {
      name: appSettingData.name,
      type: appSettingData.type,
      values: appSettingData.values,
      description: appSettingData.description,
      is_active: appSettingData.is_active,
    };

    const response = await apiRequest<AppSetting>("POST", "app-settings", requestData);
    if (!response) throw new Error("Failed to create app setting");
    return response;
  } catch (error) {
    throw error;
  }
};

export const updateAppSetting = async (id: string, appSettingData: Partial<AppSetting>): Promise<AppSetting> => {
  try {
    const requestData: Record<string, unknown> = {};

    if (appSettingData.name !== undefined) requestData.name = appSettingData.name;
    if (appSettingData.type !== undefined) requestData.type = appSettingData.type;
    if (appSettingData.values !== undefined) requestData.values = appSettingData.values;
    if (appSettingData.description !== undefined) requestData.description = appSettingData.description;
    if (appSettingData.is_active !== undefined) requestData.is_active = appSettingData.is_active;

    const response = await apiRequest<AppSetting>("PATCH", `app-settings/${id}`, requestData);
    if (!response) {
      throw new Error("Failed to update app setting");
    }
    return response;
  } catch (error) {
    throw error;
  }
};

export const deleteAppSetting = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `app-settings/${id}`);
  } catch (error) {
    throw error;
  }
};

export const getAppSettingsFormSchemas = async (): Promise<DynamicFormSchema> => {
  try {
    return await apiRequest<DynamicFormSchema>("GET", "/app-settings/form_schemas");
  } catch (error) {
    throw error;
  }
};

export const updateFileManagerSettings = async (settings: FileManagerSettings): Promise<void> => {
  const requestData = {
    name: settings.name,
    type: settings.type,
    values: settings.values,
    description: settings.description || 'File manager settings for the application',
    is_active: settings.is_active,
    id: settings.id,
  };

  if (settings.id) {
    await updateAppSetting(settings.id, requestData as unknown as Partial<AppSetting>);
  } else {
    await createAppSetting(requestData as unknown as Partial<AppSetting>);
  }
};
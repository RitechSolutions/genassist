import { apiRequest } from "@/config/api";
import { DataSource } from "@/interfaces/dataSource.interface";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getAllAppSettings } from "./appSettings";

export const getAllDataSources = async (): Promise<DataSource[]> => {
  try {
    return await apiRequest<DataSource[]>("GET", "datasources/");
  } catch (error) {
    console.error("Error fetching data sources:", error);
    throw error;
  }
};

export const getDataSource = async (id: string): Promise<DataSource | null> => {
  try {
    return await apiRequest<DataSource>("GET", `datasources/${id}`);
  } catch (error) {
    console.error("Error fetching data source:", error);
    throw error;
  }
};

export const createDataSource = async (
  dataSourceData: DataSource
): Promise<DataSource> => {
  try {
    const response = await apiRequest<DataSource>(
      "POST",
      "datasources/",
      JSON.parse(JSON.stringify(dataSourceData))
    );
    return response;
  } catch (error) {
    console.error("Error creating data source:", error);
    throw error;
  }
};

export const updateDataSource = async (
  id: string,
  dataSourceData: Partial<DataSource>
): Promise<DataSource> => {
  try {
    const response = await apiRequest<DataSource>(
      "PUT",
      `datasources/${id}`,
      JSON.parse(JSON.stringify(dataSourceData))
    );
    return response;
  } catch (error) {
    console.error("Error updating data source:", error);
    throw error;
  }
};

export const deleteDataSource = async (id: string): Promise<void> => {
  try {
    await apiRequest<void>("DELETE", `datasources/${id}`);
  } catch (error) {
    console.error("Error deleting data source:", error);
    throw error;
  }
};

export const getDataSourceFormSchemas =
  async (): Promise<DynamicFormSchema> => {
    try {
      return await apiRequest<DynamicFormSchema>(
        "GET",
        "/datasources/form_schemas"
      );
    } catch (error) {
      console.error("Error fetching data source schemas", error);
      throw error;
    }
  };

// Gmail OAuth specific functions
export const getGmailClientId = async (): Promise<string> => {
  try {
    const appSettings = await getAllAppSettings();
    const gmailSetting = appSettings.find(
      (setting) => setting.type === "Gmail" && setting.is_active === 1
    );

    if (!gmailSetting?.values?.gmail_client_id) {
      throw new Error("Gmail client ID not found in app settings");
    }

    return gmailSetting.values.gmail_client_id;
  } catch (error) {
    console.error("Error fetching Gmail client ID:", error);
    throw error;
  }
};

export const createTempGmailDataSource = async (
  name: string,
  appSettingsId: string
): Promise<string> => {
  try {
    const tempDataSource: Partial<DataSource> = {
      name,
      source_type: "gmail",
      connection_data: { app_settings_id: appSettingsId },
      is_active: 0,
      oauth_status: "pending",
    };

    const response = await createDataSource(tempDataSource as DataSource);
    return response.id!;
  } catch (error) {
    console.error("Error creating temporary Gmail datasource:", error);
    throw error;
  }
};

export const buildGmailOAuthUrl = (
  clientId: string,
  datasourceId: string
): string => {
  const baseUrl = `${window.location.protocol}//${window.location.hostname}${
    window.location.port ? `:${window.location.port}` : ""
  }`;
  const redirectUri = `${baseUrl}/gauth/callback`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    scope:
      "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/calendar.events",
    response_type: "code",
    access_type: "offline",
    prompt: "consent",
    include_granted_scopes: "true",
    state: datasourceId,
  });

  return `https://accounts.google.com/o/oauth2/auth?${params.toString()}`;
};

// Office365 scpecific functions
export const getOffice365SettingValue = async (
  setting_key_name: string
): Promise<string> => {
  try {
    const appSettings = await getAllAppSettings();
    const microsoftSetting = appSettings.find(
      (setting) => setting.type === "Microsoft" && setting.is_active === 1
    );

    if (!microsoftSetting?.values?.[setting_key_name]) {
      throw new Error(
        `Microsoft ${setting_key_name} not found in app settings`
      );
    }

    return microsoftSetting.values[setting_key_name];
  } catch (error) {
    console.error(`Error fetching Microsoft ${setting_key_name} `, error);
    throw error;
  }
};

export const createTempOffice365DataSource = async (
  name: string,
  appSettingsId: string
): Promise<string> => {
  try {
    const tempDataSource: Partial<DataSource> = {
      name,
      source_type: "o365",
      connection_data: { app_settings_id: appSettingsId },
      is_active: 0,
      oauth_status: "pending",
    };

    const response = await createDataSource(tempDataSource as DataSource);
    return response.id!;
  } catch (error) {
    console.error("Error creating temporary Office365 datasource:", error);
    throw error;
  }
};

export function buildOffice365OAuthUrl(
  clientId: string,
  tenantId: string,
  dataSourceId: string
): string {
  const redirectUri = encodeURIComponent(
    `${window.location.origin}/office365/oauth/callback`
  );
  const state = encodeURIComponent(dataSourceId);

  return (
    `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize` +
    `?client_id=${clientId}` +
    `&response_type=code` +
    `&redirect_uri=${redirectUri}` +
    `&response_mode=query` +
    `&scope=offline_access%20User.Read%20Mail.Send%20Mail.Read%20Files.Read%20Sites.Read.All%20Calendars.ReadWrite` +
    `&state=${state}` +
    `&prompt=consent`
  );
}

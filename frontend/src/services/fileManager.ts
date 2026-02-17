import { apiRequest } from "@/config/api";

export interface FileManagerSettings {
  file_manager_enabled: boolean;
  file_manager_provider: string;
  base_path?: string;
  aws_bucket_name?: string;
}

export const getFileManagerSettings = async (): Promise<FileManagerSettings | null> => {
  try {
    return await apiRequest<FileManagerSettings>("GET", "file-manager/settings");
  } catch {
    return null;
  }
};

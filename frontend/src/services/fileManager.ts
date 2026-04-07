import { apiRequest } from "@/config/api";
import type { FileManagerFileRecord } from "@/interfaces/file-manager.interface";

export interface ListFileManagerFilesParams {
  storage_provider?: string;
  limit?: number;
  offset?: number;
}

export const listFileManagerFiles = async (
  params: ListFileManagerFilesParams = {}
): Promise<FileManagerFileRecord[]> => {
  const search = new URLSearchParams();
  if (params.storage_provider != null && params.storage_provider !== "") {
    search.set("storage_provider", params.storage_provider);
  }
  if (params.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params.offset != null) {
    search.set("offset", String(params.offset));
  }
  const qs = search.toString();
  const path = qs ? `file-manager/files?${qs}` : "file-manager/files";
  const data = await apiRequest<FileManagerFileRecord[]>("GET", path);
  return data ?? [];
};

export interface FileManagerSettings {
  id?: string;
  name: string;
  description?: string;
  type: string;
  values: {
    file_manager_enabled: boolean;
    file_manager_provider: string;
    base_path: string;
    aws_bucket_name: string;
    azure_container_name: string;
  };
  is_active: number;
}

export const getFileManagerSettings = async (): Promise<FileManagerSettings | null> => {
  try {
    return await apiRequest<FileManagerSettings>("GET", "file-manager/settings");
  } catch {
    return null;
  }
};

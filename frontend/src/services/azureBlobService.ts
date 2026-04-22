// src/services/azureBlobService.ts

import { apiRequest } from "@/config/api";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------
export interface AzureConnection {
  connection_string?: string;
  container?: string;
}

export interface AzureListRequest extends AzureConnection {
  prefix?: string;
}

export interface AzureFileRequest extends AzureConnection {
  filename: string;
  prefix?: string;
  content?: string | ArrayBuffer | null;
  binary?: boolean;
  overwrite?: boolean;
}

export interface AzureUploadRequest extends AzureConnection {
  file: File;
  destination_name: string;
  prefix?: string;
}

export interface AzureMoveRequest extends AzureConnection {
  source_name: string;
  destination_name: string;
  source_prefix?: string;
  destination_prefix?: string;
}

// -----------------------------------------------------------------------------
// API Calls
// -----------------------------------------------------------------------------

export const listBlobs = async (params: AzureListRequest): Promise<string[]> => {
  const data = await apiRequest<string[]>("POST", "azure-blob-storage/list", params as unknown as Record<string, unknown>);
  return data ?? [];
};

export const blobExists = async (
  params: AzureConnection & { filename: string; prefix?: string }
): Promise<boolean> => {
  const data = await apiRequest<{ exists: boolean }>("POST", "azure-blob-storage/exists", params as unknown as Record<string, unknown>);
  return data?.exists ?? false;
};

export const uploadFile = async (payload: AzureUploadRequest): Promise<string> => {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("connection_string", payload.connection_string ?? "");
  formData.append("container", payload.container ?? "");
  formData.append("destination_name", payload.destination_name);
  if (payload.prefix != null) formData.append("prefix", payload.prefix);

  const response = await apiRequest<{ url: string }>("POST", "azure-blob-storage/upload", formData);
  if (!response?.url) throw new Error("Upload failed.");
  return response.url;
};

export const uploadContent = async (payload: AzureFileRequest): Promise<string> => {
  const response = await apiRequest<{ url: string }>(
    "POST",
    "azureblob/upload-content",
    payload as unknown as Record<string, unknown>
  );
  if (!response?.url) throw new Error("Upload-content failed.");
  return response.url;
};

export const deleteBlob = async (payload: AzureFileRequest): Promise<void> => {
  const response = await apiRequest(
    "DELETE",
    "azure-blob-storage/file",
    payload as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to delete Azure blob");
};

export const moveBlob = async (payload: AzureMoveRequest): Promise<string> => {
  const response = await apiRequest<{ url: string }>(
    "POST",
    "azure-blob-storage/move",
    payload as unknown as Record<string, unknown>
  );
  if (!response?.url) throw new Error("Move failed.");
  return response.url;
};

export const bucketExists = async (params: AzureConnection): Promise<boolean> => {
  const data = await apiRequest<{ exists: boolean }>("POST", "azure-blob-storage/bucket-exists", params as unknown as Record<string, unknown>);
  return data?.exists ?? false;
};
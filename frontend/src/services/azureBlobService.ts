// src/services/azureBlobService.ts

import { apiRequest } from "@/config/api";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------
export interface AzureConnection {
  connectionstring?: string;
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

/**
 * List blobs in a container with optional prefix.
 */
export const listBlobs = async (params: AzureListRequest): Promise<string[]> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<string[]>("GET", `azure-blob-storage/list?${query}`);
    return data ?? [];
  } catch (error) {
    throw error;
  }
};

/**
 * Check if a blob exists.
 */
export const blobExists = async (
  params: AzureConnection & { filename: string; prefix?: string }
): Promise<boolean> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<{ exists: boolean }>("GET", `azure-blob-storage/exists?${query}`);
    return data?.exists ?? false;
  } catch (error) {
    throw error;
  }
};

/**
 * Upload file (binary stream).
 */
export const uploadFile = async (payload: AzureUploadRequest): Promise<string> => {
  try {
    const response = await apiRequest<{ url: string }>("POST", "azure-blob-storage/upload", payload as unknown as Record<string, unknown>);
    if (!response?.url) throw new Error("Upload failed.");
    return response.url;
  } catch (error) {
    throw error;
  }
};

/**
 * Upload raw string or binary content.
 */
export const uploadContent = async (payload: AzureFileRequest): Promise<string> => {
  try {
    const response = await apiRequest<{ url: string }>(
      "POST",
      "azureblob/upload-content",
      payload as unknown as Record<string, unknown>
    );
    if (!response?.url) throw new Error("Upload-content failed.");
    return response.url;
  } catch (error) {
    throw error;
  }
};

/**
 * Delete a blob.
 */
export const deleteBlob = async (payload: AzureFileRequest): Promise<void> => {
  try {
    const response = await apiRequest(
      "DELETE",
      "azure-blob-storage/file",
      payload as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to delete Azure blob");
  } catch (error) {
    throw error;
  }
};

/**
 * Move a blob (copy + delete original).
 */
export const moveBlob = async (payload: AzureMoveRequest): Promise<string> => {
  try {
    const response = await apiRequest<{ url: string }>(
      "POST",
      "azure-blob-storage/move",
      payload as unknown as Record<string, unknown>
    );
    if (!response?.url) throw new Error("Move failed.");
    return response.url;
  } catch (error) {
    throw error;
  }
};

/**
 * Check if a container exists.
 */
export const bucketExists = async (
  params: AzureConnection
): Promise<boolean> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<{ exists: boolean }>("GET", `azure-blob-storage/bucket-exists?${query}`);
    return data?.exists ?? false;
  } catch (error) {
    throw error;
  }
};

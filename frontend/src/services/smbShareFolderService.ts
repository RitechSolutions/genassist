// src/services/smbShareFolderService.ts

import { apiRequest } from "@/config/api";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------
export interface SMBConnection {
  smb_host?: string;
  smb_share?: string;
  smb_user?: string;
  smb_pass?: string;
  smb_port?: number;
  use_local_fs?: boolean;
  local_root?: string;
}

export interface SMBPathRequest extends SMBConnection {
  subpath?: string;
}

export interface SMBFileRequest extends SMBPathRequest {
  filepath: string;
  content?: string | ArrayBuffer | null;
  binary?: boolean;
  overwrite?: boolean;
}

export interface SMBFolderRequest extends SMBPathRequest {
  folderpath: string;
}

// -----------------------------------------------------------------------------
// API Calls
// -----------------------------------------------------------------------------

/**
 * List files or folders in an SMB share or local directory.
 */
export const listDirectory = async (
  params: SMBPathRequest & {
    only_files?: boolean;
    only_dirs?: boolean;
    extension?: string;
    name_contains?: string;
    pattern?: string;
  }
): Promise<string[]> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<string[]>("GET", `smb-share/smb/list?${query}`);
    if (!data) return [];
    return data;
  } catch (error) {
    throw error;
  }
};

/**
 * Read a file (text or binary).
 */
export const readFile = async (
  params: Omit<SMBFileRequest, "content" | "overwrite">
): Promise<string | Blob> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<string | Blob>("GET", `smb-share/smb/read?${query}`);
    return data;
  } catch (error) {
    throw error;
  }
};

/**
 * Write or update a file.
 */
export const writeFile = async (payload: SMBFileRequest): Promise<void> => {
  try {
    const response = await apiRequest("POST", "smb-share/smb/write", payload as unknown as Record<string, unknown>);
    if (!response) {
      throw new Error("Failed to write SMB file");
    }
  } catch (error) {
    throw error;
  }
};

/**
 * Delete a file.
 */
export const deleteFile = async (payload: SMBFileRequest): Promise<void> => {
  try {
    const response = await apiRequest("DELETE", "smb-share/smb/file", payload as unknown as Record<string, unknown>);
    if (!response) {
      throw new Error("Failed to delete SMB file");
    }
  } catch (error) {
    throw error;
  }
};

/**
 * Create a folder (recursively).
 */
export const createFolder = async (payload: SMBFolderRequest): Promise<void> => {
  try {
    const response = await apiRequest("POST", "smb-share/smb/folder", payload as unknown as Record<string, unknown>);
    if (!response) {
      throw new Error("Failed to create SMB folder");
    }
  } catch (error) {
    throw error;
  }
};

/**
 * Delete a folder (recursively).
 */
export const deleteFolder = async (payload: SMBFolderRequest): Promise<void> => {
  try {
    const response = await apiRequest("DELETE", "smb-share/smb/folder", payload as unknown as Record<string, unknown>);
    if (!response) {
      throw new Error("Failed to delete SMB folder");
    }
  } catch (error) {
    throw error;
  }
};

/**
 * Check if a path exists (file or folder).
 */
export const checkPathExists = async (
  params: SMBConnection & { path: string }
): Promise<boolean> => {
  try {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)])
    ).toString();

    const data = await apiRequest<{ exists: boolean }>("GET", `smb-share/smb/exists?${query}`);
    return data?.exists ?? false;
  } catch (error) {
    throw error;
  }
};

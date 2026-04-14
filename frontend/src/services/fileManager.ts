import { api, apiRequest, getApiUrl } from "@/config/api";
import { setServerUp } from "@/config/serverStatus";
import { FileManagerFileRecord } from "@/interfaces/file-manager.interface";
import { AxiosError } from "axios";

export interface ListFileManagerFilesParams {
  storage_provider?: string;
  limit?: number;
  offset?: number;
  tag?: string;
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
  if (params.tag != null && params.tag !== "") {
    search.set("tag", params.tag);
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

/** Aligns with backend FileResponse */
export interface FileRecord {
  id: string;
  name: string;
  path: string;
  storage_path: string;
  storage_provider: string;
  original_filename?: string | null;
  size?: number | null;
  mime_type?: string | null;
  description?: string | null;
  file_extension?: string | null;
  file_metadata?: Record<string, unknown> | null;
  tags?: string[] | null;
  permissions?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  is_deleted: number;
}

export interface FileBase64Response {
  file_id: string;
  name: string;
  mime_type?: string | null;
  size?: number | null;
  content: string;
}

export interface ListFilesParams {
  storage_provider?: string;
  limit?: number;
  offset?: number;
  tag?: string;
}

export const getFileManagerSettings = async (): Promise<FileManagerSettings | null> => {
  try {
    return await apiRequest<FileManagerSettings>("GET", "file-manager/settings");
  } catch {
    return null;
  }
};

function buildUrl(path: string): Promise<string> {
  return getApiUrl().then((baseURL) => {
    const fullUrl = `${baseURL}${path.replace(/^\//, "")}`;
    return fullUrl.replace(/\/$/, "").replace(/\/([?&#])/, "$1");
  });
}

export const listFiles = async (
  params?: ListFilesParams
): Promise<FileRecord[] | null> => {
  const search = new URLSearchParams();
  if (params?.storage_provider) search.set("storage_provider", params.storage_provider);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));
  if (params?.tag != null && params.tag !== "") search.set("tag", params.tag);
  const q = search.toString();
  return apiRequest<FileRecord[]>("GET", `file-manager/files${q ? `?${q}` : ""}`);
};

export const getFileBase64 = async (fileId: string): Promise<FileBase64Response | null> => {
  return apiRequest<FileBase64Response>("GET", `file-manager/files/${fileId}/base64`);
};

export interface UploadFileRecordOptions {
  /** 0–100 while upload is in progress */
  onProgress?: (percentLoaded: number) => void;
}

function formatAxiosErrorMessage(error: AxiosError): string {
  const data = error.response?.data as unknown;
  if (data && typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const o = item as { msg?: string; loc?: unknown[] };
            const locParts = Array.isArray(o.loc)
              ? o.loc.filter((x): x is string | number => x !== undefined)
              : [];
            const loc =
              locParts.length > 0 ? `${locParts.join(".")}: ` : "";
            return `${loc}${o.msg ?? "Invalid"}`;
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
  }
  return error.message || "Upload failed";
}

export const uploadFileRecord = async (
  formData: FormData,
  options?: UploadFileRecordOptions
): Promise<FileRecord> => {
  const url = await buildUrl(`file-manager/files`);
  try {
    const response = await api.post<FileRecord>(url, formData, {
      onUploadProgress: (ev) => {
        const cb = options?.onProgress;
        if (!cb) return;
        const total = ev.total ?? 0;
        if (total > 0) {
          cb(Math.min(100, Math.round((ev.loaded * 100) / total)));
        }
      },
    });
    options?.onProgress?.(100);
    setServerUp();
    return response.data;
  } catch (error) {
    const errObj = error as AxiosError;
    throw new Error(
      errObj.response ? formatAxiosErrorMessage(errObj) : errObj.message || "Upload failed"
    );
  }
};

export const deleteFileRecord = async (fileId: string): Promise<void> => {
  const url = await buildUrl(`file-manager/files/${fileId}`);
  try {
    await api.delete(url);
    setServerUp();
  } catch (error) {
    const errObj = error as AxiosError;
    const detail =
      (errObj.response?.data as { detail?: string })?.detail ||
      errObj.message ||
      "Delete failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
};

/** Authenticated download via axios (Bearer); triggers browser save. */
export const downloadFileRecord = async (fileId: string, filename: string): Promise<void> => {
  const url = await buildUrl(`file-manager/files/${fileId}/download`);
  const response = await api.get(url, { responseType: "blob" });
  setServerUp();
  const blob = new Blob([response.data]);
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename || "download";
  a.click();
  URL.revokeObjectURL(objectUrl);
};

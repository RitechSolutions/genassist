import {
  apiRequest,
  getApiUrl,
  api,
  formatUploadOrNetworkError,
  API_UPLOAD_TIMEOUT_MS,
  API_DEFAULT_TIMEOUT_MS,
} from "@/config/api";
import {
  FILES_UPLOAD_CHUNK_SIZE,
  FILES_UPLOAD_SESSION_THRESHOLD_BYTES,
} from "@/config/uploadConstants";
import type { AxiosRequestConfig } from "axios";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";
import {
  AgentConfig,
  AgentConfigCreate,
  AgentConfigUpdate,
  AgentListItem,
} from "@/interfaces/ai-agent.interface";
import { PaginatedResponse } from "@/interfaces/common.interface";
import { KBListItem } from "@/views/KnowledgeBase/types/knowledgeBase";
import { getApiKeys, getApiKey } from "@/services/apiKeys";
import { AxiosError } from "axios";
import { UploadFileResponse } from "@/interfaces/file-manager.interface";

// Re-export types for backward compatibility
export type { AgentConfig, AgentListItem, PaginatedResponse };

// Define knowledge item interface
interface KnowledgeItem {
  id?: string;
  name: string;
  content: string;
  type: string;
  files?: string[];
  metadata?: Record<string, unknown>;
  file_type?: string;
  [key: string]: unknown;
}

// Define tool interface
interface Tool {
  id?: string;
  name: string;
  description: string;
  type: string;
  code?: string;
  parameters_schema?: Record<string, unknown>;
  [key: string]: unknown;
}

// Define parameter interface
interface ParametersSchema {
  type: string;
  properties: Record<string, unknown>;
  required?: string[];
  [key: string]: unknown;
}

// Helper function for API requests with FormData support
async function apiRequestWithFormData<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  endpoint: string,
  formData?: FormData,
  config: AxiosRequestConfig = {}
): Promise<T> {
  const baseURL = await getApiUrl();
  const fullUrl = `${baseURL}genagent/${endpoint.replace(/^\//, "")}`;

  try {
    const response = await api.request<T>({
      method,
      url: fullUrl,
      data: formData,
      timeout: config.timeout ?? API_UPLOAD_TIMEOUT_MS,
      ...config,
    });
    return response.data;
  } catch (error: unknown) {
    throw new Error(formatUploadOrNetworkError(error));
  }
}

// Agent configuration endpoints
export async function getAllAgentConfigs(): Promise<AgentConfig[]> {
  return apiRequest<AgentConfig[]>("GET", "genagent/agents/configs");
}

// Paginated list endpoint - optimized for performance
export async function getAgentConfigsList(
  page: number = 1,
  pageSize: number = 20,
  isSystem?: boolean | null
): Promise<PaginatedResponse<AgentListItem>> {

  const skip = (page - 1) * pageSize;
  const limit = pageSize;
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (isSystem !== undefined && isSystem !== null) {
    params.set("is_system", String(isSystem));
  }
  return apiRequest<PaginatedResponse<AgentListItem>>(
    "GET",
    `genagent/agents/configs/list?${params.toString()}`
  );
}

export async function getAgentConfig(id: string): Promise<AgentConfig> {
  return apiRequest<AgentConfig>("GET", `genagent/agents/configs/${id}`);
}

export async function getIntegrationConfig(agentId: string) {
  return apiRequest("GET", `genagent/agents/${agentId}/integration`);
}

export async function createAgentConfig(
  config: AgentConfigCreate
): Promise<AgentConfig> {
  return apiRequest<AgentConfig>("POST", "genagent/agents/configs", config);
}

export async function getRagFromSchema(): Promise<DynamicFormSchema> {
  return apiRequest<DynamicFormSchema>(
    "GET",
    "genagent/knowledge/form_schemas"
  );
}

/** Fields the PUT /configs/{id} endpoint accepts (AgentUpdate schema). Extra fields cause 422. */
const AGENT_UPDATE_ALLOWED_KEYS = [
  "name",
  "description",
  "is_active",
  "welcome_message",
  "welcome_image",
  "welcome_title",
  "input_disclaimer_html",
  "possible_queries",
  "thinking_phrases",
  "thinking_phrase_delay",
  "workflow_id",
  "llm_analyst_id",
  "security_settings",
] as const;

export async function updateAgentConfig(
  id: string,
  config: AgentConfigUpdate
): Promise<AgentConfig> {
  const payload = Object.fromEntries(
    AGENT_UPDATE_ALLOWED_KEYS.filter((k) => k in config).map((k) => [k, config[k]])
  );
  return apiRequest<AgentConfig>(
    "PUT",
    `genagent/agents/configs/${id}`,
    payload
  );
}

export async function deleteAgentConfig(id: string) {
  return apiRequest("DELETE", `genagent/agents/configs/${id}`);
}

// Agent image operations
export async function uploadWelcomeImage(
  agentId: string,
  imageFile: File
): Promise<{ status: string; message: string }> {
  const formData = new FormData();
  formData.append("image", imageFile);

  return apiRequestWithFormData<{ status: string; message: string }>(
    "POST",
    `agents/configs/${agentId}/welcome-image`,
    formData,
    { timeout: API_DEFAULT_TIMEOUT_MS }
  );
}

export async function getWelcomeImage(agentId: string): Promise<Blob> {
  const baseURL = await getApiUrl();
  // Bust caches so a replaced image is not shown as the previous blob.
  const fullUrl = `${baseURL}genagent/agents/configs/${agentId}/welcome-image?_=${Date.now()}`;

  try {
    const response = await api.get(fullUrl, {
      responseType: "blob",
      headers: {
        "Cache-Control": "no-cache",
        Pragma: "no-cache",
      },
    });
    return response.data;
  } catch (error: unknown) {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 404) {
      throw new Error("Welcome image not found");
    }
    throw new Error(
      `Failed to get welcome image: ${
        axiosError.response?.statusText || axiosError.message
      }`
    );
  }
}

export async function deleteWelcomeImage(
  agentId: string
): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>(
    "DELETE",
    `genagent/agents/configs/${agentId}/welcome-image`
  );
}

// Agent operations
export async function initializeAgent(id: string) {
  return apiRequest("POST", `genagent/agents/switch/${id}`);
}

export async function queryAgent(
  agentId: string,
  threadId: string,
  query: string
) {
  return apiRequest("POST", `genagent/agents/${agentId}/query/${threadId}`, {
    query,
  });
}

// Knowledge base endpoints
export async function getAllKnowledgeItems() {
  return apiRequest("GET", "genagent/knowledge/items");
}

export async function getKnowledgeItemsList(
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedResponse<KBListItem>> {
  const skip = (page - 1) * pageSize;
  return apiRequest<PaginatedResponse<KBListItem>>(
    "GET",
    `genagent/knowledge/list?skip=${skip}&limit=${pageSize}`
  );
}

export async function getKnowledgeItem(id: string) {
  return apiRequest("GET", `genagent/knowledge/items/${id}`);
}

export async function createKnowledgeItem(item: KnowledgeItem) {
  return apiRequest("POST", "genagent/knowledge/items", item);
}

export async function updateKnowledgeItem(id: string, item: KnowledgeItem) {
  return apiRequest("PUT", `genagent/knowledge/items/${id}`, item);
}

export async function deleteKnowledgeItem(id: string) {
  return apiRequest("DELETE", `genagent/knowledge/items/${id}`);
}
export async function finalizeKnowledgeItem(id: string) {
  return apiRequest("POST", `genagent/knowledge/finalize/${id}`);
}

export type UploadKnowledgeFilesOptions = {
  onProgress?: (percent: number) => void;
};

/** Never show 100% until the server response completes. */
const capClientProgress = (pct: number): number => Math.min(95, Math.max(0, pct));

// ==================== File-manager capabilities (direct S3 upload) ====================

export interface FileManagerCapabilities {
  /** True when backend has FILES_DIRECT_S3_UPLOAD_ENABLED=true and provider=s3. */
  directS3UploadEnabled: boolean;
}

/**
 * Cached, single-flight read of the file-manager settings to discover whether
 * the direct browser -> S3 presigned PUT upload flow is available. We never
 * fail loudly: if the request errors we fall back to the legacy upload paths.
 */
let _fileManagerCapsCache: Promise<FileManagerCapabilities> | null = null;
let _fileManagerCapsCachedAt = 0;
const FILE_MANAGER_CAPS_TTL_MS = 60_000; // 1 minute

export async function getFileManagerCaps(
  forceRefresh = false
): Promise<FileManagerCapabilities> {
  const now = Date.now();
  const stale = now - _fileManagerCapsCachedAt > FILE_MANAGER_CAPS_TTL_MS;
  if (!forceRefresh && _fileManagerCapsCache && !stale) {
    return _fileManagerCapsCache;
  }
  _fileManagerCapsCachedAt = now;
  _fileManagerCapsCache = (async () => {
    try {
      const baseURL = await getApiUrl();
      const url = `${baseURL}file-manager/settings`;
      const { data } = await api.get<{
        is_active?: number;
        values?: { direct_s3_upload_enabled?: boolean };
      }>(url, { timeout: API_DEFAULT_TIMEOUT_MS });
      return {
        directS3UploadEnabled: Boolean(
          data?.is_active === 1 && data?.values?.direct_s3_upload_enabled
        ),
      };
    } catch {
      return { directS3UploadEnabled: false };
    }
  })();
  return _fileManagerCapsCache;
}

interface PresignDirectUploadResponse {
  session_id: string;
  file_id: string;
  object_key: string;
  presigned_url: string;
  method: string;
  required_headers: Record<string, string>;
  expires_in: number;
}

interface FinalizeDirectUploadResponse {
  file_id: string;
  filename: string;
  original_filename: string;
  file_type?: string;
  file_url?: string;
  file_path?: string;
}

/**
 * Upload a single file directly to S3 using a presigned PUT URL.
 *
 * Flow: presign -> PUT to S3 -> finalize. On any error during PUT or finalize
 * we issue a best-effort `finalize { success: false }` so the server can
 * release the placeholder ``files`` row, then rethrow.
 *
 * Throws on failure; the dispatcher in {@link uploadFiles} catches and falls
 * back to the legacy chunked-session flow.
 */
async function uploadFileViaPresignedS3(
  file: File,
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse> {
  const baseURL = await getApiUrl();

  const presignUrl = `${baseURL}file-manager/upload-session/presign`;
  const { data: presigned } = await api.post<PresignDirectUploadResponse>(
    presignUrl,
    {
      original_filename: file.name,
      expected_size: file.size,
      content_type: file.type || "application/octet-stream",
    },
    { timeout: API_DEFAULT_TIMEOUT_MS }
  );

  const finalizeUrl = `${baseURL}file-manager/upload-session/${presigned.session_id}/finalize`;

  // Best-effort failure-finalize. Never throws.
  const reportFailure = async (errorMessage: string) => {
    try {
      await api.post(
        finalizeUrl,
        { success: false, error_message: errorMessage.slice(0, 1900) },
        { timeout: API_DEFAULT_TIMEOUT_MS }
      );
    } catch {
      // ignore; the cleanup task will eventually expire the session.
    }
  };

  // PUT directly to S3 with XHR so we get real upload progress without going
  // through the axios `api` instance (we don't want auth headers/cookies sent
  // to S3, and S3 won't tolerate unexpected CORS-preflighted headers).
  const etag = await new Promise<string | null>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(presigned.method || "PUT", presigned.presigned_url, true);
    Object.entries(presigned.required_headers || {}).forEach(([k, v]) => {
      try {
        xhr.setRequestHeader(k, v);
      } catch {
        // browsers forbid setting some headers; signed URL covers them.
      }
    });
    if (options?.onProgress) {
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        const pct = Math.round((ev.loaded * 100) / Math.max(ev.total, 1));
        options.onProgress?.(capClientProgress(pct));
      };
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const headerEtag =
          xhr.getResponseHeader("ETag") ?? xhr.getResponseHeader("etag");
        resolve(headerEtag ? headerEtag.replace(/"/g, "") : null);
      } else {
        reject(
          new Error(
            `S3 PUT failed (${xhr.status} ${xhr.statusText || ""}). ` +
              "Check bucket CORS for PUT + ETag exposure."
          )
        );
      }
    };
    xhr.onerror = () =>
      reject(
        new Error(
          "S3 PUT network error. Likely a CORS or connectivity issue."
        )
      );
    xhr.onabort = () => reject(new Error("S3 PUT aborted."));
    xhr.send(file);
  }).catch(async (err) => {
    await reportFailure(err instanceof Error ? err.message : String(err));
    throw err;
  });

  options?.onProgress?.(95);

  let finalized: FinalizeDirectUploadResponse;
  try {
    const { data } = await api.post<FinalizeDirectUploadResponse>(
      finalizeUrl,
      { success: true, etag },
      { timeout: API_UPLOAD_TIMEOUT_MS }
    );
    finalized = data;
  } catch (err) {
    // Server-side validation failure (e.g. size mismatch). The server itself
    // already cleaned up; we just rethrow so the dispatcher can fall back.
    throw new Error(formatUploadOrNetworkError(err));
  }

  options?.onProgress?.(100);
  return {
    file_id: finalized.file_id,
    filename: finalized.filename,
    original_filename: finalized.original_filename,
    file_type: finalized.file_type ?? "url",
    file_url: finalized.file_url,
    file_path: finalized.file_path,
  };
}

async function uploadFilesMultipartViaFileManager(
  files: File[],
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse[]> {
  const baseURL = await getApiUrl();
  const url = `${baseURL}file-manager/upload`;
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const fallbackTotalBytes = files.reduce((acc, f) => acc + (f.size ?? 0), 0);
  try {
    const response = await api.post<UploadFileResponse[]>(url, formData, {
      timeout: API_UPLOAD_TIMEOUT_MS,
      onUploadProgress: (ev) => {
        if (!options?.onProgress) return;
        const total = ev.total ?? fallbackTotalBytes;
        if (!total) return;
        options.onProgress(
          capClientProgress(Math.round((ev.loaded * 100) / total))
        );
      },
    });
    options?.onProgress?.(100);
    return response.data;
  } catch (error: unknown) {
    throw new Error(formatUploadOrNetworkError(error));
  }
}

interface KbUploadSessionCreateResponse {
  session_id: string;
  max_chunk_bytes: number;
}

async function uploadKnowledgeFileViaSession(
  file: File,
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse[]> {
  const baseURL = await getApiUrl();
  const createUrl = `${baseURL}file-manager/upload-session`;
  const { data: session } = await api.post<KbUploadSessionCreateResponse>(
    createUrl,
    {
      original_filename: file.name,
      expected_size: file.size,
      content_type: file.type || undefined,
    },
    { timeout: API_UPLOAD_TIMEOUT_MS }
  );
  const sessionId = session.session_id;
  const chunkSize = Math.min(FILES_UPLOAD_CHUNK_SIZE, session.max_chunk_bytes);

  let offset = 0;
  let chunkIndex = 0;
  while (offset < file.size) {
    const end = Math.min(offset + chunkSize, file.size);
    const blob = file.slice(offset, end);
    const fd = new FormData();
    fd.append("chunk", blob, "chunk.bin");
    fd.append("chunk_index", String(chunkIndex));
    fd.append("is_last", end >= file.size ? "true" : "false");
    const chunkUrl = `${baseURL}file-manager/upload-session/${sessionId}/chunk`;
    await api.post(chunkUrl, fd, {
      timeout: API_UPLOAD_TIMEOUT_MS,
      onUploadProgress: (ev) => {
        if (!options?.onProgress) return;
        const loaded = offset + (ev.loaded ?? 0);
        const pct = Math.min(100, Math.round((loaded * 100) / Math.max(file.size, 1)));
        options.onProgress(capClientProgress(pct));
      },
    });
    offset = end;
    chunkIndex += 1;
  }

  // Upload is fully sent; the server may still need time to assemble/commit.
  options?.onProgress?.(95);
  const completeUrl = `${baseURL}file-manager/upload-session/${sessionId}/complete`;
  const { data: one } = await api.post<UploadFileResponse>(completeUrl, {}, {
    timeout: API_UPLOAD_TIMEOUT_MS,
  });
  options?.onProgress?.(100);
  return [one];
}

/**
 * Upload knowledge files. Dispatcher:
 *
 * 1. If the backend exposes the direct-S3 presigned upload capability, try
 *    uploading each file straight to S3 (single PUT). On any failure (CORS,
 *    expired URL, network) we transparently fall back to the legacy
 *    chunked-session flow so a misconfigured bucket never blocks uploads.
 * 2. Otherwise, large files use the chunked session upload and small files
 *    use a single multipart POST through the file-manager API.
 */
export const uploadFiles = async (
  files: File[],
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse[]> => {
  if (files.length === 0) return [];

  const caps = await getFileManagerCaps();
  if (caps.directS3UploadEnabled) {
    const results: UploadFileResponse[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const wrapProgress = (p: number) => {
        if (!options?.onProgress) return;
        const totalPct = ((i + p / 100) / files.length) * 100;
        options.onProgress(Math.min(100, Math.round(totalPct)));
      };
      try {
        const one = await uploadFileViaPresignedS3(f, { onProgress: wrapProgress });
        results.push(one);
        continue;
      } catch (err) {
        // Direct path failed (CORS, expired signature, server flag flipped
        // off, etc). Fall back to the legacy session upload so we still
        // succeed; log a warning for diagnostics.
        // eslint-disable-next-line no-console
        console.warn(
          "[file-manager] direct S3 upload failed, falling back to chunked session:",
          err
        );
      }
      const part = await uploadKnowledgeFileViaSession(f, { onProgress: wrapProgress });
      results.push(...part);
    }
    return results;
  }

  const allSmall = files.every(
    (f) => f.size <= FILES_UPLOAD_SESSION_THRESHOLD_BYTES
  );
  if (allSmall) {
    return uploadFilesMultipartViaFileManager(files, options);
  }
  const results: UploadFileResponse[] = [];
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const wrapProgress = (p: number) => {
      if (!options?.onProgress) return;
      const totalPct = ((i + p / 100) / files.length) * 100;
      options.onProgress(Math.min(100, Math.round(totalPct)));
    };
    if (f.size > FILES_UPLOAD_SESSION_THRESHOLD_BYTES) {
      const part = await uploadKnowledgeFileViaSession(f, { onProgress: wrapProgress });
      results.push(...part);
    } else {
      const part = await uploadFilesMultipartViaFileManager([f], { onProgress: wrapProgress });
      results.push(...part);
    }
  }
  return results;
};

// Endpoint to trigger KB synchronization execution MANUALLY
export const executeKnowledgeBaseSyncronizationManually = async (kbId: string) => {
  return apiRequest(
    "GET",
    `genagent/knowledge/kb-batch-tasks-execution?kb_id=${kbId}`
  );
};

// Tools endpoints
export async function getAllTools() {
  return apiRequest("GET", "genagent/tools");
}

export async function getTool(id: string) {
  return apiRequest("GET", `genagent/tools/${id}`);
}

export async function createTool(tool: Tool) {
  return apiRequest("POST", "genagent/tools", tool);
}

export async function updateTool(id: string, tool: Tool) {
  return apiRequest("PUT", `genagent/tools/${id}`, tool);
}

export async function deleteTool(id: string) {
  return apiRequest("DELETE", `genagent/tools/${id}`);
}

export async function testPythonCode(
  code: string,
  params: Record<string, unknown>
) {
  return apiRequest("POST", "genagent/tools/python/test", {
    code,
    params,
  });
}

export async function generatePythonTemplate(
  parametersSchema: ParametersSchema
) {
  return apiRequest("POST", "genagent/tools/python/generate-template", {
    parameters_schema: parametersSchema,
  });
}

export async function generatePythonTemplateFromTool(toolId: string) {
  return apiRequest(
    "GET",
    `genagent/tools/python/template-from-tool/${toolId}`
  );
}

export async function testPythonCodeWithSchema(
  code: string,
  params: Record<string, unknown>,
  parametersSchema: ParametersSchema
) {
  return apiRequest("POST", "genagent/tools/python/test-with-schema", {
    code,
    params,
    parameters_schema: parametersSchema,
  });
}

export async function getAgentIntegrationKey(agentId: string): Promise<string> {
  const config = await getAgentConfig(agentId);
  const userId = config.user_id;
  if (!userId) {
    throw new Error("Agent has no user_id");
  }

  const keys = await getApiKeys(userId);
  // Key associated with the agent
  let active = keys.find((k) => k.is_active === 1 && k.agent_id === agentId);

  if (!active) {
    active = keys.find((k) => k.is_active === 1);
  }

  if (!active) {
    throw new Error("No active API key found for this agent");
  }

  const fullKey = await getApiKey(active.id);
  if (!fullKey?.key_val) {
    throw new Error("API key value missing");
  }

  return fullKey.key_val;
}

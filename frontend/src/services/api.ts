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
  pageSize: number = 20
): Promise<PaginatedResponse<AgentListItem>> {

  const skip = (page - 1) * pageSize;
  const limit = pageSize;
  return apiRequest<PaginatedResponse<AgentListItem>>(
    "GET",
    `genagent/agents/configs/list?skip=${skip}&limit=${limit}`
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

async function uploadFilesMultipartViaFileManager(
  files: File[],
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse[]> {
  const baseURL = await getApiUrl();
  const url = `${baseURL}file-manager/upload`;
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  try {
    const response = await api.post<UploadFileResponse[]>(url, formData, {
      timeout: API_UPLOAD_TIMEOUT_MS,
      onUploadProgress: (ev) => {
        if (!ev.total || !options?.onProgress) return;
        options.onProgress(
          capClientProgress(Math.round((ev.loaded * 100) / ev.total))
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
 * Upload knowledge files. Uses chunked session upload for files larger than
 * FILES_UPLOAD_SESSION_THRESHOLD_BYTES; otherwise one multipart request.
 */
export const uploadFiles = async (
  files: File[],
  options?: UploadKnowledgeFilesOptions
): Promise<UploadFileResponse[]> => {
  if (files.length === 0) return [];
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

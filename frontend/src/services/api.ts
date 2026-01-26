import { apiRequest, getApiUrl, api } from "@/config/api";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { getApiKeys, getApiKey } from "@/services/apiKeys";
import { AxiosError } from "axios";

export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  is_active?: boolean;
  welcome_message?: string;
  welcome_title?: string;
  thinking_phrase_delay?: number;
  possible_queries?: string[];
  thinking_phrases?: string[];
  workflow_id: string;
  user_id: string;
  // Security settings (nested object)
  security_settings?: {
    id?: string;
    agent_id?: string;
    token_based_auth?: boolean;
    token_expiration_minutes?: number | null;
    cors_allowed_origins?: string | null;
    rate_limit_conversation_start_per_minute?: number | null;
    rate_limit_conversation_start_per_hour?: number | null;
    rate_limit_conversation_update_per_minute?: number | null;
    rate_limit_conversation_update_per_hour?: number | null;
    recaptcha_enabled?: boolean | null;
    recaptcha_project_id?: string | null;
    recaptcha_site_key?: string | null;
    recaptcha_min_score?: string | null;
    gcp_svc_account?: string | null;
  } | null;
  [key: string]: unknown;
}
type AgentConfigCreate = Omit<AgentConfig, "id" | "user_id" | "workflow_id">;

type AgentConfigUpdate = Partial<Omit<AgentConfig, "id" | "user_id">>;

// Define knowledge item interface
interface KnowledgeItem {
  id?: string;
  name: string;
  content: string;
  type: string;
  files?: string[];
  metadata?: Record<string, unknown>;
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
  config: Record<string, unknown> = {}
): Promise<T> {
  const baseURL = await getApiUrl();
  const fullUrl = `${baseURL}genagent/${endpoint.replace(/^\//, "")}`;

  try {
    const response = await api.request<T>({
      method,
      url: fullUrl,
      data: formData,
      headers: {
        "Content-Type": "multipart/form-data",
      },
      ...config,
    });
    return response.data;
  } catch (error: unknown) {
    const axiosError = error as AxiosError;
    const errorData = (axiosError.response?.data as { detail?: string }) || {};
    throw new Error(
      errorData.detail ||
        `API error: ${axiosError.response?.status || axiosError.message}`
    );
  }
}

// Agent configuration endpoints
export async function getAllAgentConfigs(): Promise<AgentConfig[]> {
  return apiRequest<AgentConfig[]>("GET", "genagent/agents/configs");
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

export async function updateAgentConfig(
  id: string,
  config: AgentConfigUpdate
): Promise<AgentConfig> {
  return apiRequest<AgentConfig>(
    "PUT",
    `genagent/agents/configs/${id}`,
    config
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
    formData
  );
}

export async function getWelcomeImage(agentId: string): Promise<Blob> {
  const baseURL = await getApiUrl();
  const fullUrl = `${baseURL}genagent/agents/configs/${agentId}/welcome-image`;

  try {
    const response = await api.get(fullUrl, {
      responseType: "blob",
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

export const uploadFiles = async (files: File[]) => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  return apiRequestWithFormData("POST", "knowledge/upload", formData);
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

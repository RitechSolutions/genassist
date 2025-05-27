import { getApiUrl } from "@/config/api";
import { LLMProvidersConfig } from "@/interfaces/llmProvider.interface";
import { getApiKeys } from "@/services/apiKeys";
interface RequestOptions extends RequestInit {
    headers?: Record<string, string>;
  }
  
  interface AgentConfig {
    id?: string;
    name: string;
    description: string;
    llm_provider_id: string;
    system_prompt: string;
    knowledge_base_ids?: string[];
    tool_ids?: string[];
    settings?: Record<string, unknown>;
    is_active?: boolean;
    email?: string;
    welcome_message?: string;
    possible_queries?: string[];
    [key: string]: unknown;
  }
  
  // Define knowledge item interface
  interface KnowledgeItem {
    id?: string;
    name: string;
    content: string;
    type: string;
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
  
  // const API_BASE_URL = "http://localhost:8000/api";
  const baseUrl = await getApiUrl();
  const API_BASE_URL = `${baseUrl}genagent`;
  
  // Helper function for API requests
  async function fetchWithErrorHandling(
    url: string,
    options: RequestOptions = {}
  ) {
    const token = localStorage.getItem("access_token");
    const tokenType = localStorage.getItem("token_type");
    
    const isForm = options.body instanceof FormData;

    const headers: Record<string, string> = {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    };

    if (token && tokenType) {
      headers["Authorization"] = `${tokenType} ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status}`);
    }

    return response.json();
  }
  
  // Agent configuration endpoints
  export async function getAllAgentConfigs() {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/configs`);
  }
  
  export async function getAgentConfig(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/configs/${id}`);
  }

  export async function getIntegrationConfig(agentId: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/${agentId}/integration`);
  }
  
  export async function createAgentConfig(config: AgentConfig) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/configs`, {
      method: "POST",
      body: JSON.stringify(config),
    });
  }
  export async function getSupportedModels():Promise<LLMProvidersConfig> {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/supported_models`);
  }
  
  export async function updateAgentConfig(id: string, config: AgentConfig) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/configs/${id}`, {
      method: "PUT",
      body: JSON.stringify(config),
    });
  }
  
  export async function deleteAgentConfig(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/configs/${id}`, {
      method: "DELETE",
    });
  }
  
  // Agent operations
  export async function initializeAgent(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/agents/switch/${id}`, {
      method: "POST",
    });
  }
  
  export async function queryAgent(
    agentId: string,
    threadId: string,
    query: string
  ) {
    return fetchWithErrorHandling(
      `${API_BASE_URL}/agents/${agentId}/query/${threadId}`,
      {
        method: "POST",
        body: JSON.stringify({ query }),
      }
    );
  }
  
  // Knowledge base endpoints
  export async function getAllKnowledgeItems() {
    return fetchWithErrorHandling(`${API_BASE_URL}/knowledge/items`);
  }
  
  export async function getKnowledgeItem(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/knowledge/items/${id}`);
  }
  
  export async function createKnowledgeItem(item: KnowledgeItem) {
    return fetchWithErrorHandling(`${API_BASE_URL}/knowledge/items`, {
      method: "POST",
      body: JSON.stringify(item),
    });
  }
  
  export async function updateKnowledgeItem(id: string, item: KnowledgeItem) {
    return fetchWithErrorHandling(`${API_BASE_URL}/knowledge/items/${id}`, {
      method: "PUT",
      body: JSON.stringify(item),
    });
  }
  
  export async function deleteKnowledgeItem(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/knowledge/items/${id}`, {
      method: "DELETE",
    });
  }
  
  export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const result = await fetchWithErrorHandling(
      `${API_BASE_URL}/knowledge/upload`,
      {
        method: "POST",
        body: formData,
      }
    );
    return result;
  } catch (err) {
    console.error("📁 uploadFile failed:", err);
    throw err;
  }
};

  
  export async function getAllTools() {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools`);
  }
  
  export async function getTool(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools/${id}`);
  }
  
  export async function createTool(tool: Tool) {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools`, {
      method: "POST",
      body: JSON.stringify(tool),
    });
  }
  
  export async function updateTool(id: string, tool: Tool) {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools/${id}`, {
      method: "PUT",
      body: JSON.stringify(tool),
    });
  }
  
  export async function deleteTool(id: string) {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools/${id}`, {
      method: "DELETE",
    });
  }
  
  export async function testPythonCode(
    code: string,
    params: Record<string, unknown>
  ) {
    return fetchWithErrorHandling(`${API_BASE_URL}/tools/python/test`, {
      method: "POST",
      body: JSON.stringify({
        code,
        params,
      }),
    });
  }
  
  export async function generatePythonTemplate(
    parametersSchema: ParametersSchema
  ) {
    return fetchWithErrorHandling(
      `${API_BASE_URL}/tools/python/generate-template`,
      {
        method: "POST",
        body: JSON.stringify({
          parameters_schema: parametersSchema,
        }),
      }
    );
  }
  
  export async function generatePythonTemplateFromTool(toolId: string) {
    return fetchWithErrorHandling(
      `${API_BASE_URL}/tools/python/template-from-tool/${toolId}`
    );
  }
  
  export async function testPythonCodeWithSchema(
    code: string,
    params: Record<string, unknown>,
    parametersSchema: ParametersSchema
  ) {
    return fetchWithErrorHandling(
      `${API_BASE_URL}/tools/python/test-with-schema`,
      {
        method: "POST",
        body: JSON.stringify({
          code,
          params,
          parameters_schema: parametersSchema,
        }),
      }
    );
  }

  export async function getAgentIntegrationKey(agentId: string): Promise<string> {
  const config = await getAgentConfig(agentId);
  const userId = (config as any).user_id as string;
  if (!userId) {
    throw new Error("Agent has no user_id");
  }

  const keys = await getApiKeys(userId);
  const active = keys.find((k) => k.is_active === 1);
  if (!active) {
    throw new Error("No active API key found for this agent");
  }
  
  // Uncomment this when api key is available
  // const fullKey = await getApiKey(active.id);
  // if (!fullKey.key) throw new Error("API key value missing");

  // TEMP: hardcoded key for manual testing,
  return "agent123"; // Replace with the fullKey.key when available
}
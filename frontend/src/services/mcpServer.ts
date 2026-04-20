import { apiRequest } from "@/config/api";
import {
  MCPServer,
  MCPServerCreatePayload,
  MCPServerUpdatePayload,
} from "@/interfaces/mcp-server.interface";

const BASE = "mcp-servers";

function normalizeMCPServer(s: MCPServer): MCPServer {
  const raw = s as MCPServer & { auth_values?: MCPServer["auth_values"] };
  return {
    ...raw,
    auth_values: raw.auth_values ?? {},
    auth_type: raw.auth_type === "oauth2" ? "oauth2" : "api_key",
  };
}

export const getAllMCPServers = async (): Promise<MCPServer[]> => {
  try {
    const data = await apiRequest<MCPServer[]>("GET", `${BASE}`);
    if (!data || !Array.isArray(data)) {
      return [];
    }
    return data.map(normalizeMCPServer);
  } catch (error) {
    throw error;
  }
};

export const getMCPServer = async (id: string): Promise<MCPServer | null> => {
  try {
    const data = await apiRequest<MCPServer>("GET", `${BASE}/${id}`);
    return data ? normalizeMCPServer(data) : null;
  } catch (error) {
    throw error;
  }
};

export const createMCPServer = async (
  serverData: MCPServerCreatePayload
): Promise<MCPServer> => {
  try {
    const response = await apiRequest<MCPServer>(
      "POST",
      `${BASE}`,
      serverData as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to create MCP server");
    return normalizeMCPServer(response);
  } catch (error) {
    throw error;
  }
};

export const updateMCPServer = async (
  id: string,
  serverData: MCPServerUpdatePayload
): Promise<MCPServer> => {
  try {
    const response = await apiRequest<MCPServer>(
      "PUT",
      `${BASE}/${id}`,
      serverData as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to update MCP server");
    return normalizeMCPServer(response);
  } catch (error) {
    throw error;
  }
};

export const deleteMCPServer = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `${BASE}/${id}`);
  } catch (error) {
    throw error;
  }
};


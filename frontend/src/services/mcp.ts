import { apiRequest } from "@/config/api";
import { MCPTool, MCPConnectionType, HTTPConnectionConfig } from "@/views/AIAgents/Workflows/types/nodes";

const BASE = "mcp";

/**
 * Discover available tools from an MCP server
 * 
 * For HTTP/SSE connections, this calls the backend endpoint which connects to the MCP server
 * and returns the list of available tools.
 * 
 * @param connectionType - The type of connection ("http" | "sse" | "stdio")
 * @param connectionConfig - Connection configuration object
 * @returns Promise resolving to an array of available MCP tools
 * @throws Error if the request fails or server is unreachable
 */
export const discoverMCPTools = async (
  connectionType: MCPConnectionType,
  connectionConfig: HTTPConnectionConfig
): Promise<MCPTool[]> => {
  try {
    // For STDIO connections, tool discovery happens automatically during workflow execution
    if (connectionType === "stdio") {
      throw new Error("Tool discovery is not available for STDIO connections. Tools will be discovered automatically when the workflow runs.");
    }

    // Use the backend endpoint that handles MCP server connection
    // The backend will use the connection config to connect to the MCP server
    const response = await apiRequest<{ tools: MCPTool[] }>(
      "POST",
      `${BASE}/discover-tools`,
      {
        connection_type: connectionType,
        connection_config: connectionConfig,
      }
    );
    return response?.tools || [];
  } catch (error) {
    console.error("Error discovering MCP tools:", error);
    throw error;
  }
};



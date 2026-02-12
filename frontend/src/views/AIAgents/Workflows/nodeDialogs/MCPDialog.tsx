import React, { useState, useEffect } from "react";
import { MCPNodeData, MCPTool, MCPConnectionType, STDIOConnectionConfig, HTTPConnectionConfig } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { Textarea } from "@/components/textarea";
import { Save, RefreshCw } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import toast from "react-hot-toast";
import { discoverMCPTools } from "@/services/mcp";

type MCPDialogProps = BaseNodeDialogProps<MCPNodeData, MCPNodeData>;

export const MCPDialog: React.FC<MCPDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  // Initialize with default values if not provided
  const getInitialConnectionType = (): MCPConnectionType => {
    return data.connectionType || "http";
  };

  const getInitialConnectionConfig = (): STDIOConnectionConfig | HTTPConnectionConfig => {
    if (data.connectionConfig) {
      return data.connectionConfig;
    }
    
    const type = getInitialConnectionType();
    if (type === "stdio") {
      return { command: "" };
    } else {
      return { url: "" };
    }
  };

  const [name, setName] = useState(data.name || "");
  const [description, setDescription] = useState(data.description || "");
  const [connectionType, setConnectionType] = useState<MCPConnectionType>(
    getInitialConnectionType()
  );
  
  const [connectionConfig, setConnectionConfig] = useState<STDIOConnectionConfig | HTTPConnectionConfig>(
    getInitialConnectionConfig()
  );

  const [availableTools, setAvailableTools] = useState<MCPTool[]>(
    data.availableTools || []
  );
  const [whitelistedTools, setWhitelistedTools] = useState<string[]>(
    data.whitelistedTools || []
  );
  const [isLoadingTools, setIsLoadingTools] = useState(false);

  // STDIO-specific state
  const [stdioCommand, setStdioCommand] = useState(
    connectionType === "stdio" && "command" in connectionConfig
      ? connectionConfig.command
      : ""
  );
  const [stdioArgs, setStdioArgs] = useState(
    connectionType === "stdio" && "args" in connectionConfig
      ? connectionConfig.args?.join(", ") || ""
      : ""
  );
  const [stdioEnv, setStdioEnv] = useState(
    connectionType === "stdio" && "env" in connectionConfig
      ? JSON.stringify(connectionConfig.env || {}, null, 2)
      : "{}"
  );

  // HTTP/SSE-specific state
  const [httpUrl, setHttpUrl] = useState(
    (connectionType === "http" || connectionType === "sse") && "url" in connectionConfig
      ? connectionConfig.url
      : ""
  );
  const [httpApiKey, setHttpApiKey] = useState(
    (connectionType === "http" || connectionType === "sse") && "api_key" in connectionConfig
      ? connectionConfig.api_key || ""
      : ""
  );
  const [httpTimeout, setHttpTimeout] = useState(
    (connectionType === "http" || connectionType === "sse") && "timeout" in connectionConfig
      ? connectionConfig.timeout?.toString() || "30"
      : "30"
  );
  const [httpHeaders, setHttpHeaders] = useState(
    (connectionType === "http" || connectionType === "sse") && "headers" in connectionConfig
      ? JSON.stringify(connectionConfig.headers || {}, null, 2)
      : "{}"
  );

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setDescription(data.description || "");
      setConnectionType(data.connectionType || "http");
      
      if (data.connectionConfig) {
        setConnectionConfig(data.connectionConfig);
        
        if ("command" in data.connectionConfig) {
          setStdioCommand(data.connectionConfig.command || "");
          setStdioArgs(data.connectionConfig.args?.join(", ") || "");
          setStdioEnv(JSON.stringify(data.connectionConfig.env || {}, null, 2));
        } else {
          setHttpUrl(data.connectionConfig.url || "");
          setHttpApiKey(data.connectionConfig.api_key || "");
          setHttpTimeout(data.connectionConfig.timeout?.toString() || "30");
          setHttpHeaders(JSON.stringify(data.connectionConfig.headers || {}, null, 2));
        }
      } else {
        // Initialize with defaults
        const type = data.connectionType || "http";
        if (type === "stdio") {
          setStdioCommand("");
          setStdioArgs("");
          setStdioEnv("{}");
        } else {
          setHttpUrl("");
          setHttpApiKey("");
          setHttpTimeout("30");
          setHttpHeaders("{}");
        }
      }
      
      setAvailableTools(data.availableTools || []);
      setWhitelistedTools(data.whitelistedTools || []);
    }
  }, [isOpen, data]);

  // Update connection config when connection type changes
  useEffect(() => {
    if (connectionType === "stdio") {
      setConnectionConfig({
        command: stdioCommand,
        args: stdioArgs ? stdioArgs.split(",").map((arg) => arg.trim()).filter(Boolean) : undefined,
        env: parseJsonSafely(stdioEnv, {}),
      });
    } else {
      setConnectionConfig({
        url: httpUrl,
        api_key: httpApiKey || undefined,
        timeout: httpTimeout ? parseInt(httpTimeout, 10) : undefined,
        headers: parseJsonSafely(httpHeaders, {}),
      });
    }
  }, [connectionType, stdioCommand, stdioArgs, stdioEnv, httpUrl, httpApiKey, httpTimeout, httpHeaders]);

  const parseJsonSafely = (jsonString: string, defaultValue: Record<string, string>): Record<string, string> => {
    try {
      const parsed = JSON.parse(jsonString);
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        // Convert all values to strings
        const result: Record<string, string> = {};
        for (const [key, value] of Object.entries(parsed)) {
          result[key] = String(value);
        }
        return result;
      }
      return defaultValue;
    } catch {
      return defaultValue;
    }
  };

  const handleSave = () => {
    // Validate based on connection type
    if (connectionType === "stdio") {
      if (!stdioCommand.trim()) {
        toast.error("Command is required for STDIO connections");
        return;
      }
    } else {
      if (!httpUrl.trim()) {
        toast.error("Server URL is required for HTTP/SSE connections");
        return;
      }
    }

    // Validate JSON fields
    if (connectionType === "stdio") {
      try {
        JSON.parse(stdioEnv);
      } catch {
        toast.error("Invalid JSON in environment variables");
        return;
      }
    } else {
      try {
        JSON.parse(httpHeaders);
      } catch {
        toast.error("Invalid JSON in headers");
        return;
      }
    }

    onUpdate({
      ...data,
      name,
      description,
      connectionType,
      connectionConfig,
      availableTools,
      whitelistedTools,
    });
    onClose();
  };

  const handleDiscoverTools = async () => {
    if (connectionType === "stdio") {
      toast.error("Tool discovery is not available for STDIO connections. Tools will be discovered automatically when the workflow runs.");
      return;
    }

    if (!httpUrl.trim()) {
      toast.error("Please enter a server URL first");
      return;
    }

    setIsLoadingTools(true);
    try {
      // Use the new connection config format
      const tools = await discoverMCPTools(
        connectionType,
        connectionConfig as HTTPConnectionConfig
      );
      setAvailableTools(tools);
      
      // Keep only whitelisted tools that still exist in the new list
      setWhitelistedTools((prev) =>
        prev.filter((toolName) =>
          tools.some((tool) => tool.name === toolName)
        )
      );

      if (tools.length === 0) {
        toast.success("No tools found on the MCP server");
      } else {
        toast.success(`Discovered ${tools.length} tool(s)`);
      }
    } catch (error) {
      toast.error("Failed to fetch tools from MCP server");
      console.error("Error discovering tools:", error);
    } finally {
      setIsLoadingTools(false);
    }
  };

  const toggleTool = (toolName: string) => {
    setWhitelistedTools((prev) =>
      prev.includes(toolName)
        ? prev.filter((name) => name !== toolName)
        : [...prev, toolName]
    );
  };

  const selectAllTools = () => {
    setWhitelistedTools(availableTools.map((tool) => tool.name));
  };

  const deselectAllTools = () => {
    setWhitelistedTools([]);
  };

  return (
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        description,
        connectionType,
        connectionConfig,
        availableTools,
        whitelistedTools,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Node Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="MCP Server"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Input
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="MCP server tool connector"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="connectionType">Connection Type</Label>
        <Select
          value={connectionType}
          onValueChange={(value) => setConnectionType(value as MCPConnectionType)}
        >
          <SelectTrigger id="connectionType">
            <SelectValue placeholder="Select connection type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="http">HTTP</SelectItem>
            <SelectItem value="sse">SSE (Server-Sent Events)</SelectItem>
            <SelectItem value="stdio">STDIO (Local Process)</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-gray-500 break-words">
          {connectionType === "stdio" && "Run a local MCP server as a child process"}
          {connectionType === "sse" && "Connect to a remote MCP server using Server-Sent Events"}
          {connectionType === "http" && "Connect to a remote MCP server using standard HTTP"}
        </div>
      </div>

      {connectionType === "stdio" ? (
        <>
          <div className="space-y-2">
            <Label htmlFor="stdioCommand">Command *</Label>
            <DraggableInput
              id="stdioCommand"
              value={stdioCommand}
              onChange={(e) => setStdioCommand(e.target.value)}
              placeholder="python"
              className="w-full"
            />
            <div className="text-xs text-gray-500 break-words">
              Command to run the MCP server (e.g., "python", "node", "/usr/bin/mcp-server")
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="stdioArgs">Arguments (comma-separated)</Label>
            <DraggableInput
              id="stdioArgs"
              value={stdioArgs}
              onChange={(e) => setStdioArgs(e.target.value)}
              placeholder="-m, mcp_server"
              className="w-full"
            />
            <div className="text-xs text-gray-500 break-words">
              Command arguments separated by commas (e.g., "-m", "mcp_server")
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="stdioEnv">Environment Variables (JSON)</Label>
            <Textarea
              id="stdioEnv"
              value={stdioEnv}
              onChange={(e) => setStdioEnv(e.target.value)}
              placeholder='{"API_KEY": "secret"}'
              className="w-full font-mono text-sm"
              rows={4}
            />
            <div className="text-xs text-gray-500 break-words">
              Environment variables as JSON object (e.g., {"{"}"API_KEY": "secret"{"}"})
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="httpUrl">MCP Server URL *</Label>
            <DraggableInput
              id="httpUrl"
              value={httpUrl}
              onChange={(e) => setHttpUrl(e.target.value)}
              placeholder="https://mcp-server.example.com"
              className="w-full"
            />
            <div className="text-xs text-gray-500 break-words">
              {connectionType === "sse" 
                ? "Enter the SSE endpoint URL of your MCP server"
                : "Enter the URL of your MCP server"}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="httpApiKey">API Key (Optional)</Label>
            <DraggableInput
              id="httpApiKey"
              type="password"
              value={httpApiKey}
              onChange={(e) => setHttpApiKey(e.target.value)}
              placeholder="Enter API key if required"
              className="w-full"
            />
            <div className="text-xs text-gray-500 break-words">
              API key for authenticating with the MCP server
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="httpTimeout">Timeout (seconds)</Label>
            <Input
              id="httpTimeout"
              type="number"
              value={httpTimeout}
              onChange={(e) => setHttpTimeout(e.target.value)}
              placeholder="30"
              className="w-full"
              min="1"
            />
            <div className="text-xs text-gray-500 break-words">
              Request timeout in seconds (default: 30)
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="httpHeaders">Custom Headers (JSON)</Label>
            <Textarea
              id="httpHeaders"
              value={httpHeaders}
              onChange={(e) => setHttpHeaders(e.target.value)}
              placeholder='{"X-Custom-Header": "value"}'
              className="w-full font-mono text-sm"
              rows={4}
            />
            <div className="text-xs text-gray-500 break-words">
              Custom HTTP headers as JSON object (e.g., {"{"}"X-Custom-Header": "value"{"}"})
            </div>
          </div>
        </>
      )}

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Available Tools</Label>
          <Button
            size="sm"
            variant="outline"
            onClick={handleDiscoverTools}
            disabled={isLoadingTools || connectionType === "stdio" || !httpUrl.trim()}
          >
            <RefreshCw
              className={`h-3 w-3 mr-1 ${isLoadingTools ? "animate-spin" : ""}`}
            />
            Discover Tools
          </Button>
        </div>
        {connectionType === "stdio" && (
          <div className="text-xs text-gray-500 mb-2">
            Tools will be discovered automatically when the workflow runs for STDIO connections.
          </div>
        )}
        {availableTools.length > 0 && (
          <div className="flex gap-2 mb-2">
            <Button
              size="sm"
              variant="outline"
              onClick={selectAllTools}
              className="text-xs"
            >
              Select All
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={deselectAllTools}
              className="text-xs"
            >
              Deselect All
            </Button>
          </div>
        )}
        <ScrollArea className="h-60 border rounded-md p-2 w-full">
          {availableTools.length === 0 ? (
            <div className="text-sm text-gray-500 text-center py-4">
              {connectionType === "stdio" 
                ? "Tools will be discovered automatically when the workflow runs"
                : connectionType === "sse"
                ? "Enter a server URL and click 'Discover Tools' to fetch available tools"
                : httpUrl.trim()
                ? "Click 'Discover Tools' to fetch available tools from the MCP server"
                : "Enter a server URL and click 'Discover Tools' to fetch available tools"}
            </div>
          ) : (
            <div className="space-y-2">
              {availableTools.map((tool) => (
                <div
                  key={tool.name}
                  className="flex items-start space-x-2 w-full p-2 hover:bg-gray-50 rounded"
                >
                  <Checkbox
                    id={`tool-${tool.name}`}
                    checked={whitelistedTools.includes(tool.name)}
                    onCheckedChange={() => toggleTool(tool.name)}
                    className="mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <Label
                      htmlFor={`tool-${tool.name}`}
                      className="text-sm font-medium cursor-pointer block"
                    >
                      {tool.name}
                    </Label>
                    {tool.description && (
                      <p className="text-xs text-gray-500 mt-1 break-words">
                        {tool.description}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
        <p className="text-xs text-gray-500 break-words">
          Select which tools to expose to your agent. Only whitelisted tools will
          be available for the agent to use.
        </p>
      </div>
    </NodeConfigPanel>
  );
};

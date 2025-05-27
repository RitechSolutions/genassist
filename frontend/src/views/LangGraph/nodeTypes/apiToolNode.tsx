import React, { useState, useEffect } from "react";
import { Handle, Position, NodeProps, useReactFlow } from "reactflow";
import { APIToolNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Save, Globe, Play, Plus, X } from "lucide-react";
import { TestDialog, TestInputField } from "../components/TestDialog";
import { HandleTooltip } from "../components/HandleTooltip";
import {
  getAllDynamicVariables,
  replaceVariablesWithInputs,
} from "../utils/apiHelpers";
import { createSimpleSchema } from "../types/schemas";
import { getNodeColors } from "../utils/nodeColors";

// HTTP methods
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"] as const;
type HttpMethod = (typeof HTTP_METHODS)[number];

const APIToolNode: React.FC<NodeProps<APIToolNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const { getEdges } = useReactFlow();
  const colors = getNodeColors('apiToolNode');
  const [name, setName] = useState(data.name || "API Tool");
  const [description, setDescription] = useState(
    data.description || "Makes API calls to external services"
  );
  const [endpoint, setEndpoint] = useState(data.endpoint || "https://");
  const [method, setMethod] = useState<HttpMethod>(
    (data.method as HttpMethod) || "GET"
  );
  const [headers, setHeaders] = useState<Record<string, string>>(
    data.headers || {}
  );
  const [parameters, setParameters] = useState<Record<string, string>>(
    data.parameters || {}
  );
  const [requestBody, setRequestBody] = useState(data.requestBody || "");
  const [response, setResponse] = useState(data.response || "");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);

  // Save configuration whenever relevant state changes
  useEffect(() => {
    saveConfiguration();
  }, [name, description, endpoint, parameters, requestBody, method, headers]);

  // Add new header
  const addHeader = () => {
    setHeaders({ ...headers, "": "" });
  };

  // Update header key/value
  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders = { ...headers };
    if (oldKey !== newKey) {
      delete newHeaders[oldKey];
    }
    newHeaders[newKey] = value;
    setHeaders(newHeaders);
  };

  // Remove header
  const removeHeader = (key: string) => {
    const newHeaders = { ...headers };
    delete newHeaders[key];
    setHeaders(newHeaders);
  };

  // Add new parameter
  const addParameter = () => {
    setParameters({ ...parameters, "": "" });
  };

  // Update parameter key/value
  const updateParameter = (oldKey: string, newKey: string, value: string) => {
    const newParameters = { ...parameters };
    if (oldKey !== newKey) {
      delete newParameters[oldKey];
    }
    newParameters[newKey] = value;
    setParameters(newParameters);
  };

  // Remove parameter
  const removeParameter = (key: string) => {
    const newParameters = { ...parameters };
    delete newParameters[key];
    setParameters(newParameters);
  };

  // Generate input fields based on API configuration
  const generateInputFields = () => {
    const variables = getAllDynamicVariables(endpoint, headers, parameters, requestBody);
    console.log(variables);
    return Array.from(variables).map((varName) => ({
      id: varName,
      label: `Parameter: ${varName}`,
      type: "text" as const,
      required: true,
      placeholder: `Value for ${varName}`,
    }));
  };

  // Generate expected input structure for tooltip
  const generateInputStructure = () => {
    const variables = getAllDynamicVariables(endpoint, headers, parameters, requestBody);

    if (variables.size === 0) {
      return "No input required";
    }

    return `Expected input: {\n  ${Array.from(variables)
      .map((v) => `"${v}": string`)
      .join(",\n  ")}\n}`;
  };

  // Generate expected output structure for tooltip
  const generateOutputStructure = () => {
    return `Expected output: {\n  "status": number,\n  "data": any,\n  "headers": Record<string, string>\n}`;
  };

  // Update the node data whenever form values change
  const saveConfiguration = () => {
    const variables = getAllDynamicVariables(endpoint, headers, parameters, requestBody);

    // Create input schema from variables
    const inputSchemaFields: Record<
      string,
      { type: "string"; required: boolean }
    > = {};
    variables.forEach((variable) => {
      inputSchemaFields[variable] = { type: "string", required: true };
    });

    // Create output schema
    const outputSchema = createSimpleSchema({
      status: { type: "number", required: true },
      data: { type: "any", required: true },
      headers: { type: "object", required: true },
    });
    if (data.updateNodeData) {
      const updatedData: Partial<APIToolNodeData> = {
        ...data,
        name,
        description,
        endpoint,
        method,
        headers,
        parameters,
        requestBody,
        response,
        inputSchema:
          Object.keys(inputSchemaFields).length > 0
            ? createSimpleSchema(inputSchemaFields)
            : undefined,
        outputSchema,
        label: name, // Ensure label is always set to match name
      };

      data.updateNodeData(id, updatedData);
    }
  };

  // Execute API call with test input
  const executeAPICall = async (inputs: Record<string, string>) => {
    try {
      setIsLoading(true);
      setError(null);

      // Prepare URL with parameters
      let url = replaceVariablesWithInputs(endpoint, inputs);
      const queryParams = new URLSearchParams();

      // Add parameters
      for (const [key, value] of Object.entries(parameters)) {
        if (key && value) {
          // Replace any @variable placeholders in parameter values
          const paramValue = replaceVariablesWithInputs(value, inputs);
          queryParams.append(key, paramValue);
        }
      }

      // Add query parameters for GET requests
      if (method === "GET" && queryParams.toString()) {
        url = `${url}${url.includes("?") ? "&" : "?"}${queryParams.toString()}`;
      }

      // Prepare request headers
      const requestHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        ...headers,
      };

      // Prepare request body
      let body = undefined;
      if (method !== "GET") {
        if (requestBody) {
          // Replace any @variable placeholders in the body with test input
          const processedBody = replaceVariablesWithInputs(requestBody, inputs);
          body = processedBody;
        } else if (
          method === "POST" ||
          method === "PUT" ||
          method === "PATCH"
        ) {
          // Use parameters as body for non-GET requests if no body is provided
          body = JSON.stringify(parameters);
        }
      }

      // Execute the request
      const response = await fetch(url, {
        method,
        headers: requestHeaders,
        body: body ? JSON.stringify(JSON.parse(body)) : undefined,
      });

      if (!response.ok) {
        throw new Error(`API call failed with status: ${response.status}`);
      }

      const responseData = await response.text();

      // Try to parse and format JSON responses
      try {
        const jsonData = JSON.parse(responseData);
        const formattedJson = JSON.stringify(jsonData, null, 2);
        setResponse(formattedJson);
      } catch (e) {
        // Not JSON, use as plain text
        setResponse(responseData);
      }
    } catch (err) {
      console.error("API call failed:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(errorMessage);
      setResponse(`Error: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <div className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}>
          <div className="flex items-center">
            <Globe className={`h-4 w-4 text-white mr-2`} />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`text-sm font-medium h-6 py-0 bg-transparent border-transparent ${colors.focus} text-white ${colors.placeholder}`}
              maxLength={40}
            />
          </div>
          <div className="flex space-x-1">
            <Button
              size="icon"
              variant="ghost"
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Test API call"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Save configuration"
              onClick={saveConfiguration}
            >
              <Save className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Node content */}
        <div className="p-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this API tool does"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="endpoint">Endpoint URL</Label>
              <Input
                id="endpoint"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="https://api.example.com/data"
              />
              <div className="text-xs text-gray-500">
                Use @variable to define dynamic parameters
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="method">HTTP Method</Label>
              <Select
                value={method}
                onValueChange={(value) =>
                  setMethod(value as (typeof HTTP_METHODS)[number])
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select HTTP method" />
                </SelectTrigger>
                <SelectContent>
                  {HTTP_METHODS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label>Headers</Label>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs"
                  onClick={addHeader}
                >
                  <Plus className="h-3 w-3 mr-1" /> Add Header
                </Button>
              </div>

              <div className="space-y-2 max-h-[150px] overflow-y-auto">
                {Object.entries(headers).map(([key, value], idx) => (
                  <div
                    key={`header-${idx}`}
                    className="flex items-center gap-2"
                  >
                    <Input
                      placeholder="Header name"
                      value={key}
                      onChange={(e) => updateHeader(key, e.target.value, value)}
                      className="flex-1 text-xs"
                    />
                    <Input
                      placeholder="Value"
                      value={value}
                      onChange={(e) => updateHeader(key, key, e.target.value)}
                      className="flex-1 text-xs"
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      onClick={() => removeHeader(key)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label>Parameters</Label>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs"
                  onClick={addParameter}
                >
                  <Plus className="h-3 w-3 mr-1" /> Add Parameter
                </Button>
              </div>

              <div className="space-y-2 max-h-[150px] overflow-y-auto">
                {Object.entries(parameters).map(([key, value], idx) => (
                  <div key={`param-${idx}`} className="flex items-center gap-2">
                    <Input
                      placeholder="Parameter name"
                      value={key}
                      onChange={(e) =>
                        updateParameter(key, e.target.value, value)
                      }
                      className="flex-1 text-xs"
                    />
                    <Input
                      placeholder="Value"
                      value={value}
                      onChange={(e) =>
                        updateParameter(key, key, e.target.value)
                      }
                      className="flex-1 text-xs"
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      onClick={() => removeParameter(key)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {(method === "POST" || method === "PUT" || method === "PATCH") && (
              <div className="space-y-2">
                <Label htmlFor="requestBody">Request Body (JSON)</Label>
                <Textarea
                  id="requestBody"
                  value={requestBody}
                  onChange={(e) => setRequestBody(e.target.value)}
                  placeholder='{"key": "value"}'
                  className="font-mono text-xs h-24"
                />
                <div className="text-xs text-gray-500">
                  Use @variable to define dynamic parameters
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input handle */}
        {/* <HandleTooltip
          nodeId={id}
          id="input"
          type="target"
          position={Position.Left}
          text={generateInputStructure()}
          style={{ background: '#4f46e5' }}
        /> */}

        {/* Output handle */}
        {/* <HandleTooltip
          nodeId={id}
          id="output"
          type="source"
          position={Position.Right}
          compatibility='tools'
          style={{ top: '20%' }}
        /> */}

        {data.handlers
          ?.filter((handler) => handler.type === "source")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
        {data.handlers
          ?.filter((handler) => handler.type === "target")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${name}`}
        description="Fill in the required values for testing the API configuration"
        inputFields={generateInputFields()}
        onRun={executeAPICall}
        output={response}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default APIToolNode;

import React, { useEffect, useState } from "react";
import { APIToolNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Plus, X, Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import toast from "react-hot-toast";

// HTTP methods
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"] as const;
type HttpMethod = (typeof HTTP_METHODS)[number];

export const APIToolDialog: React.FC<
  BaseNodeDialogProps<APIToolNodeData, APIToolNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [endpoint, setEndpoint] = useState(data.endpoint || "");
  const [method, setMethod] = useState<HttpMethod>(
    (data.method as HttpMethod) || "GET"
  );
  const [headers, setHeaders] = useState<Record<string, string>>(
    data.headers || {}
  );
  const [parameters, setParameters] = useState<Record<string, string>>(
    data.parameters || {}
  );
  const [requestBody, setRequestBody] = useState(
    typeof data.requestBody === "string"
      ? data.requestBody
      : JSON.stringify(data.requestBody) || ""
  );
  useEffect(() => {
    setName(data.name || "");
    setEndpoint(data.endpoint || "");
    setMethod((data.method as HttpMethod) || "GET");
    setHeaders(data.headers || {});
    setParameters(data.parameters || {});
    setRequestBody(
      typeof data.requestBody === "string"
        ? data.requestBody
        : JSON.stringify(data.requestBody) || ""
    );
  }, [isOpen]);

  // Handle save
  const handleSave = () => {
    let requestBodyParsed = requestBody;
    try {
      if (requestBody && requestBody.trim() !== "") {
        requestBodyParsed = JSON.parse(requestBody);
      }
    } catch (error) {
      toast.error("Invalid JSON in request body.");

      return;
    }

    onUpdate({
      ...data,
      name,
      endpoint,
      method,
      headers,
      parameters,
      requestBody: requestBodyParsed,
    });
    onClose();
  };

  // Add new header
  const addHeader = () => {
    setHeaders({ ...headers, "": "" });
  };

  // Update header key/value
  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders: Record<string, string> = {};

    // Iterate through existing headers to maintain order
    for (const [key, val] of Object.entries(headers)) {
      if (key === oldKey) {
        // Update the header with new key and value
        newHeaders[newKey] = value;
      } else {
        // Keep other headers as they were
        newHeaders[key] = val;
      }
    }

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
    const newParameters: Record<string, string> = {};

    // Iterate through existing parameters to maintain order
    for (const [key, val] of Object.entries(parameters)) {
      if (key === oldKey) {
        // Update the parameter with new key and value
        newParameters[newKey] = value;
      } else {
        // Keep other parameters as they were
        newParameters[key] = val;
      }
    }

    setParameters(newParameters);
  };

  // Remove parameter
  const removeParameter = (key: string) => {
    const newParameters = { ...parameters };
    delete newParameters[key];
    setParameters(newParameters);
  };

  return (
    <NodeConfigPanel
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
        endpoint,
        method,
        headers,
        parameters,
        requestBody,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="API Tool"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="endpoint">Endpoint URL</Label>
        <DraggableInput
          id="endpoint"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="https://api.example.com/data"
          className="break-all w-full"
        />
        <div className="text-xs text-gray-500 break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="method">HTTP Method </Label>
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

        <div className="space-y-2">
          {Object.entries(headers).map(([key, value], idx) => (
            <div
              key={`header-${idx}`}
              className="flex items-center gap-2 w-full"
            >
              <DraggableInput
                placeholder="Header name"
                value={key}
                onChange={(e) => updateHeader(key, e.target.value, value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <DraggableInput
                placeholder="Value"
                value={value}
                onChange={(e) => updateHeader(key, key, e.target.value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6 flex-shrink-0"
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

        <div className="space-y-2">
          {Object.entries(parameters).map(([key, value], idx) => (
            <div
              key={`param-${idx}`}
              className="flex items-center gap-2 w-full"
            >
              <DraggableInput
                placeholder="Parameter name"
                value={key}
                onChange={(e) => updateParameter(key, e.target.value, value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <DraggableInput
                placeholder="Value"
                value={value}
                onChange={(e) => updateParameter(key, key, e.target.value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6 flex-shrink-0"
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
          <DraggableTextArea
            id="requestBody"
            value={requestBody}
            onChange={(e) => setRequestBody(e.target.value)}
            placeholder='{"key": "value"}'
            className="font-mono text-xs h-24 resize-none w-full"
          />
          <div className="text-xs text-gray-500 break-words">
            Use {"{{field}}"} to define dynamic parameters
          </div>
        </div>
      )}
    </NodeConfigPanel>
  );
};

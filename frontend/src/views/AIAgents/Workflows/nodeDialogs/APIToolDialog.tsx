import React from "react";
import { APIToolNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
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
import { useNodeDialogState } from "./useNodeDialogState";

// HTTP methods
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"] as const;
type HttpMethod = (typeof HTTP_METHODS)[number];

export const APIToolDialog: React.FC<
  BaseNodeDialogProps<APIToolNodeData, APIToolNodeData>
> = (props) => {
  const { onClose, onUpdate, data } = props;

  const { values, setField, merged } = useNodeDialogState(props, () => ({
    name: data.name || "",
    endpoint: data.endpoint || "",
    method: (data.method as HttpMethod) || "GET",
    headers: (data.headers || {}) as Record<string, string>,
    parameters: (data.parameters || {}) as Record<string, string>,
    requestBody:
      typeof data.requestBody === "string"
        ? data.requestBody
        : JSON.stringify(data.requestBody) || "",
  }));

  // Handle save — keeps the request-body JSON validation/abort that the hook's generic
  // handleSave cannot express. `merged` feeds NodeConfigPanel's data prop with the RAW
  // body string (dirty-detection unchanged); only the persisted payload is parsed.
  const handleSave = () => {
    let requestBodyParsed = values.requestBody;
    try {
      if (values.requestBody && values.requestBody.trim() !== "") {
        requestBodyParsed = JSON.parse(values.requestBody);
      }
    } catch (error) {
      toast.error("Invalid JSON in request body.");

      return;
    }

    onUpdate({
      ...merged,
      requestBody: requestBodyParsed,
    });
    onClose();
  };

  // Add new header
  const addHeader = () => {
    setField("headers", { ...values.headers, "": "" });
  };

  // Update header key/value
  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders: Record<string, string> = {};

    // Iterate through existing headers to maintain order
    for (const [key, val] of Object.entries(values.headers)) {
      if (key === oldKey) {
        // Update the header with new key and value
        newHeaders[newKey] = value;
      } else {
        // Keep other headers as they were
        newHeaders[key] = val;
      }
    }

    setField("headers", newHeaders);
  };

  // Remove header
  const removeHeader = (key: string) => {
    const newHeaders = { ...values.headers };
    delete newHeaders[key];
    setField("headers", newHeaders);
  };

  // Add new parameter
  const addParameter = () => {
    setField("parameters", { ...values.parameters, "": "" });
  };

  // Update parameter key/value
  const updateParameter = (oldKey: string, newKey: string, value: string) => {
    const newParameters: Record<string, string> = {};

    // Iterate through existing parameters to maintain order
    for (const [key, val] of Object.entries(values.parameters)) {
      if (key === oldKey) {
        // Update the parameter with new key and value
        newParameters[newKey] = value;
      } else {
        // Keep other parameters as they were
        newParameters[key] = val;
      }
    }

    setField("parameters", newParameters);
  };

  // Remove parameter
  const removeParameter = (key: string) => {
    const newParameters = { ...values.parameters };
    delete newParameters[key];
    setField("parameters", newParameters);
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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="API Tool"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="endpoint">Endpoint URL</Label>
        <DraggableInput
          id="endpoint"
          value={values.endpoint}
          onChange={(e) => setField("endpoint", e.target.value)}
          placeholder="https://api.example.com/data"
          className="break-all w-full"
        />
        <div className="text-xs text-muted-foreground break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="method">HTTP Method </Label>
        <Select
          value={values.method}
          onValueChange={(value) =>
            setField("method", value as (typeof HTTP_METHODS)[number])
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
          {Object.entries(values.headers).map(([key, value], idx) => (
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
          {Object.entries(values.parameters).map(([key, value], idx) => (
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

      {(values.method === "POST" ||
        values.method === "PUT" ||
        values.method === "PATCH") && (
        <div className="space-y-2">
          <Label htmlFor="requestBody">Request Body (JSON)</Label>
          <DraggableTextArea
            id="requestBody"
            value={values.requestBody}
            onChange={(e) => setField("requestBody", e.target.value)}
            placeholder='{"key": "value"}'
            size="code"
            className="w-full"
          />
          <div className="text-xs text-muted-foreground break-words">
            Use {"{{field}}"} to define dynamic parameters
          </div>
        </div>
      )}
    </NodeConfigPanel>
  );
};

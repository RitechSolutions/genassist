import React, { useEffect, useState } from "react";
import { ExternalAgentNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Plus, X, Save, ChevronDown, ChevronUp } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { DraggableAceEditor } from "../components/custom/DraggableAceEditor";
import { RichInput } from "@/components/richInput";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH"] as const;
const AUTH_TYPES = ["none", "bearer", "api_key", "basic"] as const;
type AuthType = (typeof AUTH_TYPES)[number];

export const ExternalAgentDialog: React.FC<
  BaseNodeDialogProps<ExternalAgentNodeData, ExternalAgentNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [endpoint, setEndpoint] = useState(data.endpoint || "");
  const [method, setMethod] = useState(data.method || "POST");
  const [headers, setHeaders] = useState<Record<string, string>>(data.headers || {});
  const [requestBody, setRequestBody] = useState(data.requestBody || "");
  const [authType, setAuthType] = useState<AuthType>((data.authType as AuthType) || "none");
  const [authToken, setAuthToken] = useState(data.authToken || "");
  const [authHeader, setAuthHeader] = useState(data.authHeader || "Authorization");
  const [authUsername, setAuthUsername] = useState(data.authUsername || "");
  const [authPassword, setAuthPassword] = useState(data.authPassword || "");
  const [messageField, setMessageField] = useState(data.messageField || "message");
  const [stepsField, setStepsField] = useState(data.stepsField || "steps");
  const [timeout, setTimeout] = useState<number>(data.timeout ?? 30);
  const [mappingScript, setMappingScript] = useState(data.mappingScript || "");
  const [showAdvanced, setShowAdvanced] = useState(!!data.mappingScript);

  useEffect(() => {
    setName(data.name || "");
    setEndpoint(data.endpoint || "");
    setMethod(data.method || "POST");
    setHeaders(data.headers || {});
    setRequestBody(data.requestBody || "");
    setAuthType((data.authType as AuthType) || "none");
    setAuthToken(data.authToken || "");
    setAuthHeader(data.authHeader || "Authorization");
    setAuthUsername(data.authUsername || "");
    setAuthPassword(data.authPassword || "");
    setMessageField(data.messageField || "message");
    setStepsField(data.stepsField || "steps");
    setTimeout(data.timeout ?? 30);
    setMappingScript(data.mappingScript || "");
    setShowAdvanced(!!data.mappingScript);
  }, [isOpen]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      endpoint,
      method,
      headers,
      requestBody,
      authType,
      authToken,
      authHeader,
      authUsername,
      authPassword,
      timeout,
      messageField,
      stepsField,
      mappingScript,
    });
    onClose();
  };

  const addHeader = () => setHeaders({ ...headers, "": "" });

  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const updated: Record<string, string> = {};
    for (const [k, v] of Object.entries(headers)) {
      updated[k === oldKey ? newKey : k] = k === oldKey ? value : v;
    }
    setHeaders(updated);
  };

  const removeHeader = (key: string) => {
    const updated = { ...headers };
    delete updated[key];
    setHeaders(updated);
  };

  const previewData = {
    ...data,
    name,
    endpoint,
    method,
    headers,
    requestBody,
    authType,
    authToken,
    authHeader,
    authUsername,
    authPassword,
    messageField,
    stepsField,
    mappingScript,
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
      data={previewData}
    >
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="External Agent"
          className="w-full"
        />
      </div>

      {/* Endpoint + Method */}
      <div className="space-y-2">
        <Label htmlFor="endpoint">Endpoint URL</Label>
        <DraggableInput
          id="endpoint"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="https://api.example.com/agent"
          className="w-full"
        />
        <div className="text-xs text-gray-500">Use {"{{field}}"} for dynamic values</div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="method">HTTP Method</Label>
        <Select value={method} onValueChange={setMethod}>
          <SelectTrigger>
            <SelectValue placeholder="Select method" />
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
        <Label htmlFor="timeout">Timeout (seconds)</Label>
        <RichInput
          id="timeout"
          type="number"
          value={String(timeout)}
          onChange={(e) => setTimeout(Math.max(1, parseInt(e.target.value) || 30))}
          placeholder="30"
          className="w-full"
        />
      </div>

      {/* Authentication */}
      <div className="space-y-2">
        <Label>Authentication</Label>
        <Select value={authType} onValueChange={(v) => setAuthType(v as AuthType)}>
          <SelectTrigger>
            <SelectValue placeholder="Auth type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">None</SelectItem>
            <SelectItem value="bearer">Bearer Token</SelectItem>
            <SelectItem value="api_key">API Key Header</SelectItem>
            <SelectItem value="basic">Basic Auth</SelectItem>
          </SelectContent>
        </Select>

        {(authType === "bearer" || authType === "api_key") && (
          <div className="space-y-2 pl-2 border-l-2 border-gray-200">
            {authType === "api_key" && (
              <div className="space-y-1">
                <Label className="text-xs">Header Name</Label>
                <DraggableInput
                  value={authHeader}
                  onChange={(e) => setAuthHeader(e.target.value)}
                  placeholder="Authorization"
                  className="text-xs w-full"
                />
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-xs">{authType === "bearer" ? "Token" : "API Key Value"}</Label>
              <DraggableInput
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                placeholder={authType === "bearer" ? "{{session.token}}" : "{{session.apiKey}}"}
                className="text-xs w-full"
              />
            </div>
          </div>
        )}

        {authType === "basic" && (
          <div className="space-y-2 pl-2 border-l-2 border-gray-200">
            <div className="space-y-1">
              <Label className="text-xs">Username</Label>
              <DraggableInput
                value={authUsername}
                onChange={(e) => setAuthUsername(e.target.value)}
                placeholder="{{session.username}}"
                className="text-xs w-full"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Password</Label>
              <DraggableInput
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="{{session.password}}"
                className="text-xs w-full"
              />
            </div>
          </div>
        )}
      </div>

      {/* Headers */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Headers</Label>
          <Button size="sm" variant="outline" className="h-6 text-xs" onClick={addHeader}>
            <Plus className="h-3 w-3 mr-1" /> Add Header
          </Button>
        </div>
        <div className="space-y-2">
          {Object.entries(headers).map(([key, value], idx) => (
            <div key={`header-${idx}`} className="flex items-center gap-2 w-full">
              <DraggableInput
                placeholder="Header name"
                value={key}
                onChange={(e) => updateHeader(key, e.target.value, value)}
                className="flex-1 text-xs min-w-0"
              />
              <DraggableInput
                placeholder="Value"
                value={value}
                onChange={(e) => updateHeader(key, key, e.target.value)}
                className="flex-1 text-xs min-w-0"
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

      {/* Request body */}
      {(method === "POST" || method === "PUT" || method === "PATCH") && (
        <div className="space-y-2">
          <Label htmlFor="requestBody">Request Body (JSON)</Label>
          <DraggableTextArea
            id="requestBody"
            value={requestBody}
            onChange={(e) => setRequestBody(e.target.value)}
            placeholder='{"message": "{{source.message}}"}'
            className="font-mono text-xs h-24 resize-none w-full"
          />
          <div className="text-xs text-gray-500">Use {"{{field}}"} for dynamic values</div>
        </div>
      )}

      {/* Response mapping */}
      <div className="space-y-2">
        <Label>Response Mapping</Label>
        <div className="text-xs text-gray-500 mb-1">
          Point to where the message lives in the JSON response using dot-notation (e.g. <code>output.text</code>). Use the Python script below if you need to combine fields, add fallback logic, or transform the data.
        </div>
        <div className={`space-y-2 ${mappingScript ? "opacity-40 pointer-events-none" : ""}`}>
          <div className="space-y-1">
            <Label className="text-xs">Message field path</Label>
            <DraggableInput
              value={messageField}
              onChange={(e) => setMessageField(e.target.value)}
              placeholder="message"
              className="text-xs w-full"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Steps field path (optional)</Label>
            <DraggableInput
              value={stepsField}
              onChange={(e) => setStepsField(e.target.value)}
              placeholder="steps"
              className="text-xs w-full"
            />
          </div>
        </div>
        {mappingScript && (
          <p className="text-xs text-amber-600">Field paths are ignored — Python script is active.</p>
        )}
      </div>

      {/* Advanced: Python mapping script */}
      <div className="space-y-2">
        <button
          type="button"
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Advanced: Python mapping script
        </button>
        {showAdvanced && (
          <div className="space-y-2">
            <div className="text-xs text-gray-500 bg-gray-50 rounded p-2 space-y-2">
              <div>
                <p className="font-semibold text-gray-700">When to use this</p>
                <p className="mt-0.5">Use this instead of the field paths above when you need to <strong>combine multiple fields</strong>, add <strong>fallback/conditional logic</strong>, or <strong>transform</strong> the response (e.g. extract items from a list). For simple cases where the message is at a known path, the field inputs above are enough.</p>
              </div>
              <div>
                <p className="font-semibold text-gray-700">How to write it</p>
                <ul className="mt-0.5 list-disc list-inside space-y-0.5">
                  <li><code className="bg-gray-100 px-1 rounded">params["response"]</code> — the full parsed JSON body from the API</li>
                  <li>Assign <code className="bg-gray-100 px-1 rounded">result</code> — a dict with <code className="bg-gray-100 px-1 rounded">"message"</code> <span className="text-gray-400">(str, required)</span> and <code className="bg-gray-100 px-1 rounded">"steps"</code> <span className="text-gray-400">(list, optional)</span></li>
                  <li>When set, this script overrides the field-path mapping above</li>
                </ul>
              </div>
              <div>
                <p className="font-semibold text-gray-700">Example</p>
                <pre className="mt-1 bg-gray-100 rounded p-2 font-mono text-xs overflow-x-auto">{`response = params["response"]
result = {
    "message": response.get("answer") or response["fallback_text"],
    "steps": [s["description"] for s in response.get("reasoning_steps", [])],
}`}</pre>
              </div>
            </div>
            <DraggableAceEditor
              id="mapping-script-editor"
              name="mapping-script-editor"
              mode="python"
              theme="twilight"
              value={mappingScript}
              onChange={setMappingScript}
              width="100%"
              height="100%"
            />
            <div className="text-xs text-gray-500">
              When set, this script overrides the field path mapping above.
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
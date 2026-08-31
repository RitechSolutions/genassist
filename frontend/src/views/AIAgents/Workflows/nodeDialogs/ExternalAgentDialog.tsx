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
import { useNodeDialogState } from "./useNodeDialogState";

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH"] as const;
const AUTH_TYPES = ["none", "bearer", "api_key", "basic"] as const;
type AuthType = (typeof AUTH_TYPES)[number];

export const ExternalAgentDialog: React.FC<
  BaseNodeDialogProps<ExternalAgentNodeData, ExternalAgentNodeData>
> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      endpoint: data.endpoint || "",
      method: data.method || "POST",
      headers: data.headers || {},
      requestBody: data.requestBody || "",
      authType: (data.authType as AuthType) || "none",
      authToken: data.authToken || "",
      authHeader: data.authHeader || "Authorization",
      authUsername: data.authUsername || "",
      authPassword: data.authPassword || "",
      messageField: data.messageField || "message",
      stepsField: data.stepsField || "steps",
      timeout: data.timeout ?? 30,
      mappingScript: data.mappingScript || "",
    })
  );

  const [showAdvanced, setShowAdvanced] = useState(!!data.mappingScript);

  useEffect(() => {
    setShowAdvanced(!!data.mappingScript);
  }, [isOpen, data]);

  const addHeader = () => setField("headers", { ...values.headers, "": "" });

  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const updated: Record<string, string> = {};
    for (const [k, v] of Object.entries(values.headers)) {
      updated[k === oldKey ? newKey : k] = k === oldKey ? value : v;
    }
    setField("headers", updated);
  };

  const removeHeader = (key: string) => {
    const updated = { ...values.headers };
    delete updated[key];
    setField("headers", updated);
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
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="External Agent"
          className="w-full"
        />
      </div>

      {/* Endpoint + Method */}
      <div className="space-y-2">
        <Label htmlFor="endpoint">Endpoint URL</Label>
        <DraggableInput
          id="endpoint"
          value={values.endpoint}
          onChange={(e) => setField("endpoint", e.target.value)}
          placeholder="https://api.example.com/agent"
          className="w-full"
        />
        <div className="text-xs text-muted-foreground">Use {"{{field}}"} for dynamic values</div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="method">HTTP Method</Label>
        <Select value={values.method} onValueChange={(v) => setField("method", v)}>
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
          value={String(values.timeout)}
          onChange={(e) => setField("timeout", Math.max(1, parseInt(e.target.value) || 30))}
          placeholder="30"
          className="w-full"
        />
      </div>

      {/* Authentication */}
      <div className="space-y-2">
        <Label>Authentication</Label>
        <Select value={values.authType} onValueChange={(v) => setField("authType", v as AuthType)}>
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

        {(values.authType === "bearer" || values.authType === "api_key") && (
          <div className="space-y-2 pl-2 border-l-2 border-border">
            {values.authType === "api_key" && (
              <div className="space-y-1">
                <Label className="text-xs">Header Name</Label>
                <DraggableInput
                  value={values.authHeader}
                  onChange={(e) => setField("authHeader", e.target.value)}
                  placeholder="Authorization"
                  className="text-xs w-full"
                />
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-xs">{values.authType === "bearer" ? "Token" : "API Key Value"}</Label>
              <DraggableInput
                value={values.authToken}
                onChange={(e) => setField("authToken", e.target.value)}
                placeholder={values.authType === "bearer" ? "{{session.token}}" : "{{session.apiKey}}"}
                className="text-xs w-full"
              />
            </div>
          </div>
        )}

        {values.authType === "basic" && (
          <div className="space-y-2 pl-2 border-l-2 border-border">
            <div className="space-y-1">
              <Label className="text-xs">Username</Label>
              <DraggableInput
                value={values.authUsername}
                onChange={(e) => setField("authUsername", e.target.value)}
                placeholder="{{session.username}}"
                className="text-xs w-full"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Password</Label>
              <DraggableInput
                value={values.authPassword}
                onChange={(e) => setField("authPassword", e.target.value)}
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
          {Object.entries(values.headers).map(([key, value], idx) => (
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
      {(values.method === "POST" || values.method === "PUT" || values.method === "PATCH") && (
        <div className="space-y-2">
          <Label htmlFor="requestBody">Request Body (JSON)</Label>
          <DraggableTextArea
            id="requestBody"
            value={values.requestBody}
            onChange={(e) => setField("requestBody", e.target.value)}
            placeholder='{"message": "{{source.message}}"}'
            size="code"
            className="w-full"
          />
          <div className="text-xs text-muted-foreground">Use {"{{field}}"} for dynamic values</div>
        </div>
      )}

      {/* Response mapping */}
      <div className="space-y-2">
        <Label>Response Mapping</Label>
        <div className="text-xs text-muted-foreground mb-1">
          Point to where the message lives in the JSON response using dot-notation (e.g. <code>output.text</code>). Use the Python script below if you need to combine fields, add fallback logic, or transform the data.
        </div>
        <div className={`space-y-2 ${values.mappingScript ? "opacity-40 pointer-events-none" : ""}`}>
          <div className="space-y-1">
            <Label className="text-xs">Message field path</Label>
            <DraggableInput
              value={values.messageField}
              onChange={(e) => setField("messageField", e.target.value)}
              placeholder="message"
              className="text-xs w-full"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Steps field path (optional)</Label>
            <DraggableInput
              value={values.stepsField}
              onChange={(e) => setField("stepsField", e.target.value)}
              placeholder="steps"
              className="text-xs w-full"
            />
          </div>
        </div>
        {values.mappingScript && (
          <p className="text-xs text-amber-600 dark:text-amber-400">Field paths are ignored — Python script is active.</p>
        )}
      </div>

      {/* Advanced: Python mapping script */}
      <div className="space-y-2">
        <button
          type="button"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-muted-foreground"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Advanced: Python mapping script
        </button>
        {showAdvanced && (
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground bg-muted rounded p-2 space-y-2">
              <div>
                <p className="font-semibold text-muted-foreground">When to use this</p>
                <p className="mt-0.5">Use this instead of the field paths above when you need to <strong>combine multiple fields</strong>, add <strong>fallback/conditional logic</strong>, or <strong>transform</strong> the response (e.g. extract items from a list). For simple cases where the message is at a known path, the field inputs above are enough.</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">How to write it</p>
                <ul className="mt-0.5 list-disc list-inside space-y-0.5">
                  <li><code className="bg-muted px-1 rounded">params["response"]</code> — the full parsed JSON body from the API</li>
                  <li>Assign <code className="bg-muted px-1 rounded">result</code> — a dict with <code className="bg-muted px-1 rounded">"message"</code> <span className="text-muted-foreground">(str, required)</span> and <code className="bg-muted px-1 rounded">"steps"</code> <span className="text-muted-foreground">(list, optional)</span></li>
                  <li>When set, this script overrides the field-path mapping above</li>
                </ul>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Example</p>
                <pre className="mt-1 bg-muted rounded p-2 font-mono text-xs overflow-x-auto">{`response = params["response"]
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
              value={values.mappingScript}
              onChange={(value) => setField("mappingScript", value)}
              width="100%"
              height="100%"
            />
            <div className="text-xs text-muted-foreground">
              When set, this script overrides the field path mapping above.
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
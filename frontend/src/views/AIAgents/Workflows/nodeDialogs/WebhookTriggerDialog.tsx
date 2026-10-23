import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Copy,
  Eye,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Send,
  Trash2,
} from "lucide-react";
import toast from "react-hot-toast";

import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Label } from "@/components/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Tooltip } from "@/components/tooltip";
import { RichInput } from "@/components/richInput";
import { SecretInput } from "@/components/SecretInput";
import JsonViewer, { JsonValue } from "@/components/JsonViewer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  getWorkflowTriggerRun,
  getWorkflowTriggerRuns,
  provisionWorkflowTrigger,
  revealWorkflowTriggerSecret,
  rotateWorkflowTriggerSecret,
  testWorkflowTrigger,
  updateWorkflowTrigger,
} from "@/services/workflowTriggers";
import {
  WorkflowTrigger,
  WorkflowTriggerAuthMode,
  WorkflowTriggerMethod,
  WorkflowTriggerRunStatus,
} from "@/interfaces/workflow-trigger.interface";

import { WebhookFieldMapping, WebhookTriggerNodeData } from "../types/nodes";
import { useNodeDialogState } from "./useNodeDialogState";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import {
  buildCurlExample,
  buildEnvelope,
  buildTriggerInput,
  parseSamplePayload,
} from "../nodeTypes/triggers/webhookTriggerMapping";

type WebhookTriggerDialogProps = BaseNodeDialogProps<WebhookTriggerNodeData, WebhookTriggerNodeData>;

type Values = {
  name: string;
  messagePath: string;
  threadIdPath: string;
  idempotencyPath: string;
  samplePayload: string;
  fieldMappings: WebhookFieldMapping[];
};

const STATUS_VARIANT: Record<WorkflowTriggerRunStatus, "default" | "secondary" | "destructive" | "success" | "outline"> = {
  pending: "outline",
  running: "secondary",
  completed: "success",
  failed: "destructive",
  cancelled: "outline",
};

const copy = (text: string, what: string) => {
  void navigator.clipboard.writeText(text);
  toast.success(`${what} copied.`);
};

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

export const WebhookTriggerDialog: React.FC<WebhookTriggerDialogProps> = (props) => {
  const { isOpen, onClose, data, nodeId } = props;
  const { agentId } = useParams<{ agentId: string }>();
  const queryClient = useQueryClient();

  const { values, setField, merged, handleSave } = useNodeDialogState<WebhookTriggerNodeData, Values>(
    props,
    () => ({
      name: data.name || "",
      messagePath: data.messagePath || "",
      threadIdPath: data.threadIdPath || "",
      idempotencyPath: data.idempotencyPath || "",
      samplePayload: data.samplePayload || "",
      fieldMappings: data.fieldMappings ?? [],
    }),
    (v) => ({
      name: v.name,
      messagePath: v.messagePath.trim(),
      threadIdPath: v.threadIdPath.trim(),
      idempotencyPath: v.idempotencyPath.trim(),
      samplePayload: v.samplePayload,
      fieldMappings: v.fieldMappings
        .map((m) => ({ ...m, key: m.key.trim(), path: m.path.trim() }))
        .filter((m) => m.key || m.path),
    })
  );

  // ---- endpoint -------------------------------------------------------------
  const triggerKey = ["workflowTrigger", agentId, nodeId];
  const {
    data: provisioned,
    isLoading: isProvisioning,
    error: provisionError,
  } = useQuery({
    queryKey: triggerKey,
    queryFn: () => provisionWorkflowTrigger({ agent_id: agentId as string, node_id: nodeId as string }),
    enabled: isOpen && !!agentId && !!nodeId,
    staleTime: 30_000,
  });
  const trigger: WorkflowTrigger | undefined = provisioned;

  const [oneTimeSecret, setOneTimeSecret] = useState<string | null>(null);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  useEffect(() => {
    if (provisioned?.created && provisioned.secret) {
      setOneTimeSecret(provisioned.secret);
      void queryClient.invalidateQueries({ queryKey: ["workflowTriggers", agentId] });
    }
  }, [provisioned, agentId, queryClient]);
  useEffect(() => {
    if (!isOpen) {
      setOneTimeSecret(null);
      setRevealedSecret(null);
    }
  }, [isOpen]);

  const [method, setMethod] = useState<WorkflowTriggerMethod>("POST");
  const [authMode, setAuthMode] = useState<WorkflowTriggerAuthMode>("bearer");
  const [rateLimit, setRateLimit] = useState<string>("60");
  const [isActive, setIsActive] = useState(true);
  useEffect(() => {
    if (trigger) {
      setMethod(trigger.method);
      setAuthMode(trigger.auth_mode);
      setRateLimit(String(trigger.rate_limit_per_minute));
      setIsActive(trigger.is_active);
    }
  }, [trigger]);
  const endpointDirty =
    !!trigger &&
    (method !== trigger.method ||
      authMode !== trigger.auth_mode ||
      Number(rateLimit) !== trigger.rate_limit_per_minute ||
      isActive !== trigger.is_active);

  const invalidateTrigger = () => {
    void queryClient.invalidateQueries({ queryKey: triggerKey });
    void queryClient.invalidateQueries({ queryKey: ["workflowTriggers", agentId] });
  };

  const updateEndpoint = useMutation({
    mutationFn: () =>
      updateWorkflowTrigger(trigger!.id, {
        method,
        auth_mode: authMode,
        rate_limit_per_minute: Math.max(0, Number(rateLimit) || 0),
        is_active: isActive,
      }),
    onSuccess: () => {
      toast.success("Endpoint settings applied.");
      invalidateTrigger();
    },
    onError: () => toast.error("Could not apply the endpoint settings."),
  });

  const rotateSecret = useMutation({
    mutationFn: () => rotateWorkflowTriggerSecret(trigger!.id),
    onSuccess: (result) => {
      setRevealedSecret(null);
      setOneTimeSecret(result.secret);
      toast.success("Secret rotated. Update your caller.");
    },
    onError: () => toast.error("Could not rotate the secret."),
  });

  const revealSecret = useMutation({
    mutationFn: () => revealWorkflowTriggerSecret(trigger!.id),
    onSuccess: (result) => setRevealedSecret(result.secret),
    onError: () => toast.error("Could not reveal the secret."),
  });

  // ---- mapping preview --------------------------------------------------------
  const preview = useMemo(() => {
    const envelope = buildEnvelope(parseSamplePayload(values.samplePayload), { method, is_test: true });
    return buildTriggerInput(envelope, {
      fieldMappings: values.fieldMappings,
      messagePath: values.messagePath,
      messageRequired: data.messageRequired,
    });
  }, [values.samplePayload, values.fieldMappings, values.messagePath, data.messageRequired, method]);

  const sampleIsValidJson = useMemo(() => {
    const text = values.samplePayload.trim();
    if (!text) return true;
    try {
      JSON.parse(text);
      return true;
    } catch {
      return false;
    }
  }, [values.samplePayload]);

  const updateMapping = (index: number, patch: Partial<WebhookFieldMapping>) =>
    setField(
      "fieldMappings",
      values.fieldMappings.map((m, i) => (i === index ? { ...m, ...patch } : m))
    );
  const addMapping = () => setField("fieldMappings", [...values.fieldMappings, { key: "", path: "" }]);
  const removeMapping = (index: number) =>
    setField(
      "fieldMappings",
      values.fieldMappings.filter((_, i) => i !== index)
    );

  // ---- runs -------------------------------------------------------------------
  const [activeTab, setActiveTab] = useState("endpoint");
  const runsKey = ["workflowTriggerRuns", trigger?.id];
  const { data: runs, isFetching: runsFetching } = useQuery({
    queryKey: runsKey,
    queryFn: () => getWorkflowTriggerRuns(trigger!.id, { limit: 25 }),
    enabled: isOpen && !!trigger?.id,
    refetchInterval: isOpen && activeTab === "runs" ? 5000 : false,
  });
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const { data: openRun } = useQuery({
    queryKey: ["workflowTriggerRun", trigger?.id, openRunId],
    queryFn: () => getWorkflowTriggerRun(trigger!.id, openRunId as string),
    enabled: !!trigger?.id && !!openRunId,
    refetchInterval: openRunId ? 5000 : false,
  });

  const sendTest = useMutation({
    mutationFn: () =>
      testWorkflowTrigger(trigger!.id, { payload: parseSamplePayload(values.samplePayload) }),
    onSuccess: (delivery) => {
      toast.success(`Test delivery queued (run ${delivery.run_id.slice(0, 8)}…).`);
      setActiveTab("runs");
      setOpenRunId(delivery.run_id);
      void queryClient.invalidateQueries({ queryKey: runsKey });
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      toast.error(
        typeof message === "string"
          ? message
          : "Test delivery failed. Save the workflow first so the node is published."
      );
    },
  });

  const curl = trigger
    ? buildCurlExample(trigger.url, method, authMode, values.samplePayload)
    : "";

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
        <Label htmlFor="node-name">Node Name</Label>
        <RichInput
          id="node-name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="endpoint">Endpoint</TabsTrigger>
          <TabsTrigger value="mapping">Mapping</TabsTrigger>
          <TabsTrigger value="runs">
            Runs{runs?.length ? ` (${runs.length})` : ""}
          </TabsTrigger>
        </TabsList>

        {/* ------------------------------------------------------------------ */}
        <TabsContent value="endpoint" className="space-y-4 pt-2">
          {isProvisioning && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Generating endpoint…
            </div>
          )}
          {provisionError && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
              <span>Could not generate the endpoint. Check that the agent exists and try again.</span>
            </div>
          )}

          {trigger && (
            <>
              <div className="space-y-2">
                <Label>Endpoint URL</Label>
                <div className="flex gap-2">
                  <Input readOnly value={trigger.url} className="font-mono text-xs" />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => copy(trigger.url, "Endpoint URL")}
                    title="Copy URL"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  The endpoint answers 404 until the workflow containing this node is saved and
                  published. Node id: <span className="font-mono">{nodeId}</span>
                </p>
              </div>

              {oneTimeSecret ? (
                <div className="space-y-2 rounded-md border border-amber-300/60 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <KeyRound className="h-4 w-4" /> Secret — shown once, copy it now
                  </div>
                  <SecretInput value={oneTimeSecret} />
                </div>
              ) : (
                <div className="space-y-2">
                  <Label>Secret</Label>
                  {revealedSecret ? (
                    <SecretInput value={revealedSecret} />
                  ) : (
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => revealSecret.mutate()}
                        disabled={revealSecret.isPending}
                      >
                        <Eye className="mr-2 h-4 w-4" /> Reveal
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (window.confirm("Rotate the secret? Existing callers stop working until updated.")) {
                            rotateSecret.mutate();
                          }
                        }}
                        disabled={rotateSecret.isPending}
                      >
                        <RefreshCw className="mr-2 h-4 w-4" /> Rotate
                      </Button>
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 items-start gap-3">
                <div className="space-y-2">
                  <div className="flex h-5 items-center gap-1.5">
                    <Label htmlFor="wt-method">HTTP method</Label>
                  </div>
                  <Select value={method} onValueChange={(v) => setMethod(v as WorkflowTriggerMethod)}>
                    <SelectTrigger id="wt-method">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="POST">POST</SelectItem>
                      <SelectItem value="GET">GET</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <div className="flex h-5 items-center gap-1.5">
                    <Label htmlFor="wt-auth">Authentication</Label>
                  </div>
                  <Select value={authMode} onValueChange={(v) => setAuthMode(v as WorkflowTriggerAuthMode)}>
                    <SelectTrigger id="wt-auth">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bearer">Bearer token</SelectItem>
                      <SelectItem value="hmac">HMAC-SHA256 signature</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <div className="flex h-5 items-center gap-1.5">
                    <Label htmlFor="wt-rate">Rate limit (per minute)</Label>
                    <Tooltip
                      content="Maximum deliveries accepted per minute for this endpoint. 0 disables the limit."
                      iconClassName="h-3.5 w-3.5"
                      contentClassName="w-56 text-left"
                    />
                  </div>
                  <Input
                    id="wt-rate"
                    type="number"
                    min={0}
                    max={6000}
                    value={rateLimit}
                    onChange={(e) => setRateLimit(e.target.value)}
                    className="h-10"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex h-5 items-center gap-1.5">
                    <Label htmlFor="wt-active">Accepting deliveries</Label>
                    <Tooltip
                      content="When off, the endpoint answers 404 and no runs are queued. Use it to pause an integration without rotating the secret."
                      iconClassName="h-3.5 w-3.5"
                      contentClassName="w-56 text-left"
                    />
                  </div>
                  <div className="flex h-10 items-center justify-between rounded-full border border-input bg-background px-3">
                    <span className="text-sm">{isActive ? "Enabled" : "Paused"}</span>
                    <Switch id="wt-active" checked={isActive} onCheckedChange={(c) => setIsActive(Boolean(c))} />
                  </div>
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  variant={endpointDirty ? "default" : "outline"}
                  disabled={!endpointDirty || updateEndpoint.isPending}
                  onClick={() => updateEndpoint.mutate()}
                >
                  {updateEndpoint.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Apply endpoint settings
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Endpoint settings are stored with the endpoint, not the workflow version, so they apply
                immediately and survive publishing.
              </p>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Example request</Label>
                  <Button type="button" variant="ghost" size="sm" onClick={() => copy(curl, "curl command")}>
                    <Copy className="mr-2 h-3.5 w-3.5" /> Copy
                  </Button>
                </div>
                <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs font-mono whitespace-pre">{curl}</pre>
                {authMode === "hmac" && (
                  <p className="text-xs text-muted-foreground">
                    Signature = <span className="font-mono">sha256=hex(HMAC_SHA256(secret, "&lt;timestamp&gt;.&lt;raw body&gt;"))</span>;
                    timestamps older than 5 minutes are rejected.
                  </p>
                )}
              </div>
            </>
          )}
        </TabsContent>

        {/* ------------------------------------------------------------------ */}
        <TabsContent value="mapping" className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            Downstream nodes always receive the delivery as{" "}
            <span className="font-mono">webhook</span> (method, headers, query, body). Paths are dotted
            and start at that envelope, e.g. <span className="font-mono">body.order.id</span> or{" "}
            <span className="font-mono">headers.x-event-type</span>.
          </p>

          <div className="grid grid-cols-1 gap-3">
            <div className="space-y-1">
              <Label htmlFor="wt-message">Message path</Label>
              <Input
                id="wt-message"
                value={values.messagePath}
                onChange={(e) => setField("messagePath", e.target.value)}
                placeholder="body.message"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Sets the workflow <span className="font-mono">message</span> and writes the run to
                conversation memory. Leave empty for event-style payloads.
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="wt-thread">Thread id path</Label>
              <Input
                id="wt-thread"
                value={values.threadIdPath}
                onChange={(e) => setField("threadIdPath", e.target.value)}
                placeholder="body.conversation_id"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Groups deliveries into one conversation thread. Empty = a new thread per run.
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="wt-idem">Idempotency key path</Label>
              <Input
                id="wt-idem"
                value={values.idempotencyPath}
                onChange={(e) => setField("idempotencyPath", e.target.value)}
                placeholder="body.event_id"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                A redelivery with the same key returns the first run. An{" "}
                <span className="font-mono">Idempotency-Key</span> header is always honoured.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Extra input fields</Label>
              <Button type="button" variant="outline" size="sm" onClick={addMapping}>
                <Plus className="mr-1 h-4 w-4" /> Add field
              </Button>
            </div>
            {values.fieldMappings.length === 0 && (
              <p className="text-xs text-muted-foreground">
                Optional. Expose parts of the payload as top-level inputs (e.g.{" "}
                <span className="font-mono">order_id</span>) for easier reference downstream.
              </p>
            )}
            <div className="space-y-2">
              {values.fieldMappings.map((mapping, index) => (
                <div key={index} className="grid grid-cols-[1fr_1.4fr_auto_1fr_auto] items-center gap-2 rounded-md border p-2">
                  <Input
                    aria-label={`Field ${index + 1} key`}
                    value={mapping.key}
                    onChange={(e) => updateMapping(index, { key: e.target.value })}
                    placeholder="input key"
                    className="font-mono text-xs"
                  />
                  <Input
                    aria-label={`Field ${index + 1} path`}
                    value={mapping.path}
                    onChange={(e) => updateMapping(index, { path: e.target.value })}
                    placeholder="body.path.to.value"
                    className="font-mono text-xs"
                  />
                  <div className="flex items-center gap-1" title="Required: reject the delivery (422) when missing">
                    <Switch
                      aria-label={`Field ${index + 1} required`}
                      checked={!!mapping.required}
                      onCheckedChange={(c) => updateMapping(index, { required: Boolean(c) })}
                    />
                    <span className="text-[10px] text-muted-foreground">req</span>
                  </div>
                  <Input
                    aria-label={`Field ${index + 1} default`}
                    value={mapping.default ?? ""}
                    onChange={(e) => updateMapping(index, { default: e.target.value })}
                    placeholder="default"
                    className="text-xs"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0 text-red-600 hover:text-red-700"
                    onClick={() => removeMapping(index)}
                    title="Remove field"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="wt-sample">Sample payload (JSON body)</Label>
              <Button
                type="button"
                size="sm"
                onClick={() => sendTest.mutate()}
                disabled={!trigger || !sampleIsValidJson || sendTest.isPending}
                title={trigger ? "Queue a real run with this payload (no auth needed)" : "Generate the endpoint first"}
              >
                {sendTest.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Send test delivery
              </Button>
            </div>
            <Textarea
              id="wt-sample"
              size="code"
              value={values.samplePayload}
              onChange={(e) => setField("samplePayload", e.target.value)}
              className="font-mono text-xs"
              spellCheck={false}
            />
            {!sampleIsValidJson && (
              <p className="text-xs text-destructive">Not valid JSON — it would arrive as {"{ raw: ... }"}.</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Preview of the workflow input</Label>
            {preview.errors.length > 0 && (
              <ul className="space-y-1 rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
                {preview.errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            )}
            <div className="rounded-md border bg-muted/40 p-2">
              <JsonViewer data={preview.input as unknown as JsonValue} name="input" collapsed={false} />
            </div>
          </div>
        </TabsContent>

        {/* ------------------------------------------------------------------ */}
        <TabsContent value="runs" className="space-y-3 pt-2">
          {!trigger && (
            <p className="text-sm text-muted-foreground">Generate the endpoint to see its runs.</p>
          )}
          {trigger && (
            <>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  Latest deliveries{runsFetching ? " · refreshing…" : ""}
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => void queryClient.invalidateQueries({ queryKey: runsKey })}
                >
                  <RefreshCw className="mr-2 h-3.5 w-3.5" /> Refresh
                </Button>
              </div>
              {(runs?.length ?? 0) === 0 && (
                <p className="text-sm text-muted-foreground">
                  No deliveries yet. Send a test from the Mapping tab or call the endpoint.
                </p>
              )}
              <div className="space-y-1">
                {runs?.map((run) => (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => setOpenRunId(openRunId === run.id ? null : run.id)}
                    className={`flex w-full items-center gap-3 rounded-md border p-2 text-left text-xs hover:bg-muted/50 ${
                      openRunId === run.id ? "bg-muted/60" : ""
                    }`}
                  >
                    <Badge variant={STATUS_VARIANT[run.status]} className="w-20 justify-center capitalize">
                      {run.status}
                    </Badge>
                    <span className="font-mono">{run.id.slice(0, 8)}</span>
                    <span className="flex-1 truncate text-muted-foreground">{formatDate(run.created_at)}</span>
                    {run.idempotency_key && (
                      <span className="truncate font-mono text-muted-foreground" title="Idempotency key">
                        {run.idempotency_key}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              {openRunId && openRun && (
                <div className="space-y-2 rounded-md border p-2">
                  {openRun.error_message && (
                    <p className="text-xs text-destructive">{openRun.error_message}</p>
                  )}
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                    <span>Started: {formatDate(openRun.started_at)}</span>
                    <span>Completed: {formatDate(openRun.completed_at)}</span>
                    <span className="col-span-2 font-mono">Thread: {openRun.thread_id ?? "—"}</span>
                  </div>
                  <JsonViewer data={(openRun.input_data ?? {}) as unknown as JsonValue} name="input" collapsed />
                  <JsonViewer
                    data={(openRun.execution_output ?? {}) as unknown as JsonValue}
                    name="output"
                    collapsed
                  />
                </div>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
    </NodeConfigPanel>
  );
};

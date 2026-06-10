import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { toast } from "react-hot-toast";
import { X, Plus, Copy, Check, RefreshCw, AlertTriangle } from "lucide-react";
import {
  MCPServer,
  MCPServerAuthType,
  MCPServerCreatePayload,
  MCPServerUpdatePayload,
  MCPServerWorkflow,
} from "@/interfaces/mcp-server.interface";
import { createMCPServer, updateMCPServer } from "@/services/mcpServer";
import { getAllWorkflows } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { extractInboundOAuthHintsFromJwt } from "@/helpers/mcpOauthInboundJwt";
interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onServerSaved?: () => void;
  onServerUpdated?: (server: MCPServer) => void;
  mode?: "create" | "edit";
  serverToEdit?: MCPServer | null;
}

export function MCPServerDialog({
  isOpen,
  onOpenChange,
  onServerSaved,
  onServerUpdated,
  mode = "create",
  serverToEdit,
}: Props) {
  const [name, setName] = useState("");
  const [authType, setAuthType] = useState<MCPServerAuthType>("api_key");
  const [apiKey, setApiKey] = useState("");
  const [oauth2ClientId, setOauth2ClientId] = useState("");
  const [oauth2ClientSecret, setOauth2ClientSecret] = useState("");
  const [oauth2IssuerUrl, setOauth2IssuerUrl] = useState("");
  const [oauth2Scope, setOauth2Scope] = useState("");
  const [oauth2Audience, setOauth2Audience] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflows, setSelectedWorkflows] = useState<MCPServerWorkflow[]>([]);
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false);
  const [isApiKeyGenerated, setIsApiKeyGenerated] = useState(false);
  const [isApiKeyCopied, setIsApiKeyCopied] = useState(false);
  /** Paste JWT to fill issuer URL / scope hints (client-side only; never submitted). */
  const [sampleJwtPaste, setSampleJwtPaste] = useState("");

  useEffect(() => {
    if (isOpen) {
      const fetchWorkflows = async () => {
        setIsLoadingWorkflows(true);
        try {
          const workflowsData = await getAllWorkflows();
          setWorkflows(workflowsData);
        } catch (error) {
          toast.error("Failed to load workflows");
        } finally {
          setIsLoadingWorkflows(false);
        }
      };

      fetchWorkflows();

      if (mode === "edit" && serverToEdit) {
        setName(serverToEdit.name);
        setAuthType(serverToEdit.auth_type === "oauth2" ? "oauth2" : "api_key");
        setApiKey(""); // Don't show existing API key for security
        setOauth2ClientSecret("");
        const av = serverToEdit.auth_values ?? {};
        setOauth2ClientId(
          typeof av.oauth2_client_id === "string" ? av.oauth2_client_id : ""
        );
        setOauth2IssuerUrl(
          typeof av.oauth2_issuer_url === "string" ? av.oauth2_issuer_url.trim() : ""
        );
        setOauth2Scope(typeof av.oauth2_scope === "string" ? av.oauth2_scope : "");
        setOauth2Audience(
          typeof av.oauth2_audience === "string" ? av.oauth2_audience.trim() : ""
        );
        setDescription(serverToEdit.description || "");
        setIsActive(serverToEdit.is_active === 1);
        setSelectedWorkflows(serverToEdit.workflows || []);
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
      } else {
        setName("");
        setAuthType("api_key");
        setApiKey("");
        setOauth2ClientId("");
        setOauth2ClientSecret("");
        setOauth2IssuerUrl("");
        setOauth2Scope("");
        setOauth2Audience("");
        setDescription("");
        setIsActive(true);
        setSelectedWorkflows([]);
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
      }
    }
  }, [isOpen, mode, serverToEdit]);

  const generateApiKey = () => {
    // Generate a cryptographically secure random API key
    // Format: mcp_ followed by 32 random hex characters
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    const hexString = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    const newApiKey = `mcp_${hexString}`;
    setApiKey(newApiKey);
    setIsApiKeyGenerated(true);
    setIsApiKeyCopied(false);
    // Auto-copy to clipboard
    copyApiKeyToClipboard(newApiKey);
  };

  const copyApiKeyToClipboard = async (keyToCopy?: string) => {
    const key = keyToCopy || apiKey;
    if (!key) return;

    try {
      await navigator.clipboard.writeText(key);
      setIsApiKeyCopied(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setIsApiKeyCopied(false), 3000);
    } catch (error) {
      toast.error("Failed to copy API key");
    }
  };

  const handleSubmit = async () => {
    const missingFields: string[] = [];
    if (!name.trim()) missingFields.push("Name");
    if (mode === "create" && authType === "api_key" && !apiKey.trim()) {
      missingFields.push("API Key");
    }
    if (mode === "create" && authType === "oauth2") {
      if (!oauth2ClientId.trim()) missingFields.push("OAuth Client ID");
      if (!oauth2ClientSecret.trim()) missingFields.push("OAuth Client Secret");
      if (!oauth2IssuerUrl.trim()) {
        missingFields.push("OIDC issuer URL");
      }
    }
    if (mode === "edit" && serverToEdit) {
      const prevAuth: MCPServerAuthType =
        serverToEdit.auth_type === "oauth2" ? "oauth2" : "api_key";
      if (authType === "oauth2" && prevAuth !== "oauth2") {
        if (!oauth2ClientId.trim()) missingFields.push("OAuth Client ID");
        if (!oauth2ClientSecret.trim()) missingFields.push("OAuth Client Secret");
        if (!oauth2IssuerUrl.trim()) {
          missingFields.push("OIDC issuer URL");
        }
      }
      if (authType === "api_key" && prevAuth !== "api_key") {
        if (!apiKey.trim()) missingFields.push("API Key");
      }
    }
    if (selectedWorkflows.length === 0) missingFields.push("At least one workflow");

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    // Validate all workflows have tool names and descriptions
    const invalidWorkflows = selectedWorkflows.filter(
      (w) => !w.tool_name.trim() || !w.tool_description.trim()
    );
    if (invalidWorkflows.length > 0) {
      toast.error("All workflows must have a tool name and description.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === 'create') {
        const payload: MCPServerCreatePayload = {
          name,
          auth_type: authType,
          description: description || undefined,
          is_active: isActive ? 1 : 0,
          workflows: selectedWorkflows,
          ...(authType === "api_key"
            ? { api_key: apiKey }
            : {
                oauth2_client_id: oauth2ClientId.trim(),
                oauth2_client_secret: oauth2ClientSecret.trim(),
                oauth2_issuer_url: oauth2IssuerUrl.trim(),
                ...(oauth2Scope.trim() ? { oauth2_scope: oauth2Scope.trim() } : {}),
                ...(oauth2Audience.trim()
                  ? { oauth2_audience: oauth2Audience.trim() }
                  : {}),
              }),
        };
        await createMCPServer(payload);
        toast.success('MCP server created successfully.');
        // Reset API key state after saving
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
        onServerSaved?.();
        onOpenChange(false);
      } else if (serverToEdit) {
        const updatePayload: MCPServerUpdatePayload = {};

        if (name !== serverToEdit.name) updatePayload.name = name;
        if ((description || undefined) !== (serverToEdit.description || undefined))
          updatePayload.description = description || undefined;
        if ((isActive ? 1 : 0) !== serverToEdit.is_active) updatePayload.is_active = isActive ? 1 : 0;

        const prevAuth: MCPServerAuthType =
          serverToEdit.auth_type === "oauth2" ? "oauth2" : "api_key";
        if (authType !== prevAuth) {
          updatePayload.auth_type = authType;
        }
        if (authType === "api_key" && apiKey.trim()) updatePayload.api_key = apiKey;
        if (authType === "oauth2") {
          const prevAv = serverToEdit.auth_values ?? {};
          const prevIss =
            typeof prevAv.oauth2_issuer_url === "string"
              ? prevAv.oauth2_issuer_url.trim()
              : "";
          if (oauth2IssuerUrl.trim() !== prevIss.trim()) {
            updatePayload.oauth2_issuer_url = oauth2IssuerUrl.trim();
          }
          const prevScope =
            typeof prevAv.oauth2_scope === "string" ? prevAv.oauth2_scope.trim() : "";
          const nextScope = oauth2Scope.trim();
          if (nextScope !== prevScope) {
            updatePayload.oauth2_scope = nextScope || "";
          }
          const prevAudience =
            typeof prevAv.oauth2_audience === "string"
              ? prevAv.oauth2_audience.trim()
              : "";
          const nextAudience = oauth2Audience.trim();
          if (nextAudience !== prevAudience) {
            updatePayload.oauth2_audience = nextAudience || "";
          }
          const prevCid =
            typeof prevAv.oauth2_client_id === "string" ? prevAv.oauth2_client_id : "";
          if (
            oauth2ClientId.trim() &&
            oauth2ClientId.trim() !== prevCid.trim()
          ) {
            updatePayload.oauth2_client_id = oauth2ClientId.trim();
          }
          if (oauth2ClientSecret.trim()) {
            updatePayload.oauth2_client_secret = oauth2ClientSecret.trim();
          }
        }

        const workflowsChanged =
          selectedWorkflows.length !== (serverToEdit.workflows || []).length ||
          selectedWorkflows.some((sw) => {
            const orig = (serverToEdit.workflows || []).find((w) => w.workflow_id === sw.workflow_id);
            return !orig || orig.tool_name !== sw.tool_name || orig.tool_description !== sw.tool_description;
          });
        if (workflowsChanged) updatePayload.workflows = selectedWorkflows;

        const updated = await updateMCPServer(serverToEdit.id, updatePayload);
        toast.success('MCP server updated successfully.');

        onServerUpdated?.(updated);

        onOpenChange(false);
      }
    } catch (error: unknown) {
      const errorMessage =
        error && typeof error === "object" && "status" in error && error.status === 400
          ? ": A server with this name already exists"
          : "";
      toast.error(`Failed to ${mode} MCP server${errorMessage}.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const addWorkflow = (workflowId: string) => {
    const workflow = workflows.find((w) => w.id === workflowId);
    if (!workflow) return;

    // Check if already added
    if (selectedWorkflows.some((w) => w.workflow_id === workflowId)) {
      toast.error("Workflow already added");
      return;
    }

    setSelectedWorkflows([
      ...selectedWorkflows,
      {
        workflow_id: workflowId,
        tool_name: workflow.name.toLowerCase().replace(/\s+/g, "_"),
        tool_description: workflow.description || `Execute ${workflow.name} workflow`,
      },
    ]);
  };

  const removeWorkflow = (workflowId: string) => {
    setSelectedWorkflows(selectedWorkflows.filter((w) => w.workflow_id !== workflowId));
  };

  const updateWorkflowToolName = (workflowId: string, toolName: string) => {
    setSelectedWorkflows(
      selectedWorkflows.map((w) =>
        w.workflow_id === workflowId ? { ...w, tool_name: toolName } : w
      )
    );
  };

  const updateWorkflowToolDescription = (
    workflowId: string,
    toolDescription: string
  ) => {
    setSelectedWorkflows(
      selectedWorkflows.map((w) =>
        w.workflow_id === workflowId
          ? { ...w, tool_description: toolDescription }
          : w
      )
    );
  };

  const availableWorkflows = workflows.filter(
    (w) => !selectedWorkflows.some((sw) => sw.workflow_id === w.id)
  );

  const handleDialogClose = (open: boolean) => {
    if (!open && isApiKeyGenerated && !isApiKeyCopied && apiKey) {
      // Warn user if they're closing without copying
      const confirmed = window.confirm(
        "You haven't copied the API key yet. This key can only be viewed once. Are you sure you want to close without copying it?"
      );
      if (!confirmed) {
        return;
      }
    }
    // Reset states when closing
    if (!open) {
      setIsApiKeyGenerated(false);
      setIsApiKeyCopied(false);
      setSampleJwtPaste("");
    }
    onOpenChange(open);
  };

  const applyOAuthHintsFromSampleJwt = () => {
    const hints = extractInboundOAuthHintsFromJwt(sampleJwtPaste);
    if (!hints) {
      toast.error(
        "Could not read that token. Paste a JWT access token (three segments separated by dots)."
      );
      return;
    }
    const clientIdWasEmpty = !oauth2ClientId.trim();
    setOauth2IssuerUrl(hints.discoveryUrl);
    if (hints.scopeHint) {
      setOauth2Scope(hints.scopeHint);
    }
    if (hints.clientIdHint && clientIdWasEmpty) {
      setOauth2ClientId(hints.clientIdHint);
    }
    const filled = ["Issuer URL"];
    if (hints.scopeHint) filled.push("Scope");
    if (hints.clientIdHint && clientIdWasEmpty) filled.push("Client ID");
    toast.success(`Updated ${filled.join(", ")} from token (parsed in your browser only).`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogClose}>
      <DialogContent className="sm:max-w-[700px] p-0 flex flex-col max-h-[90vh]">
        <DialogHeader className="p-6 pb-4 flex-shrink-0">
          <DialogTitle>
            {mode === "create" ? "Add New MCP Server" : "Edit MCP Server"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6">
          <div className="grid gap-4 pb-4">
            <div>
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My MCP Server"
              />
            </div>

            <div>
              <Label htmlFor="auth-type">Authentication *</Label>
              <Select
                value={authType}
                onValueChange={(v) => setAuthType(v as MCPServerAuthType)}
                disabled={isSubmitting}
              >
                <SelectTrigger id="auth-type" className="w-full mt-1">
                  <SelectValue placeholder="Select method" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="api_key">API key</SelectItem>
                  <SelectItem value="oauth2">OAuth 2.0 / OIDC — inbound JWT (discovery)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500 mt-1">
                {authType === "api_key"
                  ? `MCP clients send Authorization: Bearer <api_key>.`
                  : `Inbound auth: callers send Authorization: Bearer <JWT access_token>. Provide the full OIDC issuer URL (…/.well-known/openid-configuration); JWKS and issuer checks use that document. Client ID must match the application id in the token (e.g. azp, client_id, appid). Optional scope (space-separated) requires matching scope/scp claims in the token.`}
              </p>
            </div>

            {authType === "api_key" && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label htmlFor="api-key">
                  API Key {mode === "create" ? "*" : "(leave blank to keep existing)"}
                </Label>
                {mode === "create" && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={generateApiKey}
                    className="h-7 text-xs"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Generate
                  </Button>
                )}
              </div>

              {isApiKeyGenerated && (
                <div className="mb-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-xs font-medium text-yellow-800 mb-1">
                        Important: Copy this API key now
                      </p>
                      <p className="text-xs text-yellow-700">
                        This API key can only be viewed once. Make sure to copy and save it securely before continuing.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                <Input
                  id="api-key"
                  type={isApiKeyGenerated ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setIsApiKeyGenerated(false);
                    setIsApiKeyCopied(false);
                  }}
                  placeholder={mode === "edit" ? "Enter new API key or leave blank" : "Click Generate or enter API key"}
                  className={isApiKeyGenerated ? "font-mono text-sm" : ""}
                  readOnly={isApiKeyGenerated}
                />
                {apiKey && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-10 w-10 flex-shrink-0"
                    onClick={() => copyApiKeyToClipboard()}
                    title="Copy API key"
                  >
                    {isApiKeyCopied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {isApiKeyGenerated
                  ? "API key generated. Copy it now - you won't be able to see it again after saving."
                  : "API key for authenticating MCP client requests"}
              </p>
            </div>
            )}

            {authType === "oauth2" && (
              <div className="space-y-3 rounded-md border p-3">
                <p className="text-xs font-medium text-gray-700">
                  OAuth 2.0 + OpenID Connect — inbound JWT validation
                </p>
                <p className="text-xs text-gray-600 -mt-2">
                  This form configures how Genassist <strong>verifies</strong> tokens clients send to{" "}
                  <strong>this</strong> hosted MCP server. It is not used to fetch tokens (that is the workflow
                  MCP node when it calls an external server).
                </p>

                <div
                  className="rounded-md border border-slate-200 bg-slate-50/90 px-3 py-2.5 text-xs text-slate-700"
                  role="region"
                  aria-label="Inbound OIDC fields reference"
                >
                  <p className="font-semibold text-slate-800 mb-2">Hosted MCP — OIDC discovery configuration</p>
                  <dl className="space-y-1.5">
                    <div className="flex flex-col sm:flex-row sm:gap-2">
                      <dt className="shrink-0 text-slate-500 sm:w-32">Issuer URL</dt>
                      <dd className="font-mono text-[11px] text-slate-800 break-all">
                        …/.well-known/openid-configuration
                      </dd>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:gap-2">
                      <dt className="shrink-0 text-slate-500 sm:w-32">Client ID</dt>
                      <dd className="text-slate-800">Must match the app id embedded in callers&apos; JWTs</dd>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:gap-2">
                      <dt className="shrink-0 text-slate-500 sm:w-32">Client secret</dt>
                      <dd className="text-slate-800">Stored encrypted (aligned with your IdP registration)</dd>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:gap-2">
                      <dt className="shrink-0 text-slate-500 sm:w-32">Scope</dt>
                      <dd className="text-slate-800">
                        Optional — if set, JWT <code className="text-[10px]">scope</code> /{" "}
                        <code className="text-[10px]">scp</code> must include these values
                      </dd>
                    </div>
                  </dl>
                </div>

                <details className="rounded-md border border-dashed border-amber-200/80 bg-amber-50/50 p-3 text-xs text-gray-700">
                  <summary className="cursor-pointer font-medium text-gray-800 select-none">
                    Don&apos;t know the issuer URL yet?
                  </summary>
                  <div className="mt-3 space-y-3">
                    <p>
                      <strong>Issuer URL</strong> is the full address of your IdP&apos;s OpenID
                      configuration document (usually ends in{" "}
                      <code className="text-xs">/.well-known/openid-configuration</code>). You do not need to
                      copy it from a portal first: obtain any <strong>access token</strong> from the same M2M
                      application (client credentials in Postman, <code className="text-xs">az login</code>,
                      etc.), paste it below, and click <strong>Fill fields from token</strong>. Only the payload
                      is decoded <strong>in your browser</strong>; the token is not sent to Genassist.
                    </p>
                    <div className="space-y-2">
                      <Label htmlFor="mcp-sample-jwt" className="text-xs">
                        Sample access token (JWT)
                      </Label>
                      <Textarea
                        id="mcp-sample-jwt"
                        value={sampleJwtPaste}
                        onChange={(e) => setSampleJwtPaste(e.target.value)}
                        placeholder="eyJhbGciOiJSUzI1NiIs..."
                        className="font-mono text-xs min-h-[72px]"
                        autoComplete="off"
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="w-full sm:w-auto"
                        onClick={applyOAuthHintsFromSampleJwt}
                      >
                        Fill fields from token
                      </Button>
                    </div>
                  </div>
                </details>

                {mode === "edit" && serverToEdit?.auth_type === "oauth2" && (
                  <div className="rounded-md bg-slate-50 border border-slate-200 p-3 space-y-2 mb-1">
                    <p className="text-xs font-semibold text-slate-800">
                      Current configuration (from server)
                    </p>
                    <dl className="grid gap-2 text-xs text-slate-700">
                      <div>
                        <dt className="text-slate-500 font-normal">OIDC issuer URL</dt>
                        <dd className="font-mono break-all mt-0.5">
                          {oauth2IssuerUrl.trim() || "—"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 font-normal">Client ID (must match token)</dt>
                        <dd className="font-mono break-all mt-0.5">
                          {oauth2ClientId.trim() || "—"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 font-normal">Scope</dt>
                        <dd className="font-mono break-all mt-0.5">
                          {oauth2Scope.trim() ? oauth2Scope : "None — scope/scp not enforced"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 font-normal">Client secret</dt>
                        <dd className="mt-0.5">
                          {serverToEdit.auth_values?.oauth2_client_secret_set
                            ? "Stored (hidden) — enter a new secret below to replace it"
                            : "Not set"}
                        </dd>
                      </div>
                    </dl>
                    <p className="text-xs text-slate-600 pt-1 border-t border-slate-200">
                      Edit the fields below to change values. Leave Client secret empty to keep the current
                      secret. Use the same Client ID as in your IdP; inbound JWTs are matched by hashing this id
                      (case-insensitive).
                    </p>
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="oauth-discovery">OIDC issuer URL *</Label>
                  <Input
                    id="oauth-discovery"
                    value={oauth2IssuerUrl}
                    onChange={(e) => setOauth2IssuerUrl(e.target.value)}
                    placeholder="http://localhost:8000/.well-known/openid-configuration"
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500">
                    Full URL to the OpenID configuration document. The JWT{" "}
                    <code className="text-xs">iss</code> must match the <code className="text-xs">issuer</code>{" "}
                    field from this document. JWKS comes from <code className="text-xs">jwks_uri</code> in the
                    same JSON.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="oauth-client-id">
                    OAuth Client ID {mode === "create" ? "*" : "(optional if unchanged)"}
                  </Label>
                  <Input
                    id="oauth-client-id"
                    value={oauth2ClientId}
                    onChange={(e) => setOauth2ClientId(e.target.value)}
                    placeholder="Application (M2M) client id — must appear in the access token"
                    className="font-mono text-sm"
                    autoComplete="off"
                  />
                  <p className="text-xs text-gray-500">
                    Same id you use at the IdP. The token should include it as{" "}
                    <code className="text-xs">azp</code>, <code className="text-xs">client_id</code>, or on
                    Azure often <code className="text-xs">appid</code>.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="oauth-client-secret">
                    Client secret {mode === "create" ? "*" : "(optional if unchanged)"}
                  </Label>
                  <Input
                    id="oauth-client-secret"
                    type="password"
                    value={oauth2ClientSecret}
                    onChange={(e) => setOauth2ClientSecret(e.target.value)}
                    placeholder={
                      mode === "edit" && serverToEdit?.auth_values?.oauth2_client_secret_set
                        ? "Leave empty to keep current secret"
                        : "Client secret from your IdP app registration"
                    }
                    className="font-mono text-sm"
                    autoComplete="new-password"
                  />
                  <p className="text-xs text-gray-500">
                    Stored encrypted. Required when you first create an OAuth2 server. Inbound callers are
                    validated with JWKS; the secret is for management and IdP-aligned features.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="oauth-scope">Scope</Label>
                  <Input
                    id="oauth-scope"
                    value={oauth2Scope}
                    onChange={(e) => setOauth2Scope(e.target.value)}
                    placeholder="openid mcp"
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500">
                    Optional. Space-separated values that must all appear in the token&apos;s{" "}
                    <code className="text-xs">scope</code> or <code className="text-xs">scp</code> claims. Leave
                    empty to skip scope checks (signature and issuer are still validated).
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="oauth-audience">Audience</Label>
                  <Input
                    id="oauth-audience"
                    value={oauth2Audience}
                    onChange={(e) => setOauth2Audience(e.target.value)}
                    placeholder="api://your-api-id, https://api.example.com"
                    className="font-mono text-sm"
                    autoComplete="off"
                  />
                  <p className="text-xs text-gray-500">
                    Optional. Comma-separated allowlist for JWT <code className="text-xs">aud</code>. Leave
                    empty to skip audience checks.
                  </p>
                </div>
              </div>
            )}

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Optional description for this MCP server"
              />
            </div>

            <div>
              <Label>Workflows *</Label>
              <p className="text-xs text-gray-500 mb-3">
                Select workflows to expose as MCP tools. Each workflow will be available as a tool with a custom name and description.
              </p>

              {selectedWorkflows.length === 0 && availableWorkflows.length === 0 ? (
                <div className="text-sm text-gray-500 text-center py-8 border-2 border-dashed rounded-md bg-gray-50">
                  <p className="mb-1">No workflows available</p>
                  <p className="text-xs">Create workflows first to expose them as MCP tools</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                  {selectedWorkflows.map((sw) => {
                    const workflow = workflows.find((w) => w.id === sw.workflow_id);
                    return (
                      <div
                        key={sw.workflow_id}
                        className="border rounded-lg p-4 space-y-3 bg-white shadow-sm"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">
                              {workflow?.name || "Unknown Workflow"}
                            </p>
                            {workflow?.description && (
                              <p className="text-xs text-gray-500 mt-1 line-clamp-1">
                                {workflow.description}
                              </p>
                            )}
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 flex-shrink-0 ml-2"
                            onClick={() => removeWorkflow(sw.workflow_id)}
                            title="Remove workflow"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="grid grid-cols-1 gap-3">
                          <div>
                            <Label htmlFor={`tool-name-${sw.workflow_id}`} className="text-xs font-medium">
                              Tool Name *
                            </Label>
                            <Input
                              id={`tool-name-${sw.workflow_id}`}
                              value={sw.tool_name}
                              onChange={(e) =>
                                updateWorkflowToolName(sw.workflow_id, e.target.value)
                              }
                              placeholder="e.g., execute_my_workflow"
                              className="text-sm mt-1"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              Name to expose this workflow as in MCP (use lowercase with underscores)
                            </p>
                          </div>

                          <div>
                            <Label htmlFor={`tool-desc-${sw.workflow_id}`} className="text-xs font-medium">
                              Tool Description *
                            </Label>
                            <Textarea
                              id={`tool-desc-${sw.workflow_id}`}
                              value={sw.tool_description}
                              onChange={(e) =>
                                updateWorkflowToolDescription(
                                  sw.workflow_id,
                                  e.target.value
                                )
                              }
                              placeholder="Description of what this tool does"
                              rows={2}
                              className="text-sm mt-1"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              Description that will be shown to MCP clients
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {availableWorkflows.length > 0 && (
                    <div className="relative">
                      <Select
                        onValueChange={addWorkflow}
                        disabled={isLoadingWorkflows}
                      >
                        <SelectTrigger className="w-full border-2 border-dashed rounded-lg p-4 hover:border-primary hover:bg-primary/5 transition-colors h-auto">
                          <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
                            <Plus className="h-4 w-4" />
                            <span>Add Workflow</span>
                          </div>
                        </SelectTrigger>
                        <SelectContent>
                          {availableWorkflows.map((workflow) => (
                            <SelectItem key={workflow.id} value={workflow.id || ""}>
                              {workflow.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center space-x-2 pt-2">
              <Switch
                id="is-active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
              <Label htmlFor="is-active">Active</Label>
            </div>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t flex-shrink-0">
          <div className="flex justify-end gap-3 w-full">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting
                ? "Saving..."
                : mode === "create"
                ? "Create MCP Server"
                : "Update MCP Server"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


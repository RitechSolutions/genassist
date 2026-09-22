import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Separator } from "@/components/separator";
import { Button } from "@/components/button";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { toast } from "react-hot-toast";
import { Copy } from "lucide-react";
import {
  Webhook,
  WebhookCreatePayload,
  WebhookUpdatePayload,
  WebhookType,
  HTTPMethod,
} from "@/interfaces/webhook.interface";
import { createWebhook, updateWebhook } from "@/services/webhook";
import { getAllAgentConfigs, AgentConfig } from "@/services/api";
import { getAllAppSettings } from "@/services/appSettings";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getApiUrl } from "@/config/api";
import { AgentFormDialog } from "@/views/AIAgents/components/AgentForm";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { AppSettingDialog } from "@/views/AppSettings/components/AppSettingDialog";

interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onWebhookSaved?: () => void;
  onWebhookUpdated?: (webhook: Webhook) => void;
  mode?: "create" | "edit";
  webhookToEdit?: Webhook | null;
}

type WebhookFormValues = {
  name: string;
  url: string;
  method: HTTPMethod;
  description: string;
  secret: string;
  isActive: boolean;
  webhookType: WebhookType;
  agentId: string;
  appSettingsId: string;
};

export function WebhookDialog({
  isOpen,
  onOpenChange,
  onWebhookSaved,
  onWebhookUpdated,
  mode = "create",
  webhookToEdit,
}: Props) {
  // Dynamic headers list + the fetched option lists / loading & sub-dialog flags
  // stay in the component body; CRUDDialog owns the scalar form fields.
  const [headers, setHeaders] = useState<Record<string, string>>({});
  const [headerKey, setHeaderKey] = useState("");
  const [headerValue, setHeaderValue] = useState("");
  const [isLoadingData, setIsLoadingData] = useState(false);

  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [isCreateAgentOpen, setIsCreateAgentOpen] = useState(false);

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  const reloadAgents = async () => {
    try {
      const agentsData = await getAllAgentConfigs();
      setAgents(agentsData);
    } catch {
      toast.error("Failed to refresh agents");
    }
  };

  useEffect(() => {
    if (!isOpen) return;

    const fetchData = async () => {
      setIsLoadingData(true);
      try {
        const [agentsData, appSettingsData] = await Promise.all([
          getAllAgentConfigs(),
          getAllAppSettings(),
        ]);
        setAgents(agentsData);
        setAppSettings(appSettingsData);
      } catch {
        toast.error("Failed to load agents or app settings");
      } finally {
        setIsLoadingData(false);
      }
    };

    fetchData();

    // Initialize the dynamic headers list (CRUDDialog handles the scalar fields).
    if (mode === "edit" && webhookToEdit) {
      setHeaders(webhookToEdit.headers || {});
    } else {
      setHeaders({});
    }
    setHeaderKey("");
    setHeaderValue("");
  }, [isOpen, mode, webhookToEdit]);

  const addHeader = () => {
    if (headerKey && headerValue) {
      setHeaders((prev) => ({ ...prev, [headerKey]: headerValue }));
      setHeaderKey("");
      setHeaderValue("");
    }
  };

  const removeHeader = (key: string) => {
    const newHeaders = { ...headers };
    delete newHeaders[key];
    setHeaders(newHeaders);
  };

  return (
    <CRUDDialog<WebhookFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="550px"
      resetKey={webhookToEdit?.id ?? null}
      initialValues={{
        name: "",
        url: "",
        method: "POST",
        description: "",
        secret: "",
        isActive: true,
        webhookType: "generic",
        agentId: "",
        appSettingsId: "",
      }}
      editValues={
        webhookToEdit
          ? {
              name: webhookToEdit.name ?? "",
              url: webhookToEdit.url ?? "",
              method: webhookToEdit.method,
              description: webhookToEdit.description ?? "",
              secret: webhookToEdit.secret ?? "",
              isActive: webhookToEdit.is_active === 1,
              webhookType: webhookToEdit.webhook_type || "generic",
              agentId: webhookToEdit.agent_id ?? "",
              appSettingsId: webhookToEdit.app_settings_id ?? "",
            }
          : null
      }
      title={{ create: "Add New Webhook", edit: "Edit Webhook" }}
      submitLabel={{ create: "Create Webhook", edit: "Update Webhook" }}
      loadingLabel="Saving..."
      successMessage={{
        create: "Webhook created successfully.",
        edit: "Webhook updated successfully.",
      }}
      errorMessage={(err, m) => {
        const status = (err as { status?: number })?.status;
        return `Failed to ${m} webhook${
          status === 400 ? ": A webhook with this name already exists" : ""
        }.`;
      }}
      validate={(values) => {
        const errs: Partial<Record<keyof WebhookFormValues, string>> = {};
        if (!values.name.trim()) errs.name = "Webhook Name is required.";
        if (!values.agentId.trim()) errs.agentId = "Agent is required.";
        if (values.webhookType === "generic" && !values.secret.trim())
          errs.secret = "Secret is required.";
        return Object.keys(errs).length ? errs : null;
      }}
      onSubmit={async (values, { mode: m }) => {
        // URL is generated by backend on create, so we don't send it
        // URL is read-only in edit mode, so we don't send it in updates either
        const payload: WebhookCreatePayload | WebhookUpdatePayload = {
          name: values.name,
          method: values.webhookType === "generic" ? values.method : undefined,
          description:
            m === "edit" ? values.description : values.description || undefined,
          headers:
            m === "edit"
              ? values.webhookType === "generic"
                ? headers
                : undefined
              : values.webhookType === "generic" &&
                  Object.keys(headers).length > 0
                ? headers
                : undefined,
          is_active: values.isActive ? 1 : 0,
          secret:
            values.webhookType === "generic"
              ? values.secret || undefined
              : undefined,
          webhook_type: values.webhookType,
          agent_id: values.agentId,
          app_settings_id: values.appSettingsId || undefined,
        };

        if (m === "edit" && webhookToEdit) {
          await updateWebhook(webhookToEdit.id, payload as WebhookUpdatePayload);

          if (onWebhookUpdated) {
            const updatedWebhook: Webhook = {
              ...webhookToEdit,
              ...payload,
            };
            onWebhookUpdated(updatedWebhook);
          }
        } else {
          const baseURL = await getApiUrl();
          const body = payload as WebhookCreatePayload;
          body.base_url = baseURL;
          await createWebhook(body);

          onWebhookSaved?.();
        }
      }}
    >
      {({ values, setField, errors, mode: m }) => (
        <>
          <FormField id="name" label="Name" error={errors.name}>
            <Input
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Enter name of webhook"
            />
          </FormField>

          {m === "edit" && webhookToEdit?.url && (
            <div>
              <Label htmlFor="url">Webhook URL</Label>
              <div className="relative">
                <Input
                  id="url"
                  value={values.url}
                  readOnly
                  className="bg-muted cursor-not-allowed pr-20"
                />
                <div className="absolute top-1/2 right-2 -translate-y-1/2 flex items-center space-x-1 z-10">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 pointer-events-auto"
                    onClick={() => {
                      navigator.clipboard.writeText(values.url);
                      toast.success("Copied to clipboard.");
                    }}
                    title="Copy to clipboard"
                    disabled={!values.url}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}

          <div>
            <Label htmlFor="agent-id">Agent *</Label>
            <Select
              value={values.agentId || ""}
              onValueChange={(value) => {
                if (value === "__create__") {
                  setIsCreateAgentOpen(true);
                  return;
                }
                setField("agentId", value || "");
              }}
              disabled={isLoadingData}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select an agent" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={agent.id}>
                    {agent.name}
                  </SelectItem>
                ))}
                <CreateNewSelectItem />
              </SelectContent>
            </Select>
            {errors.agentId && (
              <p className="text-sm text-red-500 mt-1">{errors.agentId}</p>
            )}
          </div>

          <Separator className="my-1" />

          <div>
            <Label htmlFor="webhook-type">Type</Label>
            <Select
              value={values.webhookType}
              onValueChange={(value) => {
                const newType = value as WebhookType;
                setField("webhookType", newType);
                // Reset app settings ID when type changes (agent stays)
                setField("appSettingsId", "");
                // Clear secret, headers, and method when switching away from generic
                if (newType !== "generic") {
                  setField("secret", "");
                  setHeaders({});
                  setHeaderKey("");
                  setHeaderValue("");
                  setField("method", "POST");
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select webhook type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="generic">Generic</SelectItem>
                <SelectItem value="slack">Slack</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {(values.webhookType === "slack" ||
            values.webhookType === "whatsapp") && (
            <div>
              <Label htmlFor="app-settings-id">Configuration Variable</Label>
              <Select
                value={values.appSettingsId || ""}
                onValueChange={(value) => {
                  if (value === "__create__") {
                    setIsCreateSettingOpen(true);
                    return;
                  }
                  setField("appSettingsId", value || "");
                }}
                disabled={isLoadingData}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a configuration variable (optional)" />
                </SelectTrigger>
                <SelectContent>
                  {appSettings
                    .filter((setting) => {
                      const settingTypeLower = setting.type.toLowerCase();
                      const webhookTypeLower = values.webhookType.toLowerCase();
                      // Map webhook types to app setting types
                      const typeMatch =
                        (webhookTypeLower === "slack" &&
                          settingTypeLower === "slack") ||
                        (webhookTypeLower === "whatsapp" &&
                          settingTypeLower === "whatsapp");
                      return typeMatch && setting.is_active === 1;
                    })
                    .map((setting) => (
                      <SelectItem key={setting.id} value={setting.id}>
                        {setting.name}
                      </SelectItem>
                    ))}
                  <CreateNewSelectItem />
                </SelectContent>
              </Select>
            </div>
          )}

          {values.webhookType === "generic" && (
            <>
              <div>
                <Label htmlFor="method">HTTP Method</Label>
                <Select
                  value={values.method}
                  onValueChange={(value) =>
                    setField("method", value as HTTPMethod)
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="GET">GET</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <FormField id="secret" label="Secret *" error={errors.secret}>
                <Input
                  id="secret"
                  type="text"
                  value={values.secret}
                  onChange={(e) => setField("secret", e.target.value)}
                  placeholder="Enter secret"
                />
              </FormField>

              <div>
                <Label>Headers</Label>
                <div className="flex gap-2 mb-2">
                  <Input
                    placeholder="Key"
                    value={headerKey}
                    onChange={(e) => setHeaderKey(e.target.value)}
                  />
                  <Input
                    placeholder="Value"
                    value={headerValue}
                    onChange={(e) => setHeaderValue(e.target.value)}
                  />
                  <Button type="button" onClick={addHeader}>
                    Add
                  </Button>
                </div>
                <ul className="space-y-1">
                  {Object.entries(headers).map(([key, value]) => (
                    <li
                      key={key}
                      className="flex justify-between items-center text-sm border-b pb-1"
                    >
                      <span>
                        {key}: {value}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeHeader(key)}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          <Separator className="my-1" />

          <FormField id="description" label="Description">
            <Textarea
              id="description"
              value={values.description}
              onChange={(e) => setField("description", e.target.value)}
              rows={3}
              placeholder="Enter description (optional)"
            />
          </FormField>

          <div className="flex items-center space-x-2">
            <Switch
              id="is-active"
              checked={values.isActive}
              onCheckedChange={(checked) => setField("isActive", checked)}
            />
            <Label htmlFor="is-active">Active</Label>
          </div>

          {/* Create new agent dialog */}
          <AgentFormDialog
            isOpen={isCreateAgentOpen}
            onClose={() => setIsCreateAgentOpen(false)}
            data={null}
            redirectOnCreate={false}
            onCreated={async (createdAgentId) => {
              try {
                await reloadAgents();
                setField("agentId", createdAgentId);
              } catch {
                // ignore
              }
            }}
          />

          {/* Create new configuration variable dialog */}
          <AppSettingDialog
            isOpen={isCreateSettingOpen}
            onOpenChange={setIsCreateSettingOpen}
            mode="create"
            initialType={values.webhookType === "slack" ? "Slack" : "WhatsApp"}
            disableTypeSelect
            onSettingSaved={async (created) => {
              try {
                const settings = await getAllAppSettings();
                setAppSettings(settings);
              } catch {
                // ignore
              }
              if (created?.id) setField("appSettingsId", created.id);
            }}
          />
        </>
      )}
    </CRUDDialog>
  );
}

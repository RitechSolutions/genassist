import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { Eye, EyeOff, Copy } from "lucide-react";
import {
  useApiKeyDialogState,
  inferPresetFromApiKey,
} from "./ApiKeyDialogLogic";
import { ApiKey } from "@/interfaces/api-key.interface";
import { ApiRoleSelection } from "./ApiRoleSelection";
import { Switch } from "@/components/switch";
import { maskInput } from "@/helpers/utils";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  API_KEY_EXPIRY_PRESET_VALUES,
  presetToExpiresInDays,
} from "@/components/api-keys/apiKeyExpiryPresets";

interface ApiKeyDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onApiKeyCreated?: () => void;
  onApiKeyUpdated?: (apiKey: ApiKey) => void;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
}

type ApiKeyFormValues = {
  name: string;
  is_active: boolean;
  role_ids: string[];
  expiry_preset: string;
};

export function ApiKeyDialog({
  isOpen,
  onOpenChange,
  onApiKeyCreated,
  onApiKeyUpdated,
  mode = "create",
  apiKeyToEdit = null,
}: ApiKeyDialogProps) {
  const formatExpiresIn = (credentialExpiresAt?: string | null) => {
    if (!credentialExpiresAt) return null;
    const expMs = new Date(credentialExpiresAt).getTime();
    if (Number.isNaN(expMs)) return null;
    const nowMs = Date.now();
    const diffMs = expMs - nowMs;
    if (diffMs <= 0) return "Expired";

    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;

    const days = Math.floor(diffMs / day);
    const hours = Math.floor((diffMs % day) / hour);
    const minutes = Math.floor((diffMs % hour) / minute);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const {
    userId,
    availableRoles,
    loading,
    generatedKey,
    setGeneratedKey,
    isKeyVisible,
    toggleKeyVisibility,
    hasGeneratedKey,
    setHasGeneratedKey,
    copyToClipboard,
  } = useApiKeyDialogState({ isOpen, mode, apiKeyToEdit });

  // Mirrors the original `dialogMode`: treated as an edit only when there is an
  // entity to edit; otherwise the dialog behaves as a create.
  const dialogMode: "create" | "edit" =
    mode === "edit" && apiKeyToEdit ? "edit" : "create";

  const expiresInLabel =
    dialogMode === "edit"
      ? formatExpiresIn(apiKeyToEdit?.credential_expires_at ?? null)
      : null;

  return (
    <CRUDDialog<ApiKeyFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={dialogMode}
      maxWidth="500px"
      resetKey={apiKeyToEdit?.id ?? null}
      initialValues={{
        name: "",
        is_active: true,
        role_ids: [],
        expiry_preset: "never",
      }}
      editValues={
        apiKeyToEdit
          ? {
              name: apiKeyToEdit.name || "",
              is_active: apiKeyToEdit.is_active === 1,
              role_ids:
                apiKeyToEdit.roles?.map((r) => r.id) ||
                apiKeyToEdit.role_ids ||
                [],
              expiry_preset: inferPresetFromApiKey(apiKeyToEdit),
            }
          : null
      }
      title={{ create: "Generate New API Key", edit: "Edit API Key" }}
      // The generated-key reveal screen stays open after a successful create so
      // the secret can be copied; edits close on success.
      closeOnSuccess={dialogMode === "edit"}
      successMessage={{
        create: "API key created successfully.",
        edit: "API key updated successfully.",
      }}
      errorMessage={(err, m) => {
        const data = (
          err as { response?: { data?: Record<string, unknown> } }
        )?.response?.data;
        let detailMsg = "";
        if (data?.error) {
          detailMsg = String(data.error);
        } else if (data?.detail && typeof data.detail === "object") {
          const d0 = (data.detail as Record<string, { msg?: string }>)["0"];
          detailMsg = d0?.msg ?? "";
        }
        return `Failed to ${m} API key${detailMsg ? `: ${detailMsg}` : "."}`;
      }}
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      onSubmit={async (values, { mode: m }) => {
        if (m === "create") {
          if (!userId) {
            throw new Error("User information is not available.");
          }
          const expiresInDays = presetToExpiresInDays(values.expiry_preset);
          const result = await createApiKey({
            name: values.name,
            user_id: userId,
            role_ids: values.role_ids,
            is_active: values.is_active ? 1 : 0,
            ...(expiresInDays !== undefined
              ? { expires_in_days: expiresInDays }
              : {}),
          });
          setGeneratedKey(result.key_val ?? null);
          setHasGeneratedKey(true);
          onApiKeyCreated?.();
        } else {
          if (!apiKeyToEdit || !userId) {
            throw new Error("User information is not available.");
          }
          const expiresInDays = presetToExpiresInDays(values.expiry_preset);
          const updateData: Partial<ApiKey> & { role_ids?: string[] } = {
            name: values.name,
            user_id: userId,
            is_active: values.is_active ? 1 : 0,
            role_ids: values.role_ids,
            // undefined ("never") => backend expects 0 to clear/store Never.
            expires_in_days: expiresInDays ?? 0,
          };
          const updatedFromApi = await updateApiKey(apiKeyToEdit.id, updateData);
          onApiKeyUpdated?.(updatedFromApi);
        }
      }}
      footer={({ isSubmitting }) => {
        const busy = loading || isSubmitting;
        return (
          <div className="flex justify-end gap-3 w-full">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            {dialogMode === "create" && (
              <Button type="submit" disabled={busy || hasGeneratedKey}>
                {busy ? "Generating..." : "Generate Key"}
              </Button>
            )}
            {dialogMode === "edit" && (
              <Button type="submit" disabled={busy || !hasGeneratedKey}>
                {busy ? "Updating..." : "Update Key"}
              </Button>
            )}
          </div>
        );
      }}
    >
      {({ values, setField, setValues, errors, isSubmitting }) => {
        const busy = loading || isSubmitting;
        const handleToggleRole = (roleId: string) =>
          setValues((prev) => ({
            ...prev,
            role_ids: prev.role_ids.includes(roleId)
              ? prev.role_ids.filter((id) => id !== roleId)
              : [...prev.role_ids, roleId],
          }));

        return (
          <>
            <FormField id="name" label="Name" error={errors.name}>
              <Input
                id="name"
                placeholder="API Key Name"
                value={values.name}
                onChange={(e) => setField("name", e.target.value)}
                disabled={busy}
              />
            </FormField>

            <ApiRoleSelection
              availableRoles={availableRoles}
              selectedRoles={values.role_ids}
              toggleRole={handleToggleRole}
              isLoading={busy}
            />

            <div className="flex items-center gap-2">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={values.is_active}
                onCheckedChange={(checked) => setField("is_active", checked)}
              />
            </div>

            {dialogMode === "edit" ? (
              <div className="space-y-2">
                <Label>Credential expires</Label>
                <Select
                  value={values.expiry_preset}
                  onValueChange={(v) => setField("expiry_preset", v)}
                >
                  <SelectTrigger id="credential-expiry-edit">
                    <SelectValue placeholder="Expiry" />
                  </SelectTrigger>
                  <SelectContent>
                    {API_KEY_EXPIRY_PRESET_VALUES.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {apiKeyToEdit?.credential_expires_at ? (
                  <div className="text-sm">
                    {expiresInLabel ? (
                      <span>
                        Expires in{" "}
                        <span className="font-medium">{expiresInLabel}</span>
                      </span>
                    ) : (
                      <span>Expiration is set.</span>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    This key currently never expires.
                  </p>
                )}

                <p className="text-xs text-muted-foreground">
                  On rotate, expiration will be recalculated from now based on
                  this setting (unless set to Never).
                </p>
              </div>
            ) : null}

            {dialogMode === "create" && !hasGeneratedKey ? (
              <div className="space-y-2">
                <Label htmlFor="credential-expiry">Credential expires</Label>
                <Select
                  value={values.expiry_preset}
                  onValueChange={(v) => setField("expiry_preset", v)}
                >
                  <SelectTrigger id="credential-expiry">
                    <SelectValue placeholder="Expiry" />
                  </SelectTrigger>
                  <SelectContent>
                    {API_KEY_EXPIRY_PRESET_VALUES.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Key stops working after this unless rotated earlier.
                </p>
              </div>
            ) : null}

            {hasGeneratedKey && generatedKey && (
              <div className="space-y-2 mt-4">
                <Label htmlFor="generated_key">Generated API Key</Label>
                <div className="relative flex flex-row items-center">
                  <Input
                    id="generated_key"
                    value={
                      isKeyVisible ? generatedKey : maskInput(generatedKey || "")
                    }
                    readOnly
                    className="w-full z-10 pr-20"
                  />
                  <div className="absolute right-2 flex gap-1 elevation-1 z-20">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={toggleKeyVisibility}
                      title={isKeyVisible ? "Hide key" : "Show key"}
                    >
                      {isKeyVisible ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={copyToClipboard}
                      title="Copy to clipboard"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  This API key will only be shown once. Make sure to copy and
                  store it securely.
                </p>
              </div>
            )}
          </>
        );
      }}
    </CRUDDialog>
  );
}

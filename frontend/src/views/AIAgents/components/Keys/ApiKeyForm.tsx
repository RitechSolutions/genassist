import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { ApiKey } from "@/interfaces/api-key.interface";
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

interface Props {
  agentId: string;
  userId: string;
  existingKey?: ApiKey;
  open: boolean;
  onClose(): void;
  onSaved: (key: ApiKey) => void;
}

type ApiKeyFormValues = {
  name: string;
  isActive: boolean;
  expiryPreset: string;
};

export default function ApiKeyForm({
  agentId,
  userId,
  existingKey,
  open,
  onClose,
  onSaved,
}: Props) {
  return (
    <CRUDDialog<ApiKeyFormValues>
      open={open}
      onOpenChange={(next) => !next && onClose()}
      mode={existingKey ? "edit" : "create"}
      maxWidth="672px"
      resetKey={existingKey?.id ?? null}
      initialValues={{ name: "", isActive: true, expiryPreset: "never" }}
      editValues={
        existingKey
          ? { name: existingKey.name, isActive: existingKey.is_active === 1 }
          : null
      }
      title={{ create: "New API Key", edit: "Edit API Key" }}
      description={{
        create: "Create a new API key",
        edit: "Update the API key details",
      }}
      submitLabel="Save"
      loadingLabel="Saving…"
      successMessage={{
        create: "API key generated successfully.",
        edit: "API key updated successfully.",
      }}
      errorMessage={(err, m) =>
        `Failed to ${m === "create" ? "create" : "update"} API key${
          (err as { status?: number })?.status === 400
            ? ": An API key with this name already exists"
            : ""
        }.`
      }
      onSubmit={async (values, { mode: m }) => {
        let saved: ApiKey;
        if (m === "edit" && existingKey) {
          saved = await updateApiKey(existingKey.id, {
            name: values.name,
            is_active: values.isActive ? 1 : 0,
            user_id: userId,
            agent_id: agentId,
          });
        } else {
          const expiresInDays = presetToExpiresInDays(values.expiryPreset);
          saved = await createApiKey({
            name: values.name,
            is_active: values.isActive ? 1 : 0,
            user_id: userId,
            role_ids: [],
            agent_id: agentId,
            ...(expiresInDays !== undefined
              ? { expires_in_days: expiresInDays }
              : {}),
          });
        }
        onSaved(saved);
      }}
    >
      {({ values, setField, mode: m }) => (
        <>
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <RichInput
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
            />
          </div>

          {m === "create" ? (
            <div className="space-y-2">
              <Label htmlFor="credential-expiry">Credential expires</Label>
              <Select
                value={values.expiryPreset}
                onValueChange={(v) => setField("expiryPreset", v)}
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

          <div className="flex items-center gap-2">
            <Label htmlFor="is_active">Active</Label>
            <Switch
              id="is_active"
              checked={values.isActive}
              onCheckedChange={(checked) => setField("isActive", checked)}
            />
          </div>
        </>
      )}
    </CRUDDialog>
  );
}

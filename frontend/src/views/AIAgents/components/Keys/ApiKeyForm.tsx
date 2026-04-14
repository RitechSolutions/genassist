import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { ApiKey } from "@/interfaces/api-key.interface";
import toast from "react-hot-toast";
import { Copy, Eye, EyeOff } from "lucide-react";
import { maskInput } from "@/helpers/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

export default function ApiKeyForm({
  agentId,
  userId,
  existingKey,
  open,
  onClose,
  onSaved,
}: Props) {
  const [name, setName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isKeyVisible, setIsKeyVisible] = useState(false);
  const toggleKeyVisibility = () => setIsKeyVisible((v) => !v);
  const [expiryPreset, setExpiryPreset] = useState<string>("never");

  useEffect(() => {
    if (existingKey) {
      setName(existingKey.name);
      setIsActive(existingKey.is_active === 1);
      setIsKeyVisible(false);
    } else {
      setName("");
      setIsActive(true);
      setExpiryPreset("never");
    }
  }, [existingKey, open]);

  async function handleSubmit() {
    setSaving(true);
    try {
      let saved: ApiKey;
      if (existingKey) {
        saved = await updateApiKey(existingKey.id, {
          name,
          is_active: isActive ? 1 : 0,
          user_id: userId,
          agent_id: agentId,
        });
        toast.success("API key updated successfully.");
      } else {
        const expiresInDays = presetToExpiresInDays(expiryPreset);
        saved = await createApiKey({
          name,
          is_active: isActive ? 1 : 0,
          user_id: userId,
          role_ids: [],
          agent_id: agentId,
          ...(expiresInDays !== undefined ? { expires_in_days: expiresInDays } : {}),
        });
        toast.success("API key generated successfully.");
      }
      onSaved(saved);
      onClose();
    } catch (error) {
      toast.error(
        `Failed to ${existingKey ? "update" : "create"} API key${
          error.status === 400
            ? ": An API key with this name already exists"
            : ""
        }.`
      );
    } finally {
      setSaving(false);
    }
  }

  const copyToClipboard = () => {
    if (!existingKey?.key_val) return;
    navigator.clipboard.writeText(existingKey.key_val);
    toast.success("API key copied to clipboard.");
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{existingKey ? "Edit" : "New"} API Key</DialogTitle>
            <DialogDescription>
              {existingKey
                ? "Update the API key details"
                : "Create a new API key"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            {!existingKey ? (
              <div className="space-y-2">
                <Label htmlFor="credential-expiry">Credential expires</Label>
                <Select value={expiryPreset} onValueChange={setExpiryPreset}>
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

            {existingKey?.key_val && (
              <div className="space-y-2">
                <Label htmlFor="api_key">API Key</Label>
                <div className="relative flex flex-row items-center">
                  <Input
                    id="api_key"
                    readOnly
                    className="w-full z-10"
                    value={
                      isKeyVisible
                        ? existingKey.key_val
                        : maskInput(existingKey.key_val || "")
                    }
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
              </div>
            )}

            <div className="flex items-center gap-2">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

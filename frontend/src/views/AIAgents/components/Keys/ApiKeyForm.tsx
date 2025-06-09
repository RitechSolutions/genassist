import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { ApiKey } from "@/interfaces/api-key.interface";
import toast from "react-hot-toast";
import { Copy, Eye, EyeOff } from "lucide-react";

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

  useEffect(() => {
    if (existingKey) {
      setName(existingKey.name);
      setIsActive(existingKey.is_active === 1);
      setIsKeyVisible(false);
    } else {
      setName("");
      setIsActive(true);
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
        });
        toast.success("API key updated.");
      } else {
        saved = await createApiKey({
          name,
          is_active: isActive ? 1 : 0,
          user_id: userId,
          role_ids: [],
        });
        toast.success("API key generated! Copy it below.");
      }
      onSaved(saved);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  const copyToClipboard = () => {
    if (!existingKey?.key_val) return;
    navigator.clipboard.writeText(existingKey.key_val);
    toast.success("API key has been copied to clipboard");
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{existingKey ? "Edit" : "New"} API Key</DialogTitle>
        </DialogHeader>
        <Label>Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} />

        {existingKey?.key_val && (
          <div className="space-y-1">
            <Label htmlFor="api_key">API Key</Label>
            <div className="relative">
              <Input
                id="api_key"
                readOnly
                className="pr-20"
                value={
                  isKeyVisible
                    ? existingKey.key_val
                    : existingKey.key_val.replace(/./g, "•")
                }
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-2">
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

        <Label>Active</Label>
        <Switch checked={isActive} onCheckedChange={setIsActive} />
        <Button onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

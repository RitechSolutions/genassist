import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { ApiKey } from "@/interfaces/api-key.interface";

interface Props {
  agentId: string;
  userId: string;
  existingKey?: ApiKey;
  open: boolean;
  onClose(): void;
  onSaved: (key: ApiKey) => void;
}

export default function ApiKeyForm({ agentId, userId, existingKey, open, onClose, onSaved }: Props) {
  const [name, setName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (existingKey) {
      setName(existingKey.name);
      setIsActive(existingKey.is_active === 1);
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
      } else {
        saved = await createApiKey({
          name,
          is_active: isActive ? 1 : 0,
          user_id: userId,
          role_ids: [],
        });
      }
      onSaved(saved);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{existingKey ? "Edit" : "New"} API Key</DialogTitle>
        </DialogHeader>
        <Label>Name</Label>
        <Input value={name} onChange={e => setName(e.target.value)} />
        <Label>Active</Label>
        <Switch checked={isActive} onCheckedChange={setIsActive} />
        <Button onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

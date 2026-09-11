import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { createTemplateFromAgent } from "@/services/templates";

interface SaveAsTemplateDialogProps {
  agent: { id: string; name: string } | null;
  onClose: () => void;
  onSaved?: () => void;
}

export function SaveAsTemplateDialog({
  agent,
  onClose,
  onSaved,
}: SaveAsTemplateDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (agent) {
      setTitle(agent.name ? `${agent.name} Template` : "");
      setDescription("");
      setCategory("");
    }
  }, [agent]);

  const handleSave = async () => {
    if (!agent || !title.trim()) return;
    setSaving(true);
    try {
      await createTemplateFromAgent({
        agent_id: agent.id,
        title: title.trim(),
        description: description.trim() || undefined,
        category: category.trim() || undefined,
      });
      toast.success("Saved as template");
      onSaved?.();
      onClose();
    } catch {
      toast.error("Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={!!agent}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save as template</DialogTitle>
          <DialogDescription>
            Save this agent&apos;s workflow as a reusable template. LLM provider,
            knowledge base, and secret values are removed — whoever installs it
            picks their own via the setup wizard.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="tmpl-title">Title</Label>
            <Input
              id="tmpl-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Support Assistant"
              maxLength={120}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="tmpl-desc">Description</Label>
            <Textarea
              id="tmpl-desc"
              size="body"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this template do?"
              maxLength={500}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="tmpl-cat">Category</Label>
            <Input
              id="tmpl-cat"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Customer Support"
              maxLength={60}
            />
          </div>
        </div>

        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !title.trim()}>
            {saving ? "Saving…" : "Save template"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

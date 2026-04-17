import { useEffect, useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ApiKey } from "@/interfaces/api-key.interface";
import { rotateApiKey } from "@/services/apiKeys";
import toast from "react-hot-toast";

export type RotateApiKeyTarget = { key: ApiKey; overlap: string };

interface RotateApiKeyDialogProps {
  open: boolean;
  target: RotateApiKeyTarget | null;
  onOpenChange: (open: boolean) => void;
  onRotated: (saved: ApiKey) => void;
}

export function RotateApiKeyDialog({
  open,
  target,
  onOpenChange,
  onRotated,
}: RotateApiKeyDialogProps) {
  const [overlap, setOverlap] = useState("0");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (target) {
      setOverlap(target.overlap);
    }
  }, [target]);

  async function handleConfirm() {
    if (!target) return;
    setSaving(true);
    try {
      const overlapSec = Number.parseInt(overlap, 10);
      const saved = await rotateApiKey(
        target.key.id,
        Number.isFinite(overlapSec) ? overlapSec : 0
      );
      toast.success(
        overlapSec > 0
          ? "New secret issued. The previous secret remains valid until the overlap ends."
          : "New secret issued. Copy it now; the previous secret no longer works."
      );
      onRotated(saved);
      onOpenChange(false);
    } catch {
      toast.error("Failed to rotate API key.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setSaving(false);
        }
        onOpenChange(next);
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Rotate API key secret</AlertDialogTitle>
          <AlertDialogDescription>
            A new secret will be shown once. Choose whether the previous secret
            stays valid for a short overlap while you update integrations.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {target ? (
          <div className="space-y-2 py-2">
            <Label htmlFor="rotate-overlap">Overlap window</Label>
            <Select value={overlap} onValueChange={setOverlap}>
              <SelectTrigger id="rotate-overlap">
                <SelectValue placeholder="Overlap" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">None — old secret stops immediately</SelectItem>
                <SelectItem value="3600">1 hour</SelectItem>
                <SelectItem value="86400">24 hours</SelectItem>
                <SelectItem value="604800">7 days (max)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel type="button" disabled={saving}>
            Cancel
          </AlertDialogCancel>
          <Button
            type="button"
            disabled={saving || !target}
            onClick={() => void handleConfirm()}
          >
            {saving ? "Rotating…" : "Rotate key"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

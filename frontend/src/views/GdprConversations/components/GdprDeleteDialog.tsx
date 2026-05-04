import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";
import { Button } from "@/components/button";
import { GdprDeleteMode } from "@/services/gdprConversations";

interface GdprDeleteDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (mode: GdprDeleteMode) => Promise<void>;
  isInProgress: boolean;
  conversationId: string | null;
  conversationCount?: number | null;
  defaultMode?: GdprDeleteMode;
  hardDeleteBlockedCount?: number;
}

const MODE_OPTIONS: {
  value: GdprDeleteMode;
  label: string;
  description: string;
}[] = [
  {
    value: "soft",
    label: "Soft delete (recommended)",
    description:
      "Hide the conversation everywhere and immediately remove the captured email/name PII. Reversible by an admin while the row still exists on disk.",
  },
  {
    value: "anonymize",
    label: "Anonymize in place",
    description:
      "Keep the conversation row visible (analytics drilldowns continue to work), redact PII inside the transcript text, and stamp the redaction timestamp.",
  },
  {
    value: "hard",
    label: "Hard delete",
    description:
      "Permanently remove the conversation and its messages. Already-aggregated analytics counts are unaffected. Not reversible.",
  },
];

export function GdprDeleteDialog({
  isOpen,
  onOpenChange,
  onConfirm,
  isInProgress,
  conversationId,
  conversationCount,
  defaultMode = "soft",
  hardDeleteBlockedCount = 0,
}: GdprDeleteDialogProps) {
  const [mode, setMode] = useState<GdprDeleteMode>(defaultMode);

  useEffect(() => {
    if (isOpen) setMode(defaultMode);
  }, [isOpen, defaultMode]);

  const handleConfirm = async () => {
    await onConfirm(mode);
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <div className="relative">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="absolute right-0 top-0 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {conversationCount && conversationCount > 1
                ? "Delete conversations for GDPR?"
                : "Delete conversation for GDPR?"}
            </AlertDialogTitle>
            <AlertDialogDescription className="pb-2">
              {conversationCount && conversationCount > 1 ? (
                <>
                  Choose how these conversations{" "}
                  (<span className="font-medium">{conversationCount}</span> selected) should be
                  erased. The action is logged for auditing.
                </>
              ) : (
                <>
                  Choose how this conversation
                  {conversationId ? (
                    <>
                      {" "}
                      (
                      <span className="font-mono text-xs">
                        {conversationId.slice(-8)}
                      </span>
                      )
                    </>
                  ) : null}{" "}
                  should be erased. The action is logged for auditing.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2 py-2">
            {MODE_OPTIONS.map((option) => {
              const isSelected = mode === option.value;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-input hover:bg-muted/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="gdpr-delete-mode"
                    value={option.value}
                    checked={isSelected}
                    onChange={() => setMode(option.value)}
                    className="mt-1 h-4 w-4 shrink-0 accent-primary"
                  />
                  <div className="min-w-0 space-y-0.5">
                    <div className="text-sm font-medium">{option.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {option.description}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>

          {mode === "hard" && hardDeleteBlockedCount > 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {hardDeleteBlockedCount} finalized conversation
              {hardDeleteBlockedCount === 1 ? "" : "s"} selected. Finalized conversations cannot be
              hard-deleted and will be skipped.
            </div>
          ) : null}

          <AlertDialogFooter>
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isInProgress}
            >
              Cancel
            </Button>
            <Button
              variant={mode === "hard" ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={isInProgress}
            >
              {isInProgress && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "hard" ? "Permanently delete" : "Delete"}
            </Button>
          </AlertDialogFooter>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}

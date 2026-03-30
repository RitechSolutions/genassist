import { useState, useEffect } from "react";
import { Loader2, X } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";

interface ConfirmDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
  isInProgress: boolean;
  primaryButtonText?: string;
  secondaryButtonText?: string;
  onCancel?: () => void;
  itemName?: string;
  title?: string;
  description?: string;
  requireConfirmText?: string;
}

export function ConfirmDialog({
  isOpen,
  onOpenChange,
  onConfirm,
  isInProgress,
  primaryButtonText = "Delete",
  secondaryButtonText = "Cancel",
  onCancel = () => {},
  itemName = "",
  title = "Are you sure?",
  description,
  requireConfirmText,
}: ConfirmDialogProps) {
  const [confirmInput, setConfirmInput] = useState("");

  useEffect(() => {
    if (!isOpen) setConfirmInput("");
  }, [isOpen]);

  const defaultDescription = `This action cannot be undone. This will permanently delete "${itemName}".`;
  const confirmBlocked = !!requireConfirmText && confirmInput !== requireConfirmText;
  // const confirmButton = isDeleteDialog ? "Delete" : "Save";
  // const clickedConfirmButton = isDeleteDialog ? "Deleting..." : "Saving...";
  // const cancelButton = isDeleteDialog ? "Cancel" : "Discard";
  const confirmButtonClassName =
    primaryButtonText === "Delete"
      ? "bg-red-600 hover:bg-red-700 focus:ring-red-600"
      : "bg-blue-600 hover:bg-blue-700 focus:ring-blue-600";

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
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>
              {description || defaultDescription}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {requireConfirmText && (
            <div className="my-3 space-y-1.5">
              <p className="text-sm text-muted-foreground">
                Type <span className="font-semibold text-foreground">{requireConfirmText}</span> to confirm.
              </p>
              <input
                type="text"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder={requireConfirmText}
              />
            </div>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel onClick={onCancel} disabled={isInProgress}>
              {secondaryButtonText}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={onConfirm}
              disabled={isInProgress || confirmBlocked}
              className={confirmButtonClassName}
            >
              {isInProgress && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {primaryButtonText}
            </AlertDialogAction>
          </AlertDialogFooter>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}

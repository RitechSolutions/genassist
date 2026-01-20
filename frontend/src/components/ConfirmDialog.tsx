import { Loader2 } from "lucide-react";
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
}: ConfirmDialogProps) {
  const defaultDescription = `This action cannot be undone. This will permanently delete "${itemName}".`;
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
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            {description || defaultDescription}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel} disabled={isInProgress}>
            {secondaryButtonText}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isInProgress}
            className={confirmButtonClassName}
          >
            {isInProgress && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {primaryButtonText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

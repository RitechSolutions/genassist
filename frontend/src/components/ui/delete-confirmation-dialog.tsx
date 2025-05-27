import React from "react";
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

interface DeleteConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void> | void;
  isDeleting: boolean;
  title?: string;
  description?: string;
  itemName?: string;
  confirmButtonText?: string;
  cancelButtonText?: string;
  loadingText?: string;
}

export function DeleteConfirmationDialog({
  open,
  onOpenChange,
  onConfirm,
  isDeleting,
  title = "Are you sure?",
  description = "This action cannot be undone.",
  itemName,
  confirmButtonText = "Delete",
  cancelButtonText = "Cancel",
  loadingText = "Deleting..."
}: DeleteConfirmationDialogProps) {
  const itemText = itemName ? `"${itemName}"` : "this item";
  const completeDescription = itemName 
    ? `${description} This will permanently delete ${itemText}.`
    : description;

  const handleConfirm = async () => {
    try {
      await onConfirm();
    } catch (error) {
      console.error("Error in delete operation:", error);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            {completeDescription}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>{cancelButtonText}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {loadingText}
              </>
            ) : (
              confirmButtonText
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
} 
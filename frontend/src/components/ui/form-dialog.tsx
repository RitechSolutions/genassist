import React, { ReactNode } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/dialog";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";

interface FormDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (e: React.FormEvent) => Promise<void> | void;
  title: string;
  description?: string;
  children: ReactNode;
  submitButtonText?: string;
  cancelButtonText?: string;
  isLoading?: boolean;
  loadingText?: string;
  maxWidth?: string;
}

export function FormDialog({
  isOpen,
  onOpenChange,
  onSubmit,
  title,
  description,
  children,
  submitButtonText = "Save Changes",
  cancelButtonText = "Cancel",
  isLoading = false,
  loadingText = "Saving...",
  maxWidth = "550px"
}: FormDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className={`sm:max-w-[${maxWidth}] p-0 overflow-hidden`}>
        <form onSubmit={onSubmit}>
          <DialogHeader className="p-6">
            <DialogTitle className="text-xl">{title}</DialogTitle>
            {description ? (
              <DialogDescription>{description}</DialogDescription>
            ) : null}
          </DialogHeader>
          
          <div className="px-6 pb-6 space-y-5 max-h-[calc(90vh-160px)] overflow-y-auto">
            {children}
          </div>
          
          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button 
                type="button" 
                variant="outline" 
                className="px-4"
                onClick={() => onOpenChange(false)}
                disabled={isLoading}
              >
                {cancelButtonText}
              </Button>
              <Button 
                type="submit" 
                disabled={isLoading}
                className="px-4 bg-blue-600 hover:bg-blue-700"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {loadingText}
                  </>
                ) : (
                  submitButtonText
                )}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
} 
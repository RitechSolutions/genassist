import { useState } from "react";
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
import { Checkbox } from "@/components/checkbox";
import { Label } from "@/components/label";
import { deleteLocalFineTuneJobFiles } from "@/services/localFineTune";
import { toast } from "react-hot-toast";

interface LocalFineTuneDeleteFilesDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
  jobDisplayName: string;
  onDeleted?: () => void;
}

export function LocalFineTuneDeleteFilesDialog({
  isOpen,
  onOpenChange,
  jobId,
  jobDisplayName,
  onDeleted,
}: LocalFineTuneDeleteFilesDialogProps) {
  const [deleteDataFiles, setDeleteDataFiles] = useState(true);
  const [deleteCheckpoints, setDeleteCheckpoints] = useState(true);
  const [deleteModel, setDeleteModel] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const nothingSelected = !deleteDataFiles && !deleteCheckpoints && !deleteModel;

  const handleConfirm = async () => {
    if (nothingSelected) return;
    try {
      setIsDeleting(true);
      const result = await deleteLocalFineTuneJobFiles(jobId, {
        delete_data_files: deleteDataFiles,
        delete_checkpoints: deleteCheckpoints,
        delete_model: deleteModel,
      });
      if (result.status === "failed") {
        toast.error(result.message || "Cleanup failed");
      } else if (result.status === "no_files") {
        toast.success("No files found to clean up");
      } else {
        toast.success(result.message || "Files deleted successfully");
      }
      onDeleted?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        "Failed to delete files";
      toast.error(message);
    } finally {
      setIsDeleting(false);
    }
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
            <AlertDialogTitle>Delete job files</AlertDialogTitle>
            <AlertDialogDescription>
              Select which files to delete for{" "}
              <span className="font-medium text-foreground">{jobDisplayName}</span>.
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="my-4 space-y-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="delete-data-files"
                checked={deleteDataFiles}
                onCheckedChange={(checked) => setDeleteDataFiles(Boolean(checked))}
                className="mt-0.5"
              />
              <Label htmlFor="delete-data-files" className="cursor-pointer leading-none">
                <span className="font-medium">Training / validation files</span>
                <p className="text-xs text-muted-foreground font-normal mt-0.5">
                  Downloaded data files used for training
                </p>
              </Label>
            </div>
            <div className="flex items-start gap-3">
              <Checkbox
                id="delete-checkpoints"
                checked={deleteCheckpoints}
                onCheckedChange={(checked) => setDeleteCheckpoints(Boolean(checked))}
                className="mt-0.5"
              />
              <Label htmlFor="delete-checkpoints" className="cursor-pointer leading-none">
                <span className="font-medium">Checkpoints</span>
                <p className="text-xs text-muted-foreground font-normal mt-0.5">
                  Intermediate checkpoints saved during training
                </p>
              </Label>
            </div>
            <div className="flex items-start gap-3">
              <Checkbox
                id="delete-model"
                checked={deleteModel}
                onCheckedChange={(checked) => setDeleteModel(Boolean(checked))}
                className="mt-0.5"
              />
              <Label htmlFor="delete-model" className="cursor-pointer leading-none">
                <span className="font-medium text-destructive">Fine-tuned model</span>
                <p className="text-xs text-muted-foreground font-normal mt-0.5">
                  The output model — cannot be recovered if deleted
                </p>
              </Label>
            </div>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirm}
              disabled={isDeleting || nothingSelected}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete files
            </AlertDialogAction>
          </AlertDialogFooter>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
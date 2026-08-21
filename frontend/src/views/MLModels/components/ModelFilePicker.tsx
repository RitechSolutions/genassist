import React, { useRef, useState } from "react";
import { toast } from "react-hot-toast";
import { Download, FileCode, Upload, X } from "lucide-react";

import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { downloadFileManagerFile } from "@/services/fileManager";
import { formatFileSize } from "../helpers/pipelineRuns";

export interface ModelFilePickerProps {
  pendingFile: File | null;
  existingPath: string | null;
  existingFileId: string | null;
  modelName: string;
  onSelect: (file: File | null) => void;
  onRemoveExisting: () => void;
}

/**
 * Drag-and-drop (or click) picker for the model's `.pkl` file, with a clear
 * "current file" row so editing a model shows what is already attached.
 */
export const ModelFilePicker: React.FC<ModelFilePickerProps> = ({
  pendingFile,
  existingPath,
  existingFileId,
  modelName,
  onSelect,
  onRemoveExisting,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const hasExistingFile = !!existingPath || !!existingFileId;

  const accept = (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pkl")) {
      toast.error("Only .pkl files are supported.");
      return;
    }
    onSelect(file);
  };

  const handleDownload = async () => {
    try {
      await downloadFileManagerFile(existingFileId as string, `${modelName || "model"}.pkl`);
    } catch {
      toast.error("Failed to download model file.");
    }
  };

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed px-4 py-5 text-center transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/50"
        )}
      >
        <Upload className="h-6 w-6 text-muted-foreground" />
        <span className="text-sm font-medium">
          {hasExistingFile || pendingFile ? "Replace model file" : "Upload a .pkl file"}
        </span>
        <span className="text-xs text-muted-foreground">
          Drag and drop, or click to browse. Optional.
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".pkl"
          className="hidden"
          onChange={(e) => {
            accept(e.target.files?.[0]);
            // Allow re-picking the same file after a removal.
            e.target.value = "";
          }}
        />
      </div>

      {pendingFile ? (
        <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/50 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm">{pendingFile.name}</span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatFileSize(pendingFile.size)}
            </span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            aria-label="Remove selected file"
            onClick={() => onSelect(null)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ) : hasExistingFile ? (
        <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/50 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm">
              {existingFileId ? `${modelName || "model"}.pkl` : existingPath}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground">Current file</span>
          </div>
          <div className="flex shrink-0 items-center">
            {existingFileId && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Download model file"
                onClick={handleDownload}
              >
                <Download className="h-4 w-4" />
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label="Detach model file"
              onClick={onRemoveExisting}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
};

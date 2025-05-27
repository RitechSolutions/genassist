import React from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { File, Plus, Trash2, Upload } from "lucide-react";

export interface FileItem {
  id: string;
  name: string;
  size?: string;
  type?: string;
}

interface FileUploadFieldProps {
  files: FileItem[];
  onAddFile: () => void;
  onRemoveFile: (fileId: string) => void;
  label?: string;
  className?: string;
}

export function FileUploadField({
  files,
  onAddFile,
  onRemoveFile,
  label = "Files",
  className = "",
}: FileUploadFieldProps) {
  return (
    <div className={className}>
      <div className="flex justify-between items-center mb-1.5">
        <Label className="text-sm font-medium">{label}</Label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 px-2"
          onClick={onAddFile}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add file
        </Button>
      </div>

      <div className="border border-dashed rounded-xl py-10 flex justify-center items-center mb-3">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <Upload className="w-4 h-4" />
          <span>Upload files</span>
        </div>
      </div>

      <div className="space-y-2">
        {files.map((file) => (
          <div
            key={file.id}
            className="flex items-center justify-between rounded-xl border px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <File className="h-5 w-5 text-gray-600" />
              <div>
                <p className="text-sm font-medium text-gray-900 truncate max-w-[180px]">
                  {file.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {file.type || '.pdf'} · {file.size || '0.2MB'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemoveFile(file.id)}
              className="h-8 w-8 flex items-center justify-center rounded-full bg-white border text-red-600 hover:bg-red-50"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
} 
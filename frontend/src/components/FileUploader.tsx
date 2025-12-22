import React, { useState } from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { FileText, Upload, X } from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { uploadFiles } from "@/services/api";

export interface FileUploaderProps {
  label: string;
  acceptedFileTypes?: string[]; // ex: [".json", ".yaml"]
  initialOriginalFileName?: string;
  initialServerFilePath?: string;
  onUploadComplete?: (result: {
    file_path: string;
    original_filename: string;
  }) => void;
  onRemove?: () => void;
  placeholder?: string;
}

export const FileUploader: React.FC<FileUploaderProps> = ({
  label,
  acceptedFileTypes,
  initialServerFilePath = "",
  initialOriginalFileName = "",
  onUploadComplete,
  onRemove,
  placeholder = "Select a file to upload",
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [originalFileName, setOriginalFileName] = useState(
    initialOriginalFileName
  );
  const [serverFilePath, setServerFilePath] = useState(initialServerFilePath);
  const [isUploading, setIsUploading] = useState(false);
  const { toast } = useToast();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (acceptedFileTypes && acceptedFileTypes.length > 0) {
      const fileExtension =
        "." + selectedFile.name.split(".").pop()?.toLowerCase();
      const isValidExtension = acceptedFileTypes.some(
        (ext) => fileExtension === ext.toLowerCase()
      );

      if (!isValidExtension) {
        toast({
          title: "Invalid file type",
          description: `Please upload a file with one of these extensions: ${acceptedFileTypes.join(
            ", "
          )}`,
          variant: "destructive",
        });
        e.target.value = ""; // Reset input
        return;
      }
    }

    setFile(selectedFile);
    uploadFile(selectedFile);
    e.target.value = ""; // Reset input to allow selecting the same file again or different files
  };

  const handleRemoveFile = () => {
    setFile(null);
    setOriginalFileName("");
    setServerFilePath("");
    onRemove?.();
  };

  const uploadFile = async (
    fileToUpload?: File
  ): Promise<{
    file_path: string;
    original_filename: string;
  } | null> => {
    const targetFile = fileToUpload || file;
    if (!targetFile) return null;

    setIsUploading(true);

    try {
      const result = (await uploadFiles([targetFile])) as Array<{
        file_path: string;
        original_filename: string;
      }>;

      const uploadResult = {
        file_path: result[0].file_path,
        original_filename: result[0].original_filename,
      };

      setServerFilePath(uploadResult.file_path);
      setOriginalFileName(uploadResult.original_filename);
      onUploadComplete?.(uploadResult);
      return uploadResult;
    } catch (error) {
      // Clear the failed file from state
      setFile(null);

      toast({
        title: "Upload Error",
        description: `Failed to upload file: ${
          error instanceof Error ? error.message : String(error)
        }`,
        variant: "destructive",
      });
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      {label && <Label htmlFor="file">{label}</Label>}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="file"
          className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md p-6 cursor-pointer hover:border-primary/50 transition-colors"
        >
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-10 w-10 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">
              {file ? file.name : serverFilePath ? "Replace file" : placeholder}
            </span>
          </div>
          <input
            id="file"
            type="file"
            accept={acceptedFileTypes?.join(",")}
            onChange={handleFileChange}
            disabled={isUploading}
            className="hidden"
          />
        </label>

        {file && (
          <div className="flex items-center justify-between p-2 bg-muted rounded-md">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm">
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={handleRemoveFile}
              className="h-8 w-8"
              disabled={isUploading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {serverFilePath && !file && (
          <div className="flex items-center justify-between p-2 bg-muted rounded-md">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm">
                File: {originalFileName || "File uploaded"}
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={handleRemoveFile}
              className="h-8 w-8"
              disabled={isUploading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {isUploading && (
          <div className="p-2 text-sm text-muted-foreground">
            Uploading file... Please wait.
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { FileText, Upload, X, Download } from 'lucide-react';
import { uploadFiles } from '@/services/api';
import { UploadFileResponse } from '@/interfaces/file-manager.interface';
import { downloadFile, getFileDownloadUrl } from '@/helpers/utils';
import { getApiUrlString } from '@/config/api';
import toast from "react-hot-toast";

export interface FileUploaderProps {
  label: string;
  acceptedFileTypes?: string[]; // ex: [".json", ".yaml"]
  initialOriginalFileName?: string;
  initialServerFilePath?: string;
  initialServerFileUrl?: string;
  onUploadComplete?: (result: UploadFileResponse) => void;
  onRemove?: () => void;
  placeholder?: string;
}

export const FileUploader: React.FC<FileUploaderProps> = ({
  label,
  acceptedFileTypes,
  initialOriginalFileName = '',
  initialServerFilePath,
  initialServerFileUrl,
  onUploadComplete,
  onRemove,
  placeholder = 'Select a file to upload',
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [originalFileName, setOriginalFileName] = useState(initialOriginalFileName);
  const [serverFilePath, setServerFilePath] = useState<string | undefined>(initialServerFilePath);
  const [serverFileUrl, setServerFileUrl] = useState<string | undefined>(initialServerFileUrl);
  const [isUploading, setIsUploading] = useState(false);

  const handleDownload = (e: React.MouseEvent, isFileUrl: boolean = false) => {
    e.stopPropagation();

    // show error toast
    const showError = (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Failed to download file');
    };

    if (isFileUrl) {
      // Use the tenant-aware download behavior
      try {
        const match = serverFileUrl.match(/file-manager\/files\/([^/]+)/);
        if (match?.[1]) {
          const tenantId = localStorage.getItem('tenant_id') || '';
          const fileUrl = getFileDownloadUrl(match[1], getApiUrlString, tenantId, 'source');
          downloadFile(fileUrl, originalFileName || 'file');
        }
      } catch (err) {
        showError(err);
      }
    } else {
      try {
        downloadFile(serverFilePath, originalFileName || 'file');
      } catch (err) {
        showError(err);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (acceptedFileTypes && acceptedFileTypes.length > 0) {
      const fileExtension = '.' + selectedFile.name.split('.').pop()?.toLowerCase();
      const isValidExtension = acceptedFileTypes.some((ext) => fileExtension === ext.toLowerCase());

      if (!isValidExtension) {
        toast.error(`Please upload a file with one of these extensions: ${acceptedFileTypes.join(', ')}`, {
          duration: 5000,
          position: 'top-center',
        });
        e.target.value = ''; // Reset input
        return;
      }
    }

    setFile(selectedFile);
    uploadFile(selectedFile);
    e.target.value = ''; // Reset input to allow selecting the same file again or different files
  };

  const handleRemoveFile = () => {
    setFile(null);
    setOriginalFileName('');
    setServerFilePath('');
    setServerFileUrl('');
    onRemove?.();
  };

  const uploadFile = async (
    fileToUpload?: File
  ): Promise<
    | ({
        file_path?: string;
        original_filename?: string;
      } & UploadFileResponse)
    | null
  > => {
    const targetFile = fileToUpload || file;
    if (!targetFile) return null;

    setIsUploading(true);

    try {
      const result = await uploadFiles([targetFile]);
      if (result.length > 0) {
        const fileResponse = result[0];
        // based on the file response and file manager service, set the server file path and url
        setServerFilePath(fileResponse?.file_path);
        setServerFileUrl(fileResponse?.file_url);

        setOriginalFileName(fileResponse.original_filename);
        onUploadComplete?.(fileResponse);
        return fileResponse;
      }
    } catch (error) {
      // Clear the failed file from state
      setFile(null);
      toast.error(` Failed to upload file: ${error instanceof Error ? error.message : String(error)}`);
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
              {file ? file.name : serverFileUrl || serverFilePath ? 'Replace file' : placeholder}
            </span>
          </div>
          <input
            id="file"
            type="file"
            accept={acceptedFileTypes?.join(',')}
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

        {serverFileUrl && !file && (
          <div className="flex items-center justify-between p-2 bg-muted rounded-md">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm">{originalFileName || 'File uploaded'}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="text-primary hover:text-primary/80"
                onClick={(e) => handleDownload(e, true)}
                disabled={isUploading}
              >
                <Download className="h-4 w-4" />
              </button>
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
          </div>
        )}

        {serverFilePath && !file && !serverFileUrl && (
          <div className="flex items-center justify-between p-2 bg-muted rounded-md">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm">File: {originalFileName || 'File uploaded'}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="text-primary hover:text-primary/80"
                onClick={(e) => handleDownload(e)}
                disabled={isUploading}
                aria-label="Download file"
              >
                <Download className="h-4 w-4" />
              </button>
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
          </div>
        )}

        {isUploading && <div className="p-2 text-sm text-muted-foreground">Uploading file... Please wait.</div>}
      </div>
    </div>
  );
};

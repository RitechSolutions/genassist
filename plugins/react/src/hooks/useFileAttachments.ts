import { useState, useRef, useEffect } from 'react';
import { Attachment, AttachmentWithFile } from '../types';
import { uploadFailureToast } from '../utils/sendFailure';

interface UseFileAttachmentsOptions {
  /** Uploads a file; `rejected` means the server refused its type (vs. the upload failing). */
  uploadAttachment: (file: File) => Promise<{ attachment: Attachment | null; rejected: boolean }>;
  t: (key: string, fallback?: string) => string;
}

export function useFileAttachments({ uploadAttachment, t }: UseFileAttachmentsOptions) {
  const [attachments, setAttachments] = useState<AttachmentWithFile[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set());
  const [fileErrorToast, setFileErrorToast] = useState<string | null>(null);
  const fileErrorToastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (fileErrorToastTimeoutRef.current) {
        clearTimeout(fileErrorToastTimeoutRef.current);
      }
    };
  }, []);

  /** Shows a short-lived error under the composer (failed uploads, failed screenshots). */
  const showFileError = (message: string) => {
    if (fileErrorToastTimeoutRef.current) {
      clearTimeout(fileErrorToastTimeoutRef.current);
    }
    setFileErrorToast(message);
    fileErrorToastTimeoutRef.current = setTimeout(() => {
      setFileErrorToast(null);
      fileErrorToastTimeoutRef.current = null;
    }, 4000);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await addFiles(Array.from(e.target.files));
    }
  };

  /** Attaches and uploads files picked by any means (file picker, screenshot). */
  const addFiles = async (newFiles: File[]) => {
    if (newFiles.length > 0) {

      const newAttachments: AttachmentWithFile[] = newFiles.map(file => ({ file, attachment: null }));
      setAttachments(prev => [...prev, ...newAttachments]);

      const newUploadingFiles = new Set(uploadingFiles);
      newFiles.forEach(file => newUploadingFiles.add(file.name));
      setUploadingFiles(newUploadingFiles);

      try {
        const settled = await Promise.allSettled(
          newFiles.map(async (file) => ({ file, ...(await uploadAttachment(file)) }))
        );

        const fileToAttachmentMap = new Map<string, Attachment | null>();
        const failedFileKeys = new Set<string>();
        const failures: Array<{ name: string; rejected: boolean }> = [];
        settled.forEach((result, index) => {
          const file = newFiles[index];
          if (!file) return;
          const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
          if (result.status === 'rejected') {
            fileToAttachmentMap.set(fileKey, null);
            failedFileKeys.add(fileKey);
            failures.push({ name: file.name, rejected: false });
            return;
          }
          const { attachment, rejected } = result.value;
          fileToAttachmentMap.set(fileKey, attachment);
          if (attachment === null) {
            failedFileKeys.add(fileKey);
            failures.push({ name: file.name, rejected });
          }
        });


        setAttachments(prev => {
          return prev
            .filter(att => {
              const fileKey = `${att.file.name}:${att.file.size}:${att.file.lastModified}`;
              return !failedFileKeys.has(fileKey);
            })
            .map(att => {
              const fileKey = `${att.file.name}:${att.file.size}:${att.file.lastModified}`;
              const uploadedAttachment = fileToAttachmentMap.get(fileKey);
              if (uploadedAttachment !== undefined) {
                return { ...att, attachment: uploadedAttachment };
              }
              return att;
            });
        });

        const failureToast = uploadFailureToast(failures, t);
        if (failureToast) showFileError(failureToast);
      } catch (error) {
        console.error('Error uploading file', error);
      } finally {
        const finalUploadingFiles = new Set(uploadingFiles);
        newFiles.forEach(file => finalUploadingFiles.delete(file.name));
        setUploadingFiles(finalUploadingFiles);
        if (fileInputRef.current) {
          fileInputRef.current!.value = '';
        }
      }
    }
  };

  const handleRemoveAttachment = (fileName: string) => {
    setAttachments(prev => prev.filter(att => att.file.name !== fileName));
  };

  const clearAttachments = () => {
    setAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return {
    attachments,
    setAttachments,
    uploadingFiles,
    fileErrorToast,
    fileInputRef,
    handleFileChange,
    addFiles,
    showFileError,
    handleRemoveAttachment,
    clearAttachments,
  };
}

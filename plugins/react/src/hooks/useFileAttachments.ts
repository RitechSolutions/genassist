import { useState, useRef, useEffect } from 'react';
import { Attachment, AttachmentWithFile } from '../types';

interface UseFileAttachmentsOptions {
  uploadFile: (file: File) => Promise<Attachment | null>;
  t: (key: string, fallback?: string) => string;
}

export function useFileAttachments({ uploadFile, t }: UseFileAttachmentsOptions) {
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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);

      const newAttachments: AttachmentWithFile[] = newFiles.map(file => ({ file, attachment: null }));
      setAttachments(prev => [...prev, ...newAttachments]);

      const newUploadingFiles = new Set(uploadingFiles);
      newFiles.forEach(file => newUploadingFiles.add(file.name));
      setUploadingFiles(newUploadingFiles);

      try {
        const settled = await Promise.allSettled(
          newFiles.map(async (file) => ({ file, attachment: await uploadFile(file) }))
        );

        const fileToAttachmentMap = new Map<string, Attachment | null>();
        const failedFileKeys = new Set<string>();
        settled.forEach((result, index) => {
          const file = newFiles[index];
          if (!file) return;
          const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
          if (result.status === 'rejected') {
            fileToAttachmentMap.set(fileKey, null);
            failedFileKeys.add(fileKey);
            return;
          }
          const { attachment } = result.value;
          fileToAttachmentMap.set(fileKey, attachment);
          if (attachment === null) {
            failedFileKeys.add(fileKey);
          }
        });

        const hasFailedUploads = failedFileKeys.size > 0;

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

        if (hasFailedUploads) {
          if (fileErrorToastTimeoutRef.current) {
            clearTimeout(fileErrorToastTimeoutRef.current);
          }
          setFileErrorToast(t('fileUpload.fileTypeNotSupported', 'This file type is not supported.'));
          fileErrorToastTimeoutRef.current = setTimeout(() => {
            setFileErrorToast(null);
            fileErrorToastTimeoutRef.current = null;
          }, 4000);
        }
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
    handleRemoveAttachment,
    clearAttachments,
  };
}

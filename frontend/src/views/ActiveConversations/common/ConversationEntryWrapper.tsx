import React from 'react';
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { FileIcon } from "lucide-react";
import { FileText, FileJson, FileImage } from 'lucide-react';

interface FileData {
  url: string;
  name: string;
  id: string;
  type: string;
}

const getFileIcon = (fileType: string): React.ReactElement => {
  if (fileType.startsWith('image/')) return <FileImage size={24} color="#6D28D9" />;
  if (fileType === 'application/pdf') return <FileText size={24} color="#B91C1C" />;
  if (fileType === 'application/json') return <FileJson size={24} color="#1D4ED8" />;
  return <FileText size={24} color="#4B5563" />;
};


/**
 * FilePreview component
 * @param fileData - The file data
 * @returns The file preview component
 */
function FilePreview({ fileData }: { fileData: FileData }) {
  if (fileData.type && fileData.type.startsWith('image')) {
    return <div className="flex flex-col items-start gap-2 cursor-pointer" onClick={() => window.open(fileData.url, '_blank')}>
      <img className="w-20 h-12 object-cover" src={fileData.url} alt="Image" loading="lazy" />
      <span className="text-xs text-muted-foreground">{fileData.name}</span>
    </div>;
  } else {
    return <div className="flex flex-col items-start gap-2 cursor-pointer" onClick={() => window.open(fileData.url, '_blank')}>
      {getFileIcon(fileData.type)}
      <span className="text-xs text-muted-foreground">{fileData.name}</span>
    </div>;
  }
}

export function ConversationEntryWrapper({ entry }: { entry: TranscriptEntry }) {
  try {
    if (entry.type === "file") {
      const cleanJson = entry.text && entry.text.replace(/\\/g, '');
      const fileData = cleanJson ? JSON.parse(cleanJson) : null;
      return <FilePreview fileData={fileData as FileData} />;
    } else {
      return <div>{entry.text}</div>;
    }
  } catch (error) {
    console.error("Error parsing entry text:", error);
    return <></>;
  }
}

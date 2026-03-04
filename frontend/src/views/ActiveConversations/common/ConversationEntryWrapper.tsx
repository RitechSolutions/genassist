import React from 'react';
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { FileIcon, ClipboardList } from "lucide-react";
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
    } else if (entry.type === "form_request") {
      const cleanJson = entry.text && entry.text.replace(/\\/g, '');
      const formSchema = cleanJson ? JSON.parse(cleanJson) : null;
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3 max-w-sm">
          <div className="flex items-center gap-2 mb-2">
            <ClipboardList className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">User Input Form</span>
          </div>
          <p className="text-xs text-blue-700 mb-2">
            {formSchema?.message || 'User input requested'}
          </p>
          <div className="flex flex-wrap gap-1">
            {formSchema?.fields?.map((f: { label: string; type: string; required?: boolean }, i: number) => (
              <span key={i} className="inline-flex items-center rounded border border-blue-300 bg-white px-1.5 py-0.5 text-[10px] text-blue-800">
                {f.label}
                {f.required && <span className="text-red-500 ml-0.5">*</span>}
              </span>
            ))}
          </div>
        </div>
      );
    } else {
      return <div>{entry.text}</div>;
    }
  } catch (error) {
    console.error("Error parsing entry text:", error);
    return <></>;
  }
}

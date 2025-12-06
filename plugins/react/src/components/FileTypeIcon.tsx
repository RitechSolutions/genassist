import React from 'react';
import { FileText, FileJson, FileImage } from 'lucide-react';

export const getFileIcon = (fileType: string): React.ReactElement => {
  if (fileType.startsWith('image/')) return <FileImage size={24} color="#6D28D9" />;
  if (fileType === 'application/pdf') return <FileText size={24} color="#B91C1C" />;
  if (fileType === 'application/json') return <FileJson size={24} color="#1D4ED8" />;
  return <FileText size={24} color="#4B5563" />;
};


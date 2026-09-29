import React from 'react';
import { getFileIcon } from '../FileTypeIcon';
import { Attachment } from '../../types';

interface UploadFilePreviewProps {
  file?: Attachment;
  index?: number;
  /** Chip background. Defaults to #f0f0f0. */
  backgroundColor?: string;
  /** File name text. Defaults to inherit. */
  textColor?: string;
  /** File size text. Defaults to #666. */
  mutedTextColor?: string;
}

export const UploadFilePreview: React.FC<UploadFilePreviewProps> = ({
  file,
  index,
  backgroundColor = '#f0f0f0',
  textColor,
  mutedTextColor = '#666',
}) => {

  let fileType = file?.type;

  // override file type for word processing documents
  if (file?.type?.startsWith('application/vnd.openxmlformats-officedocument.wordprocessingml.document')) {
    fileType = 'application/msword';
  }

  const containerStyle: React.CSSProperties = {
    cursor: 'pointer',
  };

  const contentStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    padding: '8px',
    backgroundColor,
    borderRadius: '8px',
    position: 'relative',
    maxWidth: '250px',
    ...(textColor ? { color: textColor } : {}),
  };

  const imageStyle: React.CSSProperties = {
    width: '40px',
    height: '40px',
    borderRadius: '4px',
    objectFit: 'cover',
    marginRight: '10px',
  };

  const fileNameStyle: React.CSSProperties = {
    width: '90%',
    maxWidth: '150px',
    fontWeight: 'bold',
    fontSize: '14px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const fileSizeStyle: React.CSSProperties = {
    fontSize: '12px',
    color: mutedTextColor,
  };

  const fileIconStyle: React.CSSProperties = {
    width: 40,
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const openFile = () => {
    window.open(file?.url, '_blank');
  };

  const renderContent = () => {
    return (
    <div
        key={index || Math.random()}
        style={contentStyle}
    >
        {fileType?.startsWith('image/') ? (
        <img
            src={file?.url}
            alt={file?.name}
            style={imageStyle}
        />
        ) : (
          <div style={fileIconStyle}>
              {getFileIcon(fileType || '')}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={fileNameStyle} title={file?.name}>{file?.name}</div>
        <div style={fileSizeStyle}>
            {fileType?.includes('/') ? fileType?.split('/')[1].toUpperCase() : fileType}
            {file?.size ? ` · ${(file?.size / 1024).toFixed(1)} KB` : ''}
        </div>
        </div>
    </div>
    );
  };

  return (
    <div style={containerStyle} onClick={openFile}>
      {renderContent()}
    </div>
  );
};


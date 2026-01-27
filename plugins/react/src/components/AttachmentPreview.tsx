import React from 'react';
import { Spinner } from './Spinner';
import { getFileIcon } from './FileTypeIcon';

interface AttachmentPreviewProps {
  file: File;
  onRemove: () => void;
  uploading?: boolean;
}

export const AttachmentPreview: React.FC<AttachmentPreviewProps> = ({ file, onRemove, uploading = false }) => {
  const fileType = file.type;
  const isImage = fileType.startsWith('image/');
  const [imagePreview, setImagePreview] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isImage) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  }, [file, isImage]);

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    padding: '8px',
    backgroundColor: '#f0f0f0',
    borderRadius: '8px',
    position: 'relative',
    maxWidth: '250px',
  };

  const imageStyle: React.CSSProperties = {
    width: '40px',
    height: '40px',
    borderRadius: '4px',
    objectFit: 'cover',
    marginRight: '10px',
  };

  const fileInfoStyle: React.CSSProperties = {
    flex: 1,
    overflow: 'hidden',
    whiteSpace: 'nowrap',
    textOverflow: 'ellipsis',
    width: '100%',
  };

  const fileNameStyle: React.CSSProperties = {
    width: '90%',
    fontWeight: 'bold',
    fontSize: '14px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const fileSizeStyle: React.CSSProperties = {
    fontSize: '12px',
    color: '#666',
  };

  const removeButtonStyle: React.CSSProperties = {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px',
    position: 'absolute',
    top: '4px',
    right: '4px',
  };

  const uploadingOverlayStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(255, 255, 255, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '8px',
  };

  return (
    <div style={containerStyle}>
      {isImage && imagePreview ? (
        <img src={imagePreview} alt={file.name} style={imageStyle} />
      ) : (
        <div style={{ marginRight: '10px' }}>{getFileIcon(fileType)}</div>
      )}
      <div style={fileInfoStyle}>
        <div style={fileNameStyle} title={file.name}>{file.name}</div>
        <div style={fileSizeStyle}>{(file.size ? file.size / 1024 : 0).toFixed(2)} KB</div>
      </div>
      {!uploading && (
        <button onClick={onRemove} style={removeButtonStyle} title="Remove file">
          &#x2715;
        </button>
      )}
      {uploading && (
        <div style={uploadingOverlayStyle}>
          <Spinner size={24} color="#000" />
        </div>
      )}
    </div>
  );
};


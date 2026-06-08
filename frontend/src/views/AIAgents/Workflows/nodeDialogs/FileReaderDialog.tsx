import React, { useState, useEffect } from "react";
import { FileReaderNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { FileUploader } from "@/components/FileUploader";

type FileReaderDialogProps = BaseNodeDialogProps<
  FileReaderNodeData,
  FileReaderNodeData
>;

export const FileReaderDialog: React.FC<FileReaderDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "File Reader");
  const [fileName, setFileName] = useState(data.fileName ?? "");
  const [filePath, setFilePath] = useState(data.filePath ?? "");
  const [fileUrl, setFileUrl] = useState(data.fileUrl ?? "");
  const [fileId, setFileId] = useState(data.fileId ?? "");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "File Reader");
      setFileName(data.fileName ?? "");
      setFilePath(data.filePath ?? "");
      setFileUrl(data.fileUrl ?? "");
      setFileId(data.fileId ?? "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      fileName,
      filePath,
      fileUrl,
      fileId,
    });
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{ ...data, name, fileName, filePath, fileUrl, fileId }}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., File Reader"
            className="w-full"
          />
        </div>

        <FileUploader
          label="File"
          initialOriginalFileName={fileName}
          initialServerFilePath={filePath}
          initialServerFileUrl={fileUrl}
          onUploadComplete={(result) => {
            setFileName(result.original_filename);
            setFilePath(result.file_path ?? "");
            setFileUrl(result.file_url ?? "");
            setFileId(result.file_id ?? "");
          }}
          onRemove={() => {
            setFileName("");
            setFilePath("");
            setFileUrl("");
            setFileId("");
          }}
        />
      </div>
    </NodeConfigPanel>
  );
};

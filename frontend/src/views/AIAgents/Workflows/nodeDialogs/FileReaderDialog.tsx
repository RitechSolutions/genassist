import React, { useState, useEffect } from "react";
import { FileReaderNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { FileUploader } from "@/components/FileUploader";

type FileReaderDialogProps = BaseNodeDialogProps<
  FileReaderNodeData,
  FileReaderNodeData
>;

type FileSource = "chatAttachment" | "upload";

export const FileReaderDialog: React.FC<FileReaderDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "File Reader");
  const [fileSource, setFileSource] = useState<FileSource>(
    data.fileSource ?? "upload"
  );
  const [fileName, setFileName] = useState(data.fileName ?? "");
  const [filePath, setFilePath] = useState(data.filePath ?? "");
  const [fileUrl, setFileUrl] = useState(data.fileUrl ?? "");
  const [fileId, setFileId] = useState(data.fileId ?? "");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "File Reader");
      setFileSource(data.fileSource ?? "upload");
      setFileName(data.fileName ?? "");
      setFilePath(data.filePath ?? "");
      setFileUrl(data.fileUrl ?? "");
      setFileId(data.fileId ?? "");
    }
  }, [isOpen, data]);

  const isChatAttachment = fileSource === "chatAttachment";

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      fileSource,
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
      data={{ ...data, name, fileSource, fileName, filePath, fileUrl, fileId }}
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

        <div className="space-y-2">
          <Label htmlFor="file-source">File Source</Label>
          <Select
            value={fileSource}
            onValueChange={(value) => setFileSource(value as FileSource)}
          >
            <SelectTrigger id="file-source">
              <SelectValue placeholder="Select file source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="chatAttachment">
                Document attached in chat
              </SelectItem>
              <SelectItem value="upload">Uploaded file</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">
            {isChatAttachment
              ? "Reads every document the user attaches in this chat. Images are handled by the Language Model node."
              : "Reads a fixed file uploaded here."}
          </p>
        </div>

        {!isChatAttachment && (
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
        )}
      </div>
    </NodeConfigPanel>
  );
};

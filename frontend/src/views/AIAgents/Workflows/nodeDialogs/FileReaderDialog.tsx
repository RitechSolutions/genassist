import React from "react";
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
import { useNodeDialogState } from "./useNodeDialogState";

type FileReaderDialogProps = BaseNodeDialogProps<
  FileReaderNodeData,
  FileReaderNodeData
>;

type FileSource = "chatAttachment" | "upload";

export const FileReaderDialog: React.FC<FileReaderDialogProps> = (props) => {
  const { onClose, data } = props;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(props, () => ({
      name: data.name || "File Reader",
      fileSource: data.fileSource ?? "upload",
      fileName: data.fileName ?? "",
      filePath: data.filePath ?? "",
      fileUrl: data.fileUrl ?? "",
      fileId: data.fileId ?? "",
    }));

  const isChatAttachment = values.fileSource === "chatAttachment";

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
      data={merged}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="e.g., File Reader"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="file-source">File Source</Label>
          <Select
            value={values.fileSource}
            onValueChange={(value) => setField("fileSource", value as FileSource)}
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
            initialOriginalFileName={values.fileName}
            initialServerFilePath={values.filePath}
            initialServerFileUrl={values.fileUrl}
            onUploadComplete={(result) => {
              setValues((v) => ({
                ...v,
                fileName: result.original_filename,
                filePath: result.file_path ?? "",
                fileUrl: result.file_url ?? "",
                fileId: result.file_id ?? "",
              }));
            }}
            onRemove={() => {
              setValues((v) => ({
                ...v,
                fileName: "",
                filePath: "",
                fileUrl: "",
                fileId: "",
              }));
            }}
          />
        )}
      </div>
    </NodeConfigPanel>
  );
};

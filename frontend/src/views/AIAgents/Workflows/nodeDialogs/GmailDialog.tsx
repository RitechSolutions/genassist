import React, { useState, useRef } from "react";
import { GmailNodeData, GmailOperation } from "../types/nodes";
import { DataSource } from "@/interfaces/dataSource.interface";
import { Button } from "@/components/button";
import { DraggableInput } from "../components/custom/DraggableInput";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Paperclip, X, Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { useNodeDialogState } from "./useNodeDialogState";

interface GmailDialogProps
  extends BaseNodeDialogProps<GmailNodeData, GmailNodeData> {
  connectors: DataSource[];
}

export const GmailDialog: React.FC<GmailDialogProps> = (props) => {
  const { onClose, data, connectors } = props;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(props, () => ({
      name: data.name || "",
      subject: data.subject || "",
      body: data.body || "",
      to: data.to || "",
      cc: data.cc || "",
      bcc: data.bcc || "",
      dataSourceId: data.dataSourceId?.toString() || "",
      operation: (data.operation as GmailOperation) || "send_email",
      attachments: data.attachments || [],
    }));

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isCreateDataSourceOpen, setIsCreateDataSourceOpen] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const base64Content = e.target?.result as string;
          setValues((v) => ({
            ...v,
            attachments: [...v.attachments, base64Content],
          }));
        };
        reader.readAsDataURL(file);
      });
    }
  };

  const removeAttachment = (index: number) => {
    setValues((v) => ({
      ...v,
      attachments: v.attachments.filter((_, i) => i !== index),
    }));
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  return (
    <>
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
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <RichInput
            id="node-name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="connector-select">Select Connector</Label>
          <Select
            value={values.dataSourceId}
            onValueChange={(val) => {
              if (val === "__create__") {
                setIsCreateDataSourceOpen(true);
                return;
              }
              setField("dataSourceId", val);
            }}
          >
            <SelectTrigger id="connector-select">
              <SelectValue placeholder="Select connector" />
            </SelectTrigger>
            <SelectContent>
              {connectors.map((conn) => (
                <SelectItem key={conn.id} value={String(conn.id)}>
                  {conn.name}
                </SelectItem>
              ))}
              <CreateNewSelectItem />
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="operation-select">Operation</Label>
          <Select
            value={values.operation}
            onValueChange={(value) =>
              setField("operation", value as GmailOperation)
            }
          >
            <SelectTrigger id="operation-select">
              <SelectValue placeholder="Select operation" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="send_email">Send Email</SelectItem>
              <SelectItem value="get_messages">Get Messages</SelectItem>
              <SelectItem value="mark_as_read">Mark as Read</SelectItem>
              <SelectItem value="delete_message">Delete Message</SelectItem>
              <SelectItem value="reply_to_email">Reply to Email</SelectItem>
              <SelectItem value="search_emails">Search Emails</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Recipients</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="to">To</Label>
              <DraggableInput
                id="to"
                type="email"
                value={values.to}
                onChange={(e) => setField("to", e.target.value)}
                placeholder="e.g., recipient@example.com"
                className="w-full break-all"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="cc">CC</Label>
                <DraggableInput
                  id="cc"
                  type="email"
                  value={values.cc}
                  onChange={(e) => setField("cc", e.target.value)}
                  placeholder="e.g., cc@example.com"
                  className="w-full break-all"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bcc">BCC</Label>
                <DraggableInput
                  id="bcc"
                  type="email"
                  value={values.bcc}
                  onChange={(e) => setField("bcc", e.target.value)}
                  placeholder="e.g., bcc@example.com"
                  className="w-full break-all"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Message Content</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <DraggableInput
                id="subject"
                value={values.subject}
                onChange={(e) => setField("subject", e.target.value)}
                placeholder="Enter email subject"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="body">Body</Label>
              <DraggableTextArea
                id="body"
                size="body"
                value={values.body}
                onChange={(e) => setField("body", e.target.value)}
                placeholder="Enter message content"
                className="w-full"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="font-bold">Attachments</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={triggerFileSelect}
            >
              <Paperclip className="h-3 w-3 mr-1" /> Add Files
            </Button>
          </div>
          <RichInput
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept="*/*"
          />
          <div className="space-y-2">
            {values.attachments.length > 0 ? (
              values.attachments.map((attachment, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2 bg-muted rounded-md w-full"
                >
                  <div className="flex items-center space-x-2 flex-1 min-w-0">
                    <Paperclip className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-medium truncate break-all">
                      {`Attachment ${index + 1}`}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 flex-shrink-0"
                    onClick={() => removeAttachment(index)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))
            ) : (
              <div
                className="text-center py-5 border-2 border-dashed rounded-md cursor-pointer hover:border-primary/50 transition-colors w-full"
                onClick={triggerFileSelect}
              >
                <p className="text-sm text-muted-foreground break-words">
                  Click to add attachments
                </p>
              </div>
            )}
          </div>
        </div>
      </NodeConfigPanel>
      <DataSourceDialog
        isOpen={isCreateDataSourceOpen}
        onOpenChange={setIsCreateDataSourceOpen}
        onDataSourceSaved={(created) => {
          if (created?.id) setField("dataSourceId", created.id);
        }}
        mode="create"
        defaultSourceType="gmail"
      />
    </>
  );
};

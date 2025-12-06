import React, { useEffect, useState, useRef } from "react";
import { GmailNodeData } from "../types/nodes";
import { DataSource } from "@/interfaces/dataSource.interface";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Separator } from "@/components/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Paperclip, X, Save } from "lucide-react";

interface GmailDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: GmailNodeData;
  onUpdate: (data: Partial<GmailNodeData>) => void;
  connectors: DataSource[];
}

export const GmailDialog: React.FC<GmailDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
  connectors,
}) => {
  const [name, setName] = useState(data.name || "Gmail Output");
  const [subject, setSubject] = useState(data.subject || "");
  const [body, setBody] = useState(data.body || "");
  const [to, setTo] = useState(data.to || "");
  const [cc, setCc] = useState(data.cc || "");
  const [bcc, setBcc] = useState(data.bcc || "");
  const [dataSourceId, setDataSourceId] = useState(data.dataSourceId || "");
  const [attachments, setAttachments] = useState(data.attachments || []);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Gmail Output");
      setSubject(data.subject || "");
      setBody(data.body || "");
      setTo(data.to || "");
      setCc(data.cc || "");
      setBcc(data.bcc || "");
      setDataSourceId(data.dataSourceId || "");
      setAttachments(data.attachments || []);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      name,
      subject,
      body,
      to,
      cc,
      bcc,
      dataSourceId,
      attachments,
    });
    onClose();
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const base64Content = e.target?.result as string;
          const base64Data = base64Content.split(",")[1];
          const newAttachment = {
            name: file.name,
            size: file.size,
            type: file.type,
            file: { content: base64Data },
          };
          setAttachments((prev) => [...prev, newAttachment]);
        };
        reader.onerror = (error) => console.error("Error reading file:", error);
        reader.readAsDataURL(file);
      });
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Gmail Output</DialogTitle>
          <DialogDescription>
            Set the node name, recipients, content, and attachments for the
            email.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="node-name">Node Name</Label>
            <Input
              id="node-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter the name of this node"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="connector-select">Select Connector</Label>
            <Select value={dataSourceId} onValueChange={setDataSourceId}>
              <SelectTrigger id="connector-select">
                <SelectValue placeholder="Select connector" />
              </SelectTrigger>
              <SelectContent>
                {connectors.map((conn) => (
                  <SelectItem key={conn.id} value={conn.id}>
                    {conn.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="font-bold">Recipients</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="to">To</Label>
                <Input
                  id="to"
                  type="email"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  placeholder="e.g., recipient@example.com"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="cc">CC</Label>
                  <Input
                    id="cc"
                    type="email"
                    value={cc}
                    onChange={(e) => setCc(e.target.value)}
                    placeholder="e.g., cc@example.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="bcc">BCC</Label>
                  <Input
                    id="bcc"
                    type="email"
                    value={bcc}
                    onChange={(e) => setBcc(e.target.value)}
                    placeholder="e.g., bcc@example.com"
                  />
                </div>
              </div>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="font-bold">Message Content</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="subject">Subject</Label>
                <Input
                  id="subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Enter email subject"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="body">Body</Label>
                <Textarea
                  id="body"
                  rows={6}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Enter message content"
                />
              </div>
            </div>
          </div>

          <Separator />

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
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              accept="*/*"
            />
            <div className="space-y-2">
              {attachments.length > 0 ? (
                attachments.map((attachment, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-2 bg-muted rounded-md"
                  >
                    <div className="flex items-center space-x-2 flex-1 min-w-0">
                      <Paperclip className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm font-medium truncate block">
                        {typeof attachment === "string"
                          ? attachment
                          : attachment.name || `Attachment ${index + 1}`}
                      </span>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => removeAttachment(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))
              ) : (
                <div
                  className="text-center py-5 border-2 border-dashed rounded-md cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={triggerFileSelect}
                >
                  <p className="text-sm text-muted-foreground">
                    Click to add attachments
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

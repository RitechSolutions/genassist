import React, { useEffect, useState } from "react";
import { ZendeskTicketNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Separator } from "@/components/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Save } from "lucide-react";

interface ZendeskTicketDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: ZendeskTicketNodeData;
  onUpdate: (data: Partial<ZendeskTicketNodeData>) => void;
}

export const ZendeskTicketDialog: React.FC<ZendeskTicketDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [name, setName] = useState(data.name || "Zendesk Ticket");
  const [subject, setSubject] = useState(data.subject || "");
  const [description, setDescription] = useState(data.description || "");
  const [requesterName, setRequesterName] = useState(data.requester_name || "");
  const [requesterEmail, setRequesterEmail] = useState(
    data.requester_email || ""
  );
  const [tagsCsv, setTagsCsv] = useState((data.tags || []).join(", "));

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Zendesk Ticket");
      setSubject(data.subject || "");
      setDescription(data.description || "");
      setRequesterName(data.requester_name || "");
      setRequesterEmail(data.requester_email || "");
      setTagsCsv((data.tags || []).join(", "));
    }
  }, [isOpen, data]);

  const handleSave = () => {
    const tagsArr = tagsCsv
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    onUpdate({
      name,
      subject,
      description,
      requester_name: requesterName,
      requester_email: requesterEmail,
      tags: tagsArr,
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Zendesk Ticket</DialogTitle>
          <DialogDescription>
            Set the details for the new Zendesk ticket.
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

          <Separator />

          <div className="space-y-2">
            <Label className="font-bold">Ticket Information</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="subject">Subject</Label>
                <Input
                  id="subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Enter ticket subject"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter the issue or request description"
                />
              </div>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="font-bold">Requester Information</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="requester_name">Requester Name</Label>
                <Input
                  id="requester_name"
                  value={requesterName}
                  onChange={(e) => setRequesterName(e.target.value)}
                  placeholder="e.g., Alice Smith"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="requester_email">Requester Email</Label>
                <Input
                  id="requester_email"
                  type="email"
                  value={requesterEmail}
                  onChange={(e) => setRequesterEmail(e.target.value)}
                  placeholder="e.g., alice@example.com"
                />
              </div>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="font-bold">Tags</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="tags">Tags</Label>
                <Input
                  id="tags"
                  value={tagsCsv}
                  onChange={(e) => setTagsCsv(e.target.value)}
                  placeholder="e.g., support, urgent, follow-up"
                />
              </div>
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

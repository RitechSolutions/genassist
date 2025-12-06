import React, { useEffect, useState } from "react";
import { SlackOutputNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Save } from "lucide-react";

interface SlackOutputDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: SlackOutputNodeData;
  onUpdate: (data: Partial<SlackOutputNodeData>) => void;
}

export const SlackOutputDialog: React.FC<SlackOutputDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [name, setName] = useState(data.name || "Slack Message");
  const [token, setToken] = useState(data.token || "");
  const [channel, setChannel] = useState(data.channel || "");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Slack Message");
      setToken(data.token || "");
      setChannel(data.channel || "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      name,
      token,
      channel,
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Slack Message Output</DialogTitle>
          <DialogDescription>
            Set the credentials and destination for your Slack messages.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="token">Bot Token</Label>
            <Input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="e.g., xoxb-..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="channel">Channel ID</Label>
            <Input
              id="channel"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              placeholder="e.g., C12345678 or user@example.com"
            />
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

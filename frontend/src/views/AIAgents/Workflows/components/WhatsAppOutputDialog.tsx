import React, { useEffect, useState } from "react";
import { WhatsAppOutputNodeData } from "../types/nodes";
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

interface WhatsAppOutputDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: WhatsAppOutputNodeData;
  onUpdate: (data: Partial<WhatsAppOutputNodeData>) => void;
}

export const WhatsAppOutputDialog: React.FC<WhatsAppOutputDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [name, setName] = useState(data.name || "WhatsApp Message");
  const [token, setToken] = useState(data.token || "");
  const [businessNumber, setBusinessNumber] = useState(
    data.business_number || ""
  );
  const [toNumber, setToNumber] = useState(data.to_number || "");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "WhatsApp Message");
      setToken(data.token || "");
      setBusinessNumber(data.business_number || "");
      setToNumber(data.to_number || "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      name,
      token,
      business_number: businessNumber,
      to_number: toNumber,
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure WhatsApp Message Output</DialogTitle>
          <DialogDescription>
            Set the credentials and numbers for sending WhatsApp messages
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="token">API Token</Label>
            <Input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Your WhatsApp API token"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="businessNumber">Business Phone Number</Label>
            <Input
              id="businessNumber"
              value={businessNumber}
              onChange={(e) => setBusinessNumber(e.target.value)}
              placeholder="Your WhatsApp Business phone number"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="toNumber">Recipient Number</Label>
            <Input
              id="toNumber"
              value={toNumber}
              onChange={(e) => setToNumber(e.target.value)}
              placeholder="e.g., 15551234567"
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

import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";

interface RenameNodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  currentName: string;
  onRename: (name: string) => void;
}

const RenameNodeDialog: React.FC<RenameNodeDialogProps> = ({
  isOpen,
  onClose,
  currentName,
  onRename,
}) => {
  const [name, setName] = useState(currentName);

  // Reseed from the node's current name each time the dialog opens.
  useEffect(() => {
    if (isOpen) setName(currentName);
  }, [isOpen, currentName]);

  const handleSave = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onRename(trimmed);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md" style={{ zIndex: 2000 }}>
        <DialogHeader>
          <DialogTitle>Rename node</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="rename-node-name">Node Name</Label>
          <RichInput
            id="rename-node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSave();
              }
            }}
          />
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!name.trim()}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RenameNodeDialog;

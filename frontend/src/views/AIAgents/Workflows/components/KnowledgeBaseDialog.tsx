import React, { useEffect, useState } from "react";
import { KnowledgeBaseNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { KnowledgeItem } from "@/interfaces/knowledge.interface";
import { getAllKnowledgeItems } from "@/services/api";
import { useToast } from "@/components/use-toast";
import { Save } from "lucide-react";

interface KnowledgeBaseDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: KnowledgeBaseNodeData;
  onUpdate: (data: KnowledgeBaseNodeData) => void;
}

export const KnowledgeBaseDialog: React.FC<KnowledgeBaseDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [name, setName] = useState(data.name || "Knowledge Base");
  const [description, setDescription] = useState(
    data.description || "Query multiple knowledge bases"
  );
  const [selectedBases, setSelectedBases] = useState<string[]>(
    data.selectedBases || []
  );
  const [availableBases, setAvailableBases] = useState<KnowledgeItem[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Knowledge Base");
      setDescription(data.description || "Query multiple knowledge bases");
      setSelectedBases(data.selectedBases || []);

      const loadKnowledgeBases = async () => {
        try {
          const bases = await getAllKnowledgeItems();
          setAvailableBases(bases);
        } catch (err) {
          console.error("Failed to load knowledge bases:", err);
          toast({
            title: "Error",
            description: "Failed to load knowledge bases",
            variant: "destructive",
          });
        }
      };
      loadKnowledgeBases();
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      description,
      selectedBases,
    });
    onClose();
  };

  const toggleBase = (baseId: string) => {
    setSelectedBases((prev) =>
      prev.includes(baseId)
        ? prev.filter((id) => id !== baseId)
        : [...prev, baseId]
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Knowledge Base</DialogTitle>
          <DialogDescription>
            Update the configuration for your knowledge base
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="name">Node Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter the name of this node"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter a description for this node"
            />
          </div>

          <div className="space-y-2">
            <Label>Knowledge Bases</Label>
            <ScrollArea className="h-40 border rounded-md p-2">
              <div className="space-y-2">
                {availableBases.map((base) => (
                  <div key={base.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`kb-${base.id}`}
                      checked={selectedBases.includes(base.id)}
                      onCheckedChange={() => toggleBase(base.id)}
                    />
                    <Label
                      htmlFor={`kb-${base.id}`}
                      className="text-sm font-normal"
                    >
                      {base.name}
                    </Label>
                  </div>
                ))}
              </div>
            </ScrollArea>
            <p className="text-xs text-gray-500">
              Select the knowledge bases you want to query.
            </p>
          </div>
        </div>

        <DialogFooter>
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

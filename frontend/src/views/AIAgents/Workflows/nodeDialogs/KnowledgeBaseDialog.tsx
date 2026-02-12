import React, { useState, useEffect } from "react";
import { KnowledgeBaseNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { KnowledgeItem } from "@/interfaces/knowledge.interface";
import { getAllKnowledgeItems } from "@/services/api";
import { useToast } from "@/components/use-toast";
import { Save, Plus, ExternalLink } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";

type KnowledgeBaseDialogProps = BaseNodeDialogProps<
  KnowledgeBaseNodeData,
  KnowledgeBaseNodeData
>;

export const KnowledgeBaseDialog: React.FC<KnowledgeBaseDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [query, setQuery] = useState(data.query || "");
  const [limit, setLimit] = useState(data.limit || 5);
  const [force, setForce] = useState(data.force || false);
  const [selectedBases, setSelectedBases] = useState<string[]>(
    data.selectedBases || []
  );
  const [availableBases, setAvailableBases] = useState<KnowledgeItem[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setQuery(data.query || "");
      setLimit(data.limit || 5);
      setForce(data.force || false);
      setSelectedBases(data.selectedBases || []);

      const loadKnowledgeBases = async () => {
        try {
          const bases = await getAllKnowledgeItems();
          setAvailableBases(bases);
        } catch (err) {
          toast({
            title: "Error",
            description: "Failed to load knowledge bases",
            variant: "destructive",
          });
        }
      };
      loadKnowledgeBases();
    }
  }, [isOpen, data, toast]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      query,
      limit,
      force,
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
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
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
      data={{
        ...data,
        name,
        query,
        limit,
        force,
        selectedBases,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Node Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="query">Query</Label>
        <DraggableTextArea
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter a query for this node"
          className="w-full"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="limit">Limit</Label>
          <Input
            id="limit"
            type="number"
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value))}
            placeholder="5"
            min="1"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="force">Force</Label>
          <div className="flex items-center space-x-2 h-10">
            <Checkbox
              id="force"
              checked={force}
              onCheckedChange={(checked) => setForce(checked as boolean)}
            />
            <Label
              htmlFor="force"
              className="text-sm font-normal cursor-pointer"
            >
              Force limit
            </Label>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Knowledge Bases</Label>
        <div className="flex justify-end pb-2">
          <a
            href="/knowledge-base"
            target="_blank"
            rel="noreferrer"
            className="text-sm flex items-center gap-1 text-blue-600 hover:text-blue-700"
          >
            <Plus className="w-4 h-4" /> Configure new KB{" "}
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <ScrollArea className="h-40 border rounded-md p-2 w-full">
          <div className="space-y-2">
            {availableBases.map((base) => (
              <div key={base.id} className="flex items-center space-x-2 w-full">
                <Checkbox
                  id={`kb-${base.id}`}
                  checked={selectedBases.includes(base.id)}
                  onCheckedChange={() => toggleBase(base.id)}
                />
                <Label
                  htmlFor={`kb-${base.id}`}
                  className="text-sm font-normal break-words flex-1 cursor-pointer"
                >
                  {base.name}
                </Label>
              </div>
            ))}
          </div>
        </ScrollArea>
        <p className="text-xs text-gray-500 break-words">
          Select the knowledge bases you want to query.
        </p>
      </div>
    </NodeConfigPanel>
  );
};

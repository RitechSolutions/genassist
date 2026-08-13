import React, { useState, useEffect } from "react";
import { KnowledgeBaseNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
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
import { useNodeDialogState } from "./useNodeDialogState";

type KnowledgeBaseDialogProps = BaseNodeDialogProps<
  KnowledgeBaseNodeData,
  KnowledgeBaseNodeData
>;

export const KnowledgeBaseDialog: React.FC<KnowledgeBaseDialogProps> = (
  props
) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(props, () => ({
      name: data.name || "",
      query: data.query || "",
      limit: data.limit || 5,
      force: data.force || false,
      selectedBases: data.selectedBases || [],
    }));

  const [availableBases, setAvailableBases] = useState<KnowledgeItem[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      const loadKnowledgeBases = async () => {
        try {
          const bases = await getAllKnowledgeItems();
          setAvailableBases(bases as unknown as KnowledgeItem[]);
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

  const toggleBase = (baseId: string) => {
    setValues((v) => ({
      ...v,
      selectedBases: v.selectedBases.includes(baseId)
        ? v.selectedBases.filter((id) => id !== baseId)
        : [...v.selectedBases, baseId],
    }));
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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Node Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="query">Query</Label>
        <DraggableTextArea
          id="query"
          value={values.query}
          onChange={(e) => setField("query", e.target.value)}
          placeholder="Enter a query for this node"
          className="w-full"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="limit">Limit</Label>
          <RichInput
            id="limit"
            type="number"
            value={values.limit}
            onChange={(e) => setField("limit", parseInt(e.target.value))}
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
              checked={values.force}
              onCheckedChange={(checked) =>
                setField("force", checked as boolean)
              }
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
            className="text-sm flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:text-blue-700"
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
                  checked={values.selectedBases.includes(base.id)}
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
        <p className="text-xs text-muted-foreground break-words">
          Select the knowledge bases you want to query.
        </p>
      </div>
    </NodeConfigPanel>
  );
};

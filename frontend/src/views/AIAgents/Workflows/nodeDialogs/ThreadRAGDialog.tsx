import React from "react";
import { ThreadRAGNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import RagVectorConfigSection from "@/views/KnowledgeBase/components/RagVectorConfigSection";
import { useNodeDialogState } from "./useNodeDialogState";

type ThreadRAGDialogProps = BaseNodeDialogProps<
  ThreadRAGNodeData,
  ThreadRAGNodeData
>;

export const ThreadRAGDialog: React.FC<ThreadRAGDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      action: (data.action || "retrieve") as "retrieve" | "add",
      // Retrieve action fields
      query: data.query || "",
      top_k: data.top_k || 5,
      // Add action fields
      message: data.message || "",
      // Vector store config
      ragVectorConfig: (data.ragVectorConfig ?? {}) as Record<string, unknown>,
    }),
    (v) => {
      const updatedData: Partial<ThreadRAGNodeData> = {
        name: v.name,
        action: v.action,
        ragVectorConfig: v.ragVectorConfig,
      };

      if (v.action === "retrieve") {
        updatedData.query = v.query;
        updatedData.top_k = v.top_k;
        // Clear add action fields
        updatedData.message = undefined;
      } else {
        updatedData.message = v.message;
        // Clear retrieve action fields
        updatedData.query = undefined;
        updatedData.top_k = undefined;
      }

      return updatedData;
    },
  );

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
        <Label htmlFor="action">Action</Label>
        <Select
          value={values.action}
          onValueChange={(value: "retrieve" | "add") =>
            setField("action", value)
          }
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="retrieve">Retrieve Context</SelectItem>
            <SelectItem value="add">Add Message to RAG</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {values.action === "retrieve" ? (
        <>
          <div className="space-y-2">
            <Label htmlFor="query">Query</Label>
            <DraggableTextArea
              id="query"
              value={values.query}
              onChange={(e) => setField("query", e.target.value)}
              placeholder="e.g., {{query}}"
              className="w-full"
              size="hint"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="top_k">Top K</Label>
            <RichInput
              id="top_k"
              type="number"
              value={values.top_k}
              onChange={(e) => setField("top_k", parseInt(e.target.value))}
              placeholder="5"
              min="1"
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Number of results to retrieve from RAG
            </p>
          </div>
        </>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="message">Message</Label>
            <DraggableTextArea
              id="message"
              value={values.message}
              onChange={(e) => setField("message", e.target.value)}
              placeholder="e.g., {{message}}"
              className="w-full"
              size="description"
            />
          </div>
        </>
      )}

      <div className="space-y-2 pt-2 border-t border-border">
        <Label className="text-sm font-medium">Vector Store Configuration</Label>
        <p className="text-xs text-muted-foreground">
          Embedding provider, vector database, and chunking strategy. Settings
          are applied on the first operation for this chat thread.
        </p>
        <RagVectorConfigSection
          config={values.ragVectorConfig}
          onChange={(config) => setField("ragVectorConfig", config)}
        />
      </div>
    </NodeConfigPanel>
  );
};

import React, { useState, useEffect } from "react";
import { ThreadRAGNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
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

type ThreadRAGDialogProps = BaseNodeDialogProps<
  ThreadRAGNodeData,
  ThreadRAGNodeData
>;

export const ThreadRAGDialog: React.FC<ThreadRAGDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [action, setAction] = useState<"retrieve" | "add">(
    data.action || "retrieve"
  );
  // Retrieve action fields
  const [query, setQuery] = useState(data.query || "");
  const [topK, setTopK] = useState(data.top_k || 5);
  // Add action fields
  const [message, setMessage] = useState(data.message || "");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setAction(data.action || "retrieve");
      setQuery(data.query || "");
      setTopK(data.top_k || 5);
      setMessage(data.message || "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    const updatedData: ThreadRAGNodeData = {
      ...data,
      name,
      action,
    };

    if (action === "retrieve") {
      updatedData.query = query;
      updatedData.top_k = topK;
      // Clear add action fields
      updatedData.message = undefined;
    } else {
      updatedData.message = message;
      // Clear retrieve action fields
      updatedData.query = undefined;
      updatedData.top_k = undefined;
    }

    onUpdate(updatedData);
    onClose();
  };

  return (
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Configure Per Chat RAG"
      description="Configure the RAG node to retrieve context or add messages to the chat RAG"
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
        action,
        query,
        top_k: topK,
        message,
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
        <Label htmlFor="action">Action</Label>
        <Select
          value={action}
          onValueChange={(value: "retrieve" | "add") => setAction(value)}
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

      {action === "retrieve" ? (
        <>
          <div className="space-y-2">
            <Label htmlFor="query">Query</Label>
            <DraggableTextArea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., {{query}}"
              className="w-full"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="top_k">Top K</Label>
            <Input
              id="top_k"
              type="number"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              placeholder="5"
              min="1"
              className="w-full"
            />
            <p className="text-xs text-gray-500">
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
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g., {{message}}"
              className="w-full"
              rows={4}
            />
          </div>
        </>
      )}
    </NodeConfigPanel>
  );
};

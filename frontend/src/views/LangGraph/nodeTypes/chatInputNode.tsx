import React, { useState, useEffect, useCallback } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { Button } from "@/components/button";
import { Textarea } from "@/components/textarea";
import { Save, Play, MessageCircle } from "lucide-react";
import { ChatInputNodeData } from "../types/nodes";
import { TestDialog, TestInputField } from "../components/TestDialog";
import { HandleTooltip } from "../components/HandleTooltip";
import { createSimpleSchema } from "../types/schemas";
import { getNodeColors } from "../utils/nodeColors";

// Component for the Chat Input Node
const ChatInputNode: React.FC<NodeProps<ChatInputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors('chatInputNode');

  useEffect(() => {
    // Initialize handlers if they don't exist
    if (!data.handlers) {
      data.updateNodeData?.(id, {
        ...data,
        handlers: [
          {
            id: 'output',
            type: 'source',
            compatibility: 'text',
          }
        ]
      });
    }
  }, []);

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[300px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <div className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}>
          <div className="flex items-center">
            <MessageCircle className={`h-4 w-4 text-white mr-2`} />
            <div className="text-sm font-medium text-white">Chat Input</div>
          </div>
        </div>

        {/* Node content */}
        <div className="p-4">
          <div className="space-y-4">
            <div className="text-sm text-gray-500">
              Chat input as entry point for workflow.
            </div>
          </div>
        </div>

        {data.handlers?.map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === 'source' ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: "50%" }}
          />
        ))}
      </div>
    </>
  );
};

export default ChatInputNode;

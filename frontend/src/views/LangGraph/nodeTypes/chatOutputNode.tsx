import React, { useCallback, useEffect, useState, useRef } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { ChatOutputNodeData } from "../types/nodes";
import { ScrollArea } from "@/components/scroll-area";
import { Save, Trash2, Bot, User, MessageSquare } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { HandleTooltip } from "../components/HandleTooltip";
import { createSimpleSchema } from "../types/schemas";
import { getNodeColors } from "../utils/nodeColors";

// Generate a unique ID for messages
const generateId = () => Math.random().toString(36).substring(2, 9);

const ChatOutputNode: React.FC<NodeProps<ChatOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const [messages, setMessages] = useState(data.messages || []);
  const [isDirty, setIsDirty] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const colors = getNodeColors("chatOutputNode");

  // Initialize handlers if they don't exist
  useEffect(() => {
    if (!data.handlers) {
      const inputSchema = createSimpleSchema({
        message: {
          type: "string",
          required: true,
          description: "The message to display",
        },
      });

      data.updateNodeData?.(id, {
        ...data,
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "text",
            schema: inputSchema,
          },
        ],
      });
    }
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Save changes function
  const saveChanges = useCallback(() => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        messages,
      });
    }
    setIsDirty(false);
  }, [data, id, messages]);

  // Mark as dirty when messages change
  useEffect(() => {
    if (JSON.stringify(messages) !== JSON.stringify(data.messages)) {
      setIsDirty(true);
    }
  }, [messages, data.messages]);

  // Handle input from connected nodes
  const onInputReceived = useCallback((text: string) => {
    const newMessage = {
      id: generateId(),
      text,
      timestamp: new Date().toISOString(),
      type: "assistant" as const,
    };

    setMessages((prev) => [...prev, newMessage]);
  }, []);

  // Register input handler
  useEffect(() => {
    if (data.onInputReceived !== onInputReceived) {
      data.onInputReceived = onInputReceived;
    }
  }, [data, onInputReceived]);

  // Clear all messages
  const clearMessages = () => {
    setMessages([]);
  };

  // Render message component
  const renderMessage = (message: (typeof messages)[0]) => {
    const isAssistant = message.type === "assistant";

    return (
      <div
        key={message.id}
        className={cn(
          "p-3 rounded-lg max-w-[85%] mb-2",
          isAssistant ? "bg-blue-100 ml-0 mr-auto" : "bg-gray-100 ml-auto mr-0"
        )}
      >
        <div className="flex items-center gap-2 mb-1 text-xs text-gray-500">
          {isAssistant ? (
            <Bot size={14} className="text-blue-600" />
          ) : (
            <User size={14} className="text-gray-600" />
          )}
          <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
        </div>
        <div className="text-sm whitespace-pre-wrap">{message.text}</div>
      </div>
    );
  };

  return (
    <div
      className={`border-2 rounded-md bg-white shadow-md w-[300px] ${
        selected ? "border-blue-500" : "border-gray-200"
      }`}
    >
      {/* Node header */}
      <div
        className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}
      >
        <div className="flex items-center">
          <MessageSquare className={`h-4 w-4 text-white mr-2`} />
          <div className="text-sm font-medium text-white">Chat Output</div>
        </div>
      </div>

      {/* Node content */}
      <div className="p-4">
        <div className="space-y-4">
          <div className="text-sm text-gray-500">
            Chat output as end point for workflow.
          </div>
        </div>
      </div>

      {data.handlers?.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.type === "source" ? Position.Right : Position.Left}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          style={{ top: "50%" }}
        />
      ))}
    </div>
  );
};

export default ChatOutputNode;

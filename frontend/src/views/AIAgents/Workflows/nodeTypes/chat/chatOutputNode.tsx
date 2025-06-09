import React, { useEffect } from "react";
import { Position, NodeProps } from "reactflow";
import { ChatOutputNodeData } from "../../types/nodes";
import { MessageSquare } from "lucide-react";
import { HandleTooltip } from "../../components/HandleTooltip";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColors } from "../../utils/nodeColors";


const ChatOutputNode: React.FC<NodeProps<ChatOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
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

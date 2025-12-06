import React, { useState } from "react";
import { Position, NodeProps } from "reactflow";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog } from "../../components/TestDialog";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColors } from "../../utils/nodeColors";
import { sendWhatsAppMessage } from "@/services/workflows";
import { WhatsAppOutputNodeData } from "../../types/nodes";
import NodeHeader from "../nodeHeader";
import NodeContent from "../nodeContent";
import { WhatsAppOutputDialog } from "../../components/WhatsAppOutputDialog";

const WhatsAppOutputNode: React.FC<NodeProps<WhatsAppOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("whatsappMessageNode");

  const [response, setResponse] = useState<string>("");
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onUpdate = (updatedData: Partial<WhatsAppOutputNodeData>) => {
    const inputSchema = createSimpleSchema({
      text_msg: { type: "string", required: true },
    });

    const outputSchema = createSimpleSchema({
      status: { type: "number", required: true },
      data: { type: "any", required: true },
    });

    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
        inputSchema,
        outputSchema,
      });
    }
  };

  const executeWhatsAppMessage = async (inputs: Record<string, string>) => {
    try {
      setIsLoading(true);
      setError(null);
      const message = inputs.text_msg;

      const result = await sendWhatsAppMessage(message, {
        token: data.token,
        to_number: data.to_number,
        business_number: data.business_number,
      });

      setResponse(JSON.stringify(result, null, 2));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(errorMessage);
      setResponse(`Error: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Header */}
        <NodeHeader
          iconName={"message-circle"}
          title={"WhatsApp Message Output"}
          subtitle={"Send a message via WhatsApp Business"}
          color={colors.header}
          onSettings={() => setIsEditDialogOpen(true)}
          onTest={() => setIsTestDialogOpen(true)}
        />

        {/* Body */}
        <NodeContent
          data={[
            {
              label: "API Token",
              value: "●".repeat(data.token.length),
            },
            {
              label: "Business Phone Number",
              value: data.business_number,
            },
            {
              label: "Recipient Number",
              value: data.to_number,
            },
          ]}
        />

        {/* Handles */}
        {data.handlers?.map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={
              handler.type === "source" ? Position.Right : Position.Left
            }
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{
              top: `${(index + 1) * (100 / (data.handlers?.length || 1))}%`,
            }}
          />
        ))}
      </div>

      {/* Edit Dialog */}
      <WhatsAppOutputDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
      />

      {/* Test Dialog */}
      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={data.name || "Test WhatsApp Message"}
        description="Send a test message using the configured WhatsApp API."
        inputFields={[
          { id: "text_msg", label: "Message", type: "string", required: true },
        ]}
        onRun={executeWhatsAppMessage}
        output={response}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default WhatsAppOutputNode;

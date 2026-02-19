import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { UserInputNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { UserInputDialog } from "../../nodeDialogs/UserInputDialog";
import { NodeContentRow } from "../nodeContent";

export const USER_INPUT_NODE_TYPE = "userInputNode";

const UserInputNode: React.FC<NodeProps<UserInputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(USER_INPUT_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const color = getNodeColor(nodeDefinition?.category || "io");

  const onUpdate = (updatedData: UserInputNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const fieldsSummary =
    data.form_fields && data.form_fields.length > 0
      ? data.form_fields.map((f) => `${f.label}${f.required ? "*" : ""}`).join(", ")
      : undefined;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Message",
      value: data.message,
      placeholder: "No message set",
    },
    {
      label: "Fields",
      value: fieldsSummary,
      placeholder: "No fields configured",
    },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition?.icon || "ClipboardList"}
        title={data.name || nodeDefinition?.label || "User Input"}
        subtitle={nodeDefinition?.shortDescription}
        color={color}
        nodeType={USER_INPUT_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <UserInputDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={USER_INPUT_NODE_TYPE}
      />
    </>
  );
};

export default UserInputNode;

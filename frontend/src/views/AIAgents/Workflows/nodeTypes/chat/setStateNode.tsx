import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { SetStateDialog } from "../../nodeDialogs/SetStateDialog";
import { SetStateNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";

export const SET_STATE_NODE_TYPE = "setStateNode";

const SetStateNode: React.FC<NodeProps<SetStateNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SET_STATE_NODE_TYPE);
  const color = getNodeColor(nodeDefinition?.category || "io");
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<SetStateNodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Build node content from states array or legacy fields
  const getNodeContent = (): NodeContentRow[] => {
    const content: NodeContentRow[] = [];

    data.states.forEach((state, index) => {
      if (state.key) {
        content.push({
          label: `State ${index + 1}: ${state.key}`,
          value: state.value || "",
        });
      }
    });

    content.push({
      label: "Variables",
      value: extractDynamicVariablesAsRecord(JSON.stringify(data)),
      areDynamicVars: true,
    });

    return content;
  };

  const nodeContent: NodeContentRow[] = getNodeContent();

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition?.icon || "Database"}
        title={data.name || nodeDefinition?.label || "Set State"}
        subtitle={
          nodeDefinition?.shortDescription || "Set stateful parameter value"
        }
        color={color}
        nodeType={SET_STATE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <SetStateDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SET_STATE_NODE_TYPE}
      />
    </>
  );
};

export default SetStateNode;

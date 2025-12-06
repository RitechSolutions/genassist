import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { PythonCodeNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { PythonCodeDialog } from "../../nodeDialogs/PythonCodeDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";

export const PYTHON_CODE_NODE_TYPE = "pythonCodeNode";

const PythonCodeNode: React.FC<NodeProps<PythonCodeNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(PYTHON_CODE_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  // Get code preview (first few lines)
  const getCodePreview = () => {
    if (!data.code) return "";
    const lines = data.code?.split("\n");
    if (lines?.length <= 3) return data.code;
    return lines?.slice(0, 3).join("\n") + "\n...";
  };

  const onUpdate = (updatedData: PythonCodeNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<PythonCodeNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition.icon}
        title={data.name || nodeDefinition.label}
        subtitle={nodeDefinition.shortDescription}
        color={color}
        nodeType="pythonCodeNode"
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Node content */}
        <NodeContent
          data={[
            {
              label: "Python Script",
              value: getCodePreview(),
              isMono: true,
              hasMultipleLines: true,
            },
            {
              label: "Variables",
              value: extractDynamicVariablesAsRecord(JSON.stringify(data)),
            },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <PythonCodeDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={PYTHON_CODE_NODE_TYPE}
      />
    </>
  );
};

export default PythonCodeNode;

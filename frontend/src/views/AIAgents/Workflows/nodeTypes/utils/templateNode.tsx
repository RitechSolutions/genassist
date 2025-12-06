import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { TemplateNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { TemplateNodeDialog } from "../../nodeDialogs/TemplateNodeDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";

export const TEMPLATE_NODE_TYPE = "templateNode";

const TemplateNode: React.FC<NodeProps<TemplateNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(TEMPLATE_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<TemplateNodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate = {
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
        nodeType={TEMPLATE_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            {
              label: "Template",
              value: data.template,
            },
            {
              label: "Variables",
              value: extractDynamicVariablesAsRecord(data.template),
            },
          ]}
        />
      </BaseNodeContainer>

      <TemplateNodeDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TEMPLATE_NODE_TYPE}
      />
    </>
  );
};

export default TemplateNode;

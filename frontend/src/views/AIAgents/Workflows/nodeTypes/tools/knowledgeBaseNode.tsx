import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { KnowledgeBaseNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { KnowledgeBaseDialog } from "../../nodeDialogs/KnowledgeBaseDialog";
import { KnowledgeItem } from "@/interfaces/knowledge.interface";
import { getAllKnowledgeItems } from "@/services/api";
import nodeRegistry from "../../registry/nodeRegistry";

export const KNOWLEDGE_BASE_NODE_TYPE = "knowledgeBaseNode";

const KnowledgeBaseNode: React.FC<NodeProps<KnowledgeBaseNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(KNOWLEDGE_BASE_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [availableBases, setAvailableBases] = useState<KnowledgeItem[]>([]);

  const color = getNodeColor(nodeDefinition.category);

  // Fetch all available bases to map IDs to names for display
  useEffect(() => {
    const loadKnowledgeBases = async () => {
      try {
        const bases = await getAllKnowledgeItems();
        setAvailableBases(bases);
      } catch (err) {
        // ignore
      }
    };
    loadKnowledgeBases();
  }, []);

  const onUpdate = (updatedData: KnowledgeBaseNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<KnowledgeBaseNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  }, [data.inputSchema, data.outputSchema]);

  // Find the names of selected bases using the fetched list
  const selectedBasesNames = availableBases
    .filter((base) => data.selectedBases?.includes(base.id))
    .map((base) => base.name)
    .join(", ");

  const displayValue = selectedBasesNames;

  // Find the names of selected bases using the fetched list
  const selectedBasesNames = availableBases
    .filter((base) => data.selectedBases?.includes(base.id))
    .map((base) => base.name)
    .join(", ");

  const displayValue = selectedBasesNames;

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
        nodeType={KNOWLEDGE_BASE_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Node content now displays names instead of count */}
        <NodeContent
          data={[
            { label: "Query", value: data.query },
            { label: "Limit", value: data.limit.toString() },
            { label: "Force Limit", value: data.force ? "On" : "Off" },
            { label: "Knowledge Bases", value: displayValue },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <KnowledgeBaseDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={KNOWLEDGE_BASE_NODE_TYPE}
      />
    </>
  );
};

export default KnowledgeBaseNode;

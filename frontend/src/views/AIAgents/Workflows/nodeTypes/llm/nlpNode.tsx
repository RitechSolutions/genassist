import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { NlpNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { NlpDialog } from "../../nodeDialogs/NlpDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { getLLMProvider } from "@/services/llmProviders";

const NLP_NODE_TYPE = "nlpNode";

const TASK_LABELS: Record<string, string> = {
  classify: "Classify",
  sentiment: "Sentiment",
  extract: "Extract",
  summarize: "Summarize",
};

const NlpNode: React.FC<NodeProps<NlpNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(NLP_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");

  useEffect(() => {
    if (data.providerId) {
      getLLMProvider(data.providerId).then((provider) => {
        if (provider) {
          setProviderName(
            `${provider.name} (${provider.llm_model_provider} - ${provider.llm_model})`,
          );
        }
      });
    }
  }, [data.providerId]);

  const onUpdate = (updatedData: NlpNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const task = data.task ?? "classify";

  const taskContent: NodeContentRow[] = (() => {
    switch (task) {
      case "classify":
        return [
          {
            label: "Categories",
            value: (data.categories ?? []).join(", "),
          },
          {
            label: "Multi-label",
            value: data.multiLabel ? "true" : "false",
            isSelection: true,
          },
        ];
      case "sentiment":
        return [{ label: "Scale", value: data.scale, isSelection: true }];
      case "extract":
        return [{ label: "Schema", value: data.schema }];
      case "summarize":
        return [
          {
            label: "Max Length",
            value:
              data.maxLength !== undefined ? String(data.maxLength) : "",
          },
          { label: "Style", value: data.style, isSelection: true },
        ];
      default:
        return [];
    }
  })();

  const nodeContent: NodeContentRow[] = [
    { label: "LLM Provider", value: providerName || "—" },
    { label: "Task", value: TASK_LABELS[task] ?? task, isSelection: true },
    { label: "Input Field", value: data.inputField },
    ...taskContent,
  ];

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
        nodeType={NLP_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <NlpDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={NLP_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(NlpNode);

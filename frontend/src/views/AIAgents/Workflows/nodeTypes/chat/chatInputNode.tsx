import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { ChatInputNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { ParameterSection } from "../../components/custom/ParameterSection";
import { NodeSchema, SchemaField } from "../../types/schemas";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";

export const CHAT_INPUT_NODE_TYPE = "chatInputNode";

const ChatInputNode: React.FC<NodeProps<ChatInputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(CHAT_INPUT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [dynamicParams, setDynamicParams] = useState<NodeSchema>(
    data.inputSchema
  );

  // Update local state when the input schema changes (e.g., when loading from JSON)
  useEffect(() => {
    if (data.inputSchema) {
      setDynamicParams(data.inputSchema);
    }
  }, [data.inputSchema]);

  // Update node data when schema changes
  useEffect(() => {
    data.updateNodeData?.(id, {
      ...data,
      inputSchema: dynamicParams,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dynamicParams]);

  const addItem = (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    template: SchemaField
  ) => {
    const newName = `param_${Date.now()}`;
    setter((prev) => ({
      ...prev,
      [newName]: template,
    }));
  };

  const removeItem = (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    name: string
  ) => {
    setter((prev) => {
      const newParams = { ...prev };
      delete newParams[name];
      return newParams;
    });
  };

  return (
    <BaseNodeContainer
      id={id}
      data={data}
      selected={selected}
      iconName={nodeDefinition.icon}
      title={data.name || nodeDefinition.label}
      subtitle={nodeDefinition.shortDescription}
      color={color}
      nodeType={CHAT_INPUT_NODE_TYPE}
    >
      {/* Node content */}
      <div className="p-4 mx-0.5 mb-0.5 bg-white rounded-sm">
        <ParameterSection
          dynamicParams={dynamicParams}
          setDynamicParams={setDynamicParams}
          addItem={addItem}
          removeItem={removeItem}
        />
      </div>
    </BaseNodeContainer>
  );
};

export default ChatInputNode;

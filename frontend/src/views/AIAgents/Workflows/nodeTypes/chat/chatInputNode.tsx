import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { Play } from "lucide-react";
import { ChatInputNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { ParameterSection } from "../../components/custom/ParameterSection";
import { NodeSchema, SchemaField } from "../../types/schemas";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { Button } from "@/components/button";
import { useNodeActions } from "../../context/NodeActionsContext";

export const CHAT_INPUT_NODE_TYPE = "chatInputNode";

const DEFAULT_SUGGESTED_PARAMS: NodeSchema = {
  thread_id: {
    type: "string",
    description: "The thread id of the parameter",
    required: false,
  },
    conversation_history: {
    type: "string",
    description: "The conversation history",
    required: false,
    stateful: true,
  },
  language: {
    type: "string",
    description: "The language of the conversation",
    required: false,
  },
};

const ChatInputNode: React.FC<NodeProps<ChatInputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(CHAT_INPUT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const nodeActions = useNodeActions();
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
    <div className="relative">
      {/* Inline "Test" affordance for the Start node. It's the workflow entry
          point, so testing straight from here runs the whole graph (opens the
          Executions panel). Shown when the node is selected and sits to the LEFT
          of the node — the node's only handle is the output on the right. */}
      {selected && nodeActions?.testWorkflow && (
        <div className="absolute right-full top-1/2 z-30 -translate-y-1/2 pr-3 nodrag nopan pointer-events-auto">
          <Button
            size="sm"
            onClick={() => nodeActions?.testWorkflow()}
            className="gap-1.5 rounded-full whitespace-nowrap shadow-md"
            title="Run the whole workflow with a test input"
          >
            <Play className="h-3.5 w-3.5" />
            Test
          </Button>
        </div>
      )}

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
        <div className="p-4 mx-0.5 mb-0.5 bg-card rounded-sm">
          <ParameterSection
            dynamicParams={dynamicParams}
            setDynamicParams={setDynamicParams}
            addItem={addItem}
            removeItem={removeItem}
            suggestParams={true}
            listSuggestedParams={DEFAULT_SUGGESTED_PARAMS}
            allowStateful={true}
            allowFilter={true}
            allowHidden={true}
          />
        </div>
      </BaseNodeContainer>
    </div>
  );
};

export default React.memo(ChatInputNode);

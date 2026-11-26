import React, { useState, useEffect } from "react";
import { NodeSchema, SchemaField } from "../types/schemas";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
import { Label } from "@/components/label";
import { ParameterSection } from "./custom/ParameterSection";
import { ToolBaseNodeData } from "../types/nodes";
import { Switch } from "@/components/switch";
import { generateTemplateFromInputSchema } from "../utils/helpers";

interface ToolDefinitionSectionProps {
  toolDefinition: ToolBaseNodeData;
  onToolDefinitionChange: (definition: ToolBaseNodeData) => void;
}

export const ToolDefinitionSection: React.FC<ToolDefinitionSectionProps> = ({
  toolDefinition,
  onToolDefinitionChange,
}) => {
  const [name, setName] = useState(toolDefinition.name);
  const [description, setDescription] = useState(toolDefinition.description);
  const [inputSchema, setInputSchema] = useState<NodeSchema>(
    toolDefinition.inputSchema
  );
  const [returnDirect, setReturnDirect] = useState(toolDefinition.returnDirect);
  const [skipToolResultCheck, setSkipToolResultCheck] = useState(
    toolDefinition.skipToolResultCheck
  );
  // Update local state when props change
  useEffect(() => {
    setName(toolDefinition.name);
    setDescription(toolDefinition.description);
    setInputSchema(toolDefinition.inputSchema);
    setReturnDirect(toolDefinition.returnDirect);
    setSkipToolResultCheck(toolDefinition.skipToolResultCheck);
  }, [toolDefinition]);

  // Notify parent of changes
  useEffect(() => {
    onToolDefinitionChange({
      name,
      description,
      inputSchema,
      returnDirect,
      skipToolResultCheck,
      forwardTemplate: generateTemplateFromInputSchema(inputSchema),
    });
  }, [
    name,
    description,
    inputSchema,
    returnDirect,
    skipToolResultCheck,
    onToolDefinitionChange,
  ]);

  const addItem = (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    template: SchemaField
  ) => {
    const newName = `param_${Object.keys(inputSchema).length + 1}`;
    setter((prev) => {
      const newParams = {
        ...prev,
        [newName]: template,
      };
      return newParams;
    });
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
    <div className="space-y-4 w-full min-w-0">
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter tool name"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <RichTextarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Enter a description for this tool"
          size="body"
          className="w-full text-base"
        />
      </div>
      <div className="space-y-2 w-full flex items-center">
        <Label className="w-full" htmlFor="returnDirect">
          Return data directly as agent output
        </Label>
        <Switch
          id="returnDirect"
          checked={returnDirect}
          onCheckedChange={setReturnDirect}
        />
      </div>
      <div className="flex w-full items-center gap-4">
        <div className="w-full space-y-0.5">
          <Label htmlFor="skipToolResultCheck">
            Skip the Guardrails tool result check
          </Label>
          <p className="text-xs text-muted-foreground">
            For a tool that returns your own data, such as a lookup you wrote.
            Leave it off for knowledge bases, web pages and other outside
            content.
          </p>
        </div>
        <Switch
          id="skipToolResultCheck"
          checked={!!skipToolResultCheck}
          onCheckedChange={setSkipToolResultCheck}
        />
      </div>
      <ParameterSection
        label="Required Parameters"
        dynamicParams={inputSchema}
        setDynamicParams={setInputSchema}
        addItem={addItem}
        removeItem={removeItem}
        suggestParams={true}
      />
    </div>
  );
};

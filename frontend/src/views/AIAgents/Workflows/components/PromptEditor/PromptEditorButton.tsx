import React, { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { PromptEditorDialog } from "./PromptEditorDialog";

export interface PromptEditorButtonProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  currentValue: string;
  onPromptChange: (newValue: string) => void;
  defaultProviderId?: string;
}

export const PromptEditorButton: React.FC<PromptEditorButtonProps> = ({
  workflowId,
  nodeId,
  promptField,
  currentValue,
  onPromptChange,
  defaultProviderId,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => setIsOpen(true)}
          >
            <Sparkles className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Prompt Editor</TooltipContent>
      </Tooltip>

      <PromptEditorDialog
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        workflowId={workflowId}
        nodeId={nodeId}
        promptField={promptField}
        currentValue={currentValue}
        onPromptChange={onPromptChange}
        defaultProviderId={defaultProviderId}
      />
    </>
  );
};

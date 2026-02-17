import React, { useEffect, useState } from "react";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { Switch } from "@/components/switch";
import { BaseLLMNodeData } from "../types/nodes";
import { DraggableTextArea } from "./custom/DraggableTextArea";
import { Input } from "@/components/input";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";

export interface ModelConfigurationProps {
  id: string;
  config: BaseLLMNodeData;
  onConfigChange: (config: BaseLLMNodeData) => void;
  typeSelect: "agent" | "model";
}

export const ModelConfiguration: React.FC<ModelConfigurationProps> = ({
  id,
  config,
  onConfigChange,
  typeSelect = "model",
}) => {
  const [systemPrompt, setSystemPrompt] = useState(config.systemPrompt);
  const [userPrompt, setUserPrompt] = useState(config.userPrompt);
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });

  // Reset local state when config changes
  useEffect(() => {
    setSystemPrompt(config.systemPrompt);
    setUserPrompt(config.userPrompt);
  }, [config]);

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find((p) => p.id === providerId);
    if (provider) {
      onConfigChange({
        ...config,
        providerId,
      });
    }
  };

  useEffect(() => {
    if (config.providerId === undefined && providers.length > 0) {
      handleProviderSelect(providers[0].id);
    }
  }, []);

  const handleAgentTypeSelect = (type: BaseLLMNodeData["type"]) => {
    onConfigChange({
      ...config,
      type,
    });
  };

  const handleSystemPromptChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    const newValue = e.target.value;
    setSystemPrompt(newValue);
    onConfigChange({
      ...config,
      systemPrompt: newValue,
    });
  };

  const handleUserPromptChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    const newValue = e.target.value;
    setUserPrompt(newValue);
    onConfigChange({
      ...config,
      userPrompt: newValue,
    });
  };

  const handleMemoryChange = (checked: boolean) => {
    onConfigChange({
      ...config,
      memory: checked,
    });
  };

  const handleMemoryTrimmingModeChange = (mode: "message_count" | "token_budget") => {
    onConfigChange({
      ...config,
      memoryTrimmingMode: mode,
    });
  };

  const handleMaxMessagesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({
      ...config,
      maxMessages: Number.parseInt(e.target.value) || 10,
    });
  };

  const handleTokenBudgetChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({
      ...config,
      tokenBudget: Number.parseInt(e.target.value) || 10000,
    });
  };

  const handleConversationHistoryTokensChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({
      ...config,
      conversationHistoryTokens: Number.parseInt(e.target.value) || 5000,
    });
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    onConfigChange({
      ...config,
      name: newValue,
    });
  };

  const providerId = config.providerId;
  return (
    <TooltipProvider>
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={`name-input-${id}`}>Node Name</Label>
        <Input
          id={`name-input-${id}`}
          value={config.name || ""}
          onChange={handleNameChange}
          placeholder={
            typeSelect === "agent" ? "e.g., Agent" : "e.g., LLM Model"
          }
          className="w-full"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`provider-select-${id}`}>Select Provider</Label>
        <Select
          value={providerId || ""}
          onValueChange={(val) => {
            if (val === "__create__") {
              setIsCreateProviderOpen(true);
              return;
            }
            handleProviderSelect(val);
          }}
        >
          <SelectTrigger id={`provider-select-${id}`} className="w-full">
            <SelectValue placeholder="Select provider" />
          </SelectTrigger>
          <SelectContent>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} -{" "}
                {provider.llm_model})
              </SelectItem>
            ))}
            <CreateNewSelectItem />
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`system-prompt-input-${id}`}>System Prompt</Label>
        <DraggableTextArea
          id={`system-prompt-input-${id}`}
          value={systemPrompt}
          onChange={handleSystemPromptChange}
          placeholder="Enter system prompt"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`user-prompt-input-${id}`}>User Prompt</Label>
        <DraggableTextArea
          id={`user-prompt-input-${id}`}
          value={userPrompt}
          onChange={handleUserPromptChange}
          placeholder="Enter user prompt"
        />
      </div>
      {typeSelect && (
        <div className="flex flex-row gap-2 space-y-2 w-full justify-center items-center">
          <div className="flex-1 space-y-2">
            <Label htmlFor={`agent-type-select-${id}`}>Select Agent Type</Label>
            <Select
              value={config.type}
              onValueChange={handleAgentTypeSelect}
              defaultValue={typeSelect === "agent" ? "ToolSelector" : "Base"}
            >
              <SelectTrigger id={`agent-type-select-${id}`} className="w-full">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              {typeSelect === "agent" && (
                <SelectContent>
                  <SelectItem value="ReActAgent">ReActAgent</SelectItem>
                  <SelectItem value="ToolSelector">ToolSelector</SelectItem>
                  <SelectItem value="SimpleToolExecutor">
                    SimpleToolExecutor
                  </SelectItem>
                  <SelectItem value="ReActAgentLC">ReActAgentLC</SelectItem>
                </SelectContent>
              )}
              {typeSelect === "model" && (
                <SelectContent>
                  <SelectItem value="Base">Base</SelectItem>
                  <SelectItem value="Chain-of-Thought">
                    Chain-of-Thought
                  </SelectItem>
                </SelectContent>
              )}
            </Select>
          </div>
          {typeSelect === "agent" && (
            <div className="space-y-2">
              <Label htmlFor={`system-prompt-input-${id}`}>
                Max Iterations
              </Label>
              <Input
                id={`max-iterations-input-${id}`}
                value={config.maxIterations}
                type="number"
                onChange={(e) =>
                  onConfigChange({
                    ...config,
                    maxIterations: parseInt(e.target.value),
                  })
                }
                placeholder="Enter max iterations"
              />
            </div>
          )}
        </div>
      )}
      <div className="space-y-2 flex items-center gap-2 w-full">
        <Label htmlFor={`memory-switch-${id}`}>Enable Memory</Label>
        <div className="flex-1" />
        <Switch
          id={`memory-switch-${id}`}
          checked={config.memory}
          onCheckedChange={handleMemoryChange}
        />
      </div>
      {config.memory && (
        <>
          <div className="space-y-2">
            <Label htmlFor={`memory-trimming-mode-${id}`}>Memory Trimming Mode</Label>
            <Select
              value={config.memoryTrimmingMode || "message_count"}
              onValueChange={handleMemoryTrimmingModeChange}
            >
              <SelectTrigger id={`memory-trimming-mode-${id}`} className="w-full">
                <SelectValue placeholder="Select trimming mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="message_count">Last N Messages</SelectItem>
                <SelectItem value="token_budget">Token Budget</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {config.memoryTrimmingMode === "message_count" || !config.memoryTrimmingMode ? (
            <div className="space-y-2">
              <Label htmlFor={`max-messages-${id}`}>Max Messages</Label>
              <Input
                id={`max-messages-${id}`}
                type="number"
                min={1}
                step={1}
                value={config.maxMessages || 10}
                onChange={handleMaxMessagesChange}
                placeholder="10"
              />
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`token-budget-${id}`}>Total Token Budget</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Total token budget info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Includes user prompt, system prompt & message history (RAG not included)
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`token-budget-${id}`}
                  type="number"
                  min={1000}
                  max={50000}
                  step={100}
                  value={config.tokenBudget || 10000}
                  onChange={handleTokenBudgetChange}
                  placeholder="10000"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`conversation-history-tokens-${id}`}>Conversation History Allocation (tokens)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Conversation history allocation info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      estimate 0.75 words = 1 token
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`conversation-history-tokens-${id}`}
                  type="number"
                  min={0}
                  max={20000}
                  step={100}
                  value={config.conversationHistoryTokens || 5000}
                  onChange={handleConversationHistoryTokensChange}
                  placeholder="5000"
                />
              </div>
            </>
          )}
        </>
      )}
      <LLMProviderDialog
        isOpen={isCreateProviderOpen}
        onOpenChange={(open) => setIsCreateProviderOpen(open)}
        onProviderSaved={(prov) => {
          queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
          if (prov?.id) {
            handleProviderSelect(prov.id);
          }
          setIsCreateProviderOpen(false);
        }}
        mode="create"
      />
    </div>
    </TooltipProvider>
  );
};

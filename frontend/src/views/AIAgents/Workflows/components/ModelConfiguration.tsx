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
import { Info, X } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { Badge } from "@/components/badge";

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
  const [entityInput, setEntityInput] = useState("");
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

  const handleMemoryTrimmingModeChange = (mode: "message_count" | "token_budget" | "message_compacting" | "rag_retrieval") => {
    onConfigChange({
      ...config,
      memoryTrimmingMode: mode,
    });
  };

  const handleRagPassthroughThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragPassthroughThreshold: Number.parseInt(e.target.value) || 30 });
  };

  const handleRagGroupSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragGroupSize: Number.parseInt(e.target.value) || 4 });
  };

  const handleRagGroupOverlapChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragGroupOverlap: Number.parseInt(e.target.value) || 0 });
  };

  const handleRagQueryContextMessagesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragQueryContextMessages: Number.parseInt(e.target.value) || 3 });
  };

  const handleRagTopKChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragTopK: Number.parseInt(e.target.value) || 3 });
  };

  const handleRagRecentMessagesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragRecentMessages: Number.parseInt(e.target.value) || 6 });
  };

  const handleRagMaxHistoryHoursChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, ragMaxHistoryHours: Number.parseInt(e.target.value) || 0 });
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

  const handleCompactingThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({
      ...config,
      compactingThreshold: Number.parseInt(e.target.value) || 20,
    });
  };

  const handleCompactingKeepRecentChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({
      ...config,
      compactingKeepRecent: Number.parseInt(e.target.value) || 10,
    });
  };

  const handleCompactingModelChange = (providerId: string) => {
    onConfigChange({
      ...config,
      compactingModel: providerId,
    });
  };

  const handleAddImportantEntity = () => {
    const trimmed = entityInput.trim();
    if (!trimmed) return;
    const current = config.compactingImportantEntities || [];
    if (current.includes(trimmed)) return;
    onConfigChange({
      ...config,
      compactingImportantEntities: [...current, trimmed],
    });
    setEntityInput("");
  };

  const handleRemoveImportantEntity = (entity: string) => {
    const current = config.compactingImportantEntities || [];
    onConfigChange({
      ...config,
      compactingImportantEntities: current.filter((e) => e !== entity),
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
                <SelectItem value="message_compacting">Message Compacting</SelectItem>
                <SelectItem value="rag_retrieval">RAG Retrieval</SelectItem>
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
          ) : config.memoryTrimmingMode === "message_compacting" ? (
            <>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`compacting-threshold-${id}`}>Compacting Threshold (messages)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Compacting threshold info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Trigger compaction when total messages exceed this count
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`compacting-threshold-${id}`}
                  type="number"
                  min={10}
                  max={100}
                  step={5}
                  value={config.compactingThreshold || 20}
                  onChange={handleCompactingThresholdChange}
                  placeholder="20"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`compacting-keep-recent-${id}`}>Recent Messages to Keep</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Recent messages info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Number of recent messages to include in context (older messages are compacted into summaries)
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`compacting-keep-recent-${id}`}
                  type="number"
                  min={5}
                  max={50}
                  step={5}
                  value={config.compactingKeepRecent || 10}
                  onChange={handleCompactingKeepRecentChange}
                  placeholder="10"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`compacting-model-${id}`}>Compacting Model</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Compacting model info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      LLM provider to use for compaction (defaults to node's provider)
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Select
                  value={config.compactingModel || config.providerId || ""}
                  onValueChange={handleCompactingModelChange}
                >
                  <SelectTrigger id={`compacting-model-${id}`} className="w-full">
                    <SelectValue placeholder="Use node's provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name} ({provider.llm_model_provider} -{" "}
                        {provider.llm_model})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label>Important Entities to Preserve</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Important entities info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Entities that must always be retained in the compaction summary (e.g. "client name", "project ID")
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex gap-2">
                  <Input
                    value={entityInput}
                    onChange={(e) => setEntityInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddImportantEntity();
                      }
                    }}
                    placeholder="e.g. client name"
                    className="flex-1"
                  />
                  <button
                    type="button"
                    onClick={handleAddImportantEntity}
                    className="px-3 py-1.5 rounded-md border border-input bg-background text-sm hover:bg-accent hover:text-accent-foreground"
                  >
                    Add
                  </button>
                </div>
                {(config.compactingImportantEntities || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {(config.compactingImportantEntities || []).map((entity) => (
                      <Badge
                        key={entity}
                        variant="secondary"
                        className="flex items-center gap-1 pr-1"
                      >
                        {entity}
                        <button
                          type="button"
                          onClick={() => handleRemoveImportantEntity(entity)}
                          className="ml-0.5 rounded-full hover:bg-muted-foreground/20"
                          aria-label={`Remove ${entity}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : config.memoryTrimmingMode === "rag_retrieval" ? (
            <>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-passthrough-${id}`}>Passthrough Threshold (messages)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Passthrough threshold info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Below this total message count, all messages are passed verbatim to the LLM without any vector operations.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-passthrough-${id}`}
                  type="number"
                  min={4}
                  max={500}
                  step={1}
                  value={config.ragPassthroughThreshold ?? 30}
                  onChange={handleRagPassthroughThresholdChange}
                  placeholder="30"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-group-size-${id}`}>Group Size (messages)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Group size info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Number of messages per indexed group. Must be even — each pair is one Q&amp;A exchange.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-group-size-${id}`}
                  type="number"
                  min={2}
                  max={20}
                  step={2}
                  value={config.ragGroupSize ?? 4}
                  onChange={handleRagGroupSizeChange}
                  placeholder="4"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-group-overlap-${id}`}>Group Overlap (messages)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Group overlap info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Overlapping messages between consecutive groups, preserving context at group boundaries. Must be less than group size.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-group-overlap-${id}`}
                  type="number"
                  min={0}
                  max={(config.ragGroupSize ?? 4) - 1}
                  step={1}
                  value={config.ragGroupOverlap ?? 2}
                  onChange={handleRagGroupOverlapChange}
                  placeholder="2"
                />
                {(config.ragGroupOverlap ?? 2) >= (config.ragGroupSize ?? 4) && (
                  <p className="text-xs text-destructive">Overlap must be less than group size</p>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-query-context-${id}`}>Query Context Messages</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Query context info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Recent messages combined with the current message to form a richer retrieval query embedding.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-query-context-${id}`}
                  type="number"
                  min={1}
                  max={10}
                  step={1}
                  value={config.ragQueryContextMessages ?? 3}
                  onChange={handleRagQueryContextMessagesChange}
                  placeholder="3"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-top-k-${id}`}>Retrieved Groups (top-k)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Top-k info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Maximum number of historical message groups to retrieve from the vector store per request.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-top-k-${id}`}
                  type="number"
                  min={1}
                  max={10}
                  step={1}
                  value={config.ragTopK ?? 3}
                  onChange={handleRagTopKChange}
                  placeholder="3"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-recent-messages-${id}`}>Recent Messages (verbatim)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Recent messages info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Most recent messages always included verbatim in context alongside the retrieved historical groups.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-recent-messages-${id}`}
                  type="number"
                  min={2}
                  max={50}
                  step={2}
                  value={config.ragRecentMessages ?? 6}
                  onChange={handleRagRecentMessagesChange}
                  placeholder="6"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`rag-max-history-hours-${id}`}>Max History Age (hours)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Max history age info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Exclude retrieved history older than this many hours. Set to 0 to disable (no age limit).
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id={`rag-max-history-hours-${id}`}
                  type="number"
                  min={0}
                  max={8760}
                  step={1}
                  value={config.ragMaxHistoryHours ?? 0}
                  onChange={handleRagMaxHistoryHoursChange}
                  placeholder="0"
                />
              </div>
            </>
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

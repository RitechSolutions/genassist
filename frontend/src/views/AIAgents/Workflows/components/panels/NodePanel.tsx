import React, { useState, useRef, useMemo } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { HelpCircle, Search, Sparkles, Plus, Pencil, Trash2, ArrowUp } from "lucide-react";
import { Input } from "@/components/input";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { getNodeBgColor, getNodeIconColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import type { AssistantMessage } from "@/views/AIAgents/Workflows/utils/assistantActionParser";
import { getActionLabel } from "@/views/AIAgents/Workflows/utils/assistantActionParser";
import FormattedText from "@/components/FormattedText";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  NodeData,
  NodeHelpContent,
  NodeTypeDefinition,
} from "@/views/AIAgents/Workflows/types/nodes";
import { AI_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/llm/helperDefinition";
import { IO_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/io/helperDefinition";
import { ROUTING_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/router/helperDefinition";
import { TOOLS_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/tools/helperDefinition";
import { TRAINING_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/training/helperDefinition";
import { FORMATTING_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/utils/helperDefinition";
import { INTEGRATION_NODES_HELP_CONTENT } from "@/views/AIAgents/Workflows/nodeTypes/integrations/helperDefinition";
import {
  defaultHelpHeaderGradient,
  helpHeaderGradientByCategory,
} from "@/views/AIAgents/Workflows/utils/helpHeaderGradients";

interface NodePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddNode: (nodeType: string) => void;
  messages?: AssistantMessage[];
  isThinking?: boolean;
  activeConversationalTab?: boolean;
  onSendMessage?: (message: string) => void;
}

interface HelpDialogState {
  title: string;
  badgeLabel: string;
  icon: string;
  category: string;
  helpContent: NodeHelpContent;
}

const NodePanel: React.FC<NodePanelProps> = ({
  isOpen,
  onClose,
  onAddNode,
  messages = [],
  isThinking = false,
  activeConversationalTab = false,
  onSendMessage,
}) => {
  const nodeCategories = nodeRegistry.getAllCategories();
  const [draggingNodeType, setDraggingNodeType] = useState<string | null>(null);
  const dragPreviewContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<string>("available");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedHelp, setSelectedHelp] = useState<HelpDialogState | null>(null);
  const [inputMessage, setInputMessage] = useState<string>("");
  const conversationScrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll conversation to bottom
  React.useEffect(() => {
    if (conversationScrollRef.current) {
      conversationScrollRef.current.scrollTop = conversationScrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  // Auto-switch to conversational tab when messages arrive
  React.useEffect(() => {
    if (activeConversationalTab) {
      setActiveTab("conversational");
    }
  }, [activeConversationalTab]);

  const showConversationalTab = useFeatureFlagVisible(FeatureFlags.WORKFLOW.CONVERSATIONAL_TAB);

  const handleSend = () => {
    if (inputMessage.trim() && onSendMessage && !isThinking) {
      onSendMessage(inputMessage.trim());
      setInputMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Handle drag start
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";

    setDraggingNodeType(nodeType);

    if (dragPreviewContainerRef.current) {
      const dragPreview = dragPreviewContainerRef.current.querySelector(
        `[data-node-type="${nodeType}"]`
      ) as HTMLElement;

      if (dragPreview) {
        // Clone the element for the drag operation
        const dragImage = dragPreview.cloneNode(true) as HTMLElement;
        dragImage.style.position = "absolute";
        document.body.appendChild(dragImage);

        // Clean up after a short delay
        setTimeout(() => {
          if (document.body.contains(dragImage)) {
            document.body.removeChild(dragImage);
          }
        }, 100);
      }
    }
  };

  // Handle drag end to reset visual state
  const onDragEnd = () => {
    setDraggingNodeType(null);
  };

  const categoryLabel: Record<string, string> = {
    io: "I/O",
    ai: "AI",
    routing: "Routing",
    integrations: "Integrations",
    formatting: "Formatting",
    tools: "Tools",
    training: "Training",
    utils: "Utils",
  };

  const categoryHelpContent: Record<string, NodeHelpContent | undefined> = {
    io: IO_NODES_HELP_CONTENT,
    ai: AI_NODES_HELP_CONTENT,
    routing: ROUTING_NODES_HELP_CONTENT,
    formatting: FORMATTING_NODES_HELP_CONTENT,
    tools: TOOLS_NODES_HELP_CONTENT,
    training: TRAINING_NODES_HELP_CONTENT,
    integrations: INTEGRATION_NODES_HELP_CONTENT,
  };

  // Filter nodes based on search query
  const filteredNodesByCategory = useMemo(() => {
    if (!searchQuery.trim()) {
      return null; // Return null when no search, will render all categories normally
    }

    const query = searchQuery.toLowerCase();
    const filtered: Record<string, ReturnType<typeof nodeRegistry.getNodeTypesByCategory>> = {};

    nodeCategories.forEach((category) => {
      const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
      const matchingNodes = nodesInCategory.filter(
        (node) =>
          node.label.toLowerCase().includes(query) ||
          node.description.toLowerCase().includes(query)
      );

      if (matchingNodes.length > 0) {
        filtered[category] = matchingNodes;
      }
    });

    return filtered;
  }, [searchQuery, nodeCategories]);

  // Render node categories
  const renderNodeCategories = () => {
    if (nodeCategories.length === 0) {
      return (
        <div className="text-sm text-muted-foreground p-4">
          Loading node categories...
        </div>
      );
    }

    // If searching, use filtered results
    if (searchQuery.trim() && filteredNodesByCategory) {
      const categories = Object.keys(filteredNodesByCategory);
      
      if (categories.length === 0) {
        return (
          <div className="text-sm text-muted-foreground p-4 text-center">
            No nodes found matching "{searchQuery}"
          </div>
        );
      }

      return categories.map((category) => {
        const nodesInCategory = filteredNodesByCategory[category];
        return renderCategorySection(category, nodesInCategory);
      });
    }

    // Otherwise, render all categories
    return nodeCategories.map((category) => {
      const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
      if (nodesInCategory.length === 0) return null;
      return renderCategorySection(category, nodesInCategory);
    });
  };

  // Render a single category section
  const renderCategorySection = (
    category: string,
    nodesInCategory: NodeTypeDefinition<NodeData>[]
  ) => {
    return (
      <div key={category} className="px-4 py-2">
        <div className="flex items-center gap-2 py-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase">
            {categoryLabel[category] ? categoryLabel[category] : category}
          </p>
          {categoryHelpContent[category] && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6 rounded-full text-muted-foreground hover:text-foreground hover:bg-background/90"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setSelectedHelp({
                  title: `${categoryLabel[category] ?? category} Nodes`,
                  badgeLabel: "Category",
                  icon: "Sparkles",
                  category,
                  helpContent: categoryHelpContent[category] as NodeHelpContent,
                });
              }}
              aria-label={`Show details for ${categoryLabel[category] ?? category}`}
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="flex flex-col gap-2">
          {nodesInCategory.map((nodeType) => {
            const isDragging = draggingNodeType === nodeType.type;
            const bgColor = getNodeBgColor(category);
            const iconColor = getNodeIconColor(category);

            return (
              <div
                key={nodeType.type}
                className={`${bgColor} border border-border rounded-lg p-[2px] cursor-pointer transition-all duration-200 select-none ${
                  isDragging
                    ? "opacity-50 scale-95 border-2 border-dashed border-blue-400 bg-blue-50"
                    : "hover:shadow-sm"
                }`}
                onClick={() => onAddNode(nodeType.type)}
                draggable={true}
                onDragStart={(event) => onDragStart(event, nodeType.type)}
                onDragEnd={onDragEnd}
              >
                <div className="flex gap-2 items-center px-4 pr-2 py-2">
                  <div className="shrink-0 w-4 h-4">
                    {renderIcon(nodeType.icon, `h-4 w-4 ${iconColor}`)}
                  </div>
                  <p className="flex-1 text-sm font-semibold text-accent-foreground min-w-0">
                    {nodeType.label}
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 rounded-full text-muted-foreground hover:text-foreground hover:bg-background/90"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setSelectedHelp({
                        title: nodeType.label,
                        badgeLabel:
                          categoryLabel[nodeType.category] ?? nodeType.category,
                        icon: nodeType.icon,
                        category: nodeType.category,
                        helpContent: nodeType.helpContent ?? {
                          intro: nodeType.description,
                          sections: nodeType.shortDescription
                            ? [
                                {
                                  title: "Quick Overview",
                                  body: nodeType.shortDescription,
                                },
                              ]
                            : [],
                        },
                      });
                    }}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                    }}
                    onDragStart={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                    }}
                    aria-label={`Show details for ${nodeType.label}`}
                  >
                    <HelpCircle className="h-4 w-4" />
                  </Button>
                </div>
                <div className="bg-background rounded-md px-4 py-2">
                  <p className="text-sm text-muted-foreground">
                    {nodeType.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderHelpContent = (helpContent: NodeHelpContent) => {
    return (
      <div className="space-y-8">
        <DialogDescription className="text-[18px] leading-8 text-foreground">
          {helpContent.intro}
        </DialogDescription>

        {helpContent.sections?.map((section) => (
          <section key={section.title} className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {section.title}
            </h3>

            {section.body && (
              <p className="text-base leading-7 text-foreground">{section.body}</p>
            )}

            {section.bullets && section.bullets.length > 0 && (
              <ul className="space-y-2 pl-5 text-base leading-7 text-foreground list-disc">
                {section.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            )}

            {section.steps && section.steps.length > 0 && (
              <ol className="space-y-2 pl-5 text-base leading-7 text-foreground list-decimal">
                {section.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
          </section>
        ))}
      </div>
    );
  };

  return (
    <>
      <div
        ref={dragPreviewContainerRef}
        className="fixed pointer-events-none"
        style={{ visibility: "hidden" }}
      ></div>

      <div
        className={`fixed top-2 right-2 h-[calc(100vh-1rem)] w-[360px] bg-primary-foreground shadow-lg rounded-xl transition-transform duration-300 border ${
          selectedHelp ? "z-40" : "z-[1001]"
        } ${
          isOpen ? "translate-x-0" : "translate-x-[calc(100%+0.5rem)]"
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Tabs Header */}
          <div className="p-4">
            {showConversationalTab ? (
              <Tabs
                value={activeTab}
                onValueChange={setActiveTab}
                className="w-full"
              >
                <TabsList className="w-full h-10 bg-muted p-1 rounded-full">
                  <TabsTrigger
                    value="available"
                    aria-label="Available Nodes"
                    className="flex-1 text-sm font-medium rounded-full"
                  >
                    Available Nodes
                  </TabsTrigger>
                  <TabsTrigger
                    value="conversational"
                    aria-label="Conversational AI"
                    className="flex-1 text-sm font-medium rounded-full"
                  >
                    Conversational
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            ) : (
              <h3 className="text-sm font-semibold">Available Nodes</h3>
            )}
          </div>

          {/* Tabs Content */}
          <div className="flex-1 overflow-y-auto bg-background rounded-xl">
            {(activeTab === "available" || !showConversationalTab) && (
              <div className="w-full">
                {/* Search Field */}
                <div className="px-4 pt-4 pb-2 sticky top-0 bg-background z-10">
                  <div className="relative flex items-center">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    <Input
                      type="text"
                      placeholder="Search nodes..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 h-9 text-sm w-full"
                    />
                  </div>
                </div>
                {renderNodeCategories()}
              </div>
            )}
            {showConversationalTab && activeTab === "conversational" && (
              <div className="flex flex-col h-full">
                {/* Messages area */}
                <div ref={conversationScrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                  {messages.length === 0 && !isThinking ? (
                    <div className="flex flex-col items-center justify-center h-full gap-2 text-center py-12">
                      <Sparkles className="h-8 w-8 text-[hsl(var(--brand-300))]" />
                      <p className="text-sm text-muted-foreground">
                        Ask the AI to help build your workflow.
                      </p>
                    </div>
                  ) : (
                    <>
                      {messages.map((msg) => (
                        <div key={msg.id}>
                          {msg.speaker === "customer" ? (
                            <div className="flex justify-end">
                              <div className="max-w-[80%] bg-blue-600 text-white text-sm rounded-2xl rounded-br-md px-4 py-2.5">
                                {msg.text}
                              </div>
                            </div>
                          ) : (
                            <div className="flex gap-2.5">
                              <div className="flex-shrink-0 mt-1">
                                <div className="h-6 w-6 rounded-full bg-[hsl(var(--brand-50))] flex items-center justify-center">
                                  <Sparkles className="h-3.5 w-3.5 text-[hsl(var(--brand-600))]" />
                                </div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-sm text-gray-700 leading-relaxed">
                                  <FormattedText text={msg.text} />
                                </div>
                                {msg.actions && msg.actions.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {msg.actions.map((action) => {
                                      const isAdd = action.type === "add_node";
                                      const isUpdate = action.type === "update_node";
                                      const Icon = isAdd ? Plus : isUpdate ? Pencil : Trash2;
                                      const colorClass = isAdd
                                        ? "bg-green-50 text-green-700 border-green-200"
                                        : isUpdate
                                        ? "bg-blue-50 text-blue-700 border-blue-200"
                                        : "bg-red-50 text-red-700 border-red-200";
                                      const actionKey = `${action.type}-${getActionLabel(action)}`;
                                      return (
                                        <span
                                          key={actionKey}
                                          className={`inline-flex items-center gap-1 text-xs border rounded-full px-2.5 py-1 ${colorClass}`}
                                        >
                                          <Icon className="h-3 w-3" />
                                          {getActionLabel(action)}
                                        </span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                      {isThinking && (
                        <div className="flex gap-2.5">
                          <div className="flex-shrink-0 mt-1">
                            <div className="h-6 w-6 rounded-full bg-[hsl(var(--brand-50))] flex items-center justify-center">
                              <Sparkles className="h-3.5 w-3.5 text-[hsl(var(--brand-600))] animate-pulse" />
                            </div>
                          </div>
                          <div className="text-sm text-gray-400 flex items-center gap-1">
                            <span className="animate-pulse">Thinking</span>
                            <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
                            <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
                            <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
                {/* Input bar */}
                <div className="p-3 border-t border-border">
                  <div className="relative flex items-center">
                    <Sparkles className="absolute left-3 h-4 w-4 text-[hsl(var(--brand-600))] pointer-events-none" />
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask AI to update your workflow..."
                      disabled={isThinking}
                      className="w-full h-10 bg-white rounded-full pl-9 pr-11 text-sm placeholder:text-gray-400 border border-[hsl(var(--brand-600))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--brand-600))]/30 disabled:opacity-50 transition-all"
                    />
                    <button
                      onClick={handleSend}
                      disabled={isThinking || !inputMessage.trim()}
                      className="absolute right-1.5 rounded-full bg-[hsl(var(--brand-600))] hover:opacity-90 disabled:bg-gray-200 disabled:opacity-100 disabled:cursor-not-allowed h-7 w-7 flex items-center justify-center transition-opacity"
                    >
                      <ArrowUp className="h-3.5 w-3.5 text-white" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <Dialog
        open={Boolean(selectedHelp)}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setSelectedHelp(null);
          }
        }}
      >
        <DialogContent className="w-[min(92vw,860px)] max-w-[860px] min-h-[420px] max-h-[90vh] p-0 overflow-hidden rounded-xl border border-gray-200 shadow-2xl">
          {selectedHelp && (
            <div className="flex min-h-[420px] max-h-[90vh] flex-col bg-white">
              <div
                className={`px-10 pt-10 pb-6 ${
                  helpHeaderGradientByCategory[selectedHelp.category] ??
                    defaultHelpHeaderGradient
                }`}
              >
                <div className="flex items-start gap-4">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${getNodeBgColor(
                      selectedHelp.category
                    )}`}
                  >
                    {renderIcon(
                      selectedHelp.icon,
                      `h-5 w-5 ${getNodeIconColor(selectedHelp.category)}`
                    )}
                  </div>
                  <DialogHeader className="m-0 flex-1 space-y-3 text-left">
                    <div className="flex items-center gap-3">
                      <DialogTitle className="text-[32px] font-semibold leading-tight text-foreground">
                        {selectedHelp.title} Help
                      </DialogTitle>
                      <Badge
                        variant="secondary"
                        className="rounded-md px-2.5 py-1 text-[11px] uppercase tracking-[0.14em]"
                      >
                        {selectedHelp.badgeLabel}
                      </Badge>
                    </div>
                  </DialogHeader>
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-10 pb-8 pt-8">
                {renderHelpContent(selectedHelp.helpContent)}
              </div>
              <div className="flex justify-end px-10 pb-10">
                <DialogClose asChild>
                  <Button
                    type="button"
                    variant="secondary"
                    className="h-11 rounded-full px-7 text-base font-medium shadow-sm"
                  >
                    Close
                  </Button>
                </DialogClose>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default NodePanel;

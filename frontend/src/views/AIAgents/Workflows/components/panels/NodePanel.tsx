import React, { useState, useRef, useMemo } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { HelpCircle, Search, Sparkles, Plus, Pencil, Trash2, ArrowUp } from "lucide-react";
import { Input } from "@/components/input";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { getNodeColor, getNodeBgColor, getNodeIconColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import type { AssistantMessage } from "@/views/AIAgents/Workflows/utils/assistantActionParser";
import { getActionLabel } from "@/views/AIAgents/Workflows/utils/assistantActionParser";
import FormattedText from "@/components/FormattedText";

interface NodePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddNode: (nodeType: string) => void;
  messages?: AssistantMessage[];
  isThinking?: boolean;
  activeConversationalTab?: boolean;
  onSendMessage?: (message: string) => void;
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

  const categoryLabel = {
    io: "I/O",
    ai: "AI",
    routing: "Routing",
    integrations: "Integrations",
    formatting: "Formatting",
    tools: "Tools",
    training: "Training",
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
  const renderCategorySection = (category: string, nodesInCategory: ReturnType<typeof nodeRegistry.getNodeTypesByCategory>) => {
    return (
      <div key={category} className="px-4 py-2">
        <div className="flex items-center py-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase">
            {categoryLabel[category] ? categoryLabel[category] : category}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {nodesInCategory.map((nodeType) => {
            const isDragging = draggingNodeType === nodeType.type;
            const color = getNodeColor(category);
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
                  <HelpCircle className="shrink-0 h-4 w-4 text-muted-foreground" />
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

  return (
    <>
      <div
        ref={dragPreviewContainerRef}
        className="fixed pointer-events-none"
        style={{ visibility: "hidden" }}
      ></div>

      <div
        className={`fixed top-2 right-2 h-[calc(100vh-1rem)] w-[360px] bg-primary-foreground shadow-lg rounded-xl transition-transform duration-300 border z-[1001] ${
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
    </>
  );
};

export default NodePanel;

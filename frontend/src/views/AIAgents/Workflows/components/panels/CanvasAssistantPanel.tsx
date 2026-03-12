import React, { useEffect, useRef } from "react";
import { Sparkles, X, Pencil, Trash2, Plus } from "lucide-react";
import type { AssistantMessage } from "../../utils/assistantActionParser";
import { getActionLabel } from "../../utils/assistantActionParser";

interface CanvasAssistantPanelProps {
  messages: AssistantMessage[];
  isThinking: boolean;
  onClose: () => void;
}

const CanvasAssistantPanel: React.FC<CanvasAssistantPanelProps> = ({
  messages,
  isThinking,
  onClose,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  if (messages.length === 0 && !isThinking) return null;

  return (
    <div className="fixed bottom-[5.5rem] left-1/2 -translate-x-1/2 z-30 w-[520px] max-h-[60vh] flex flex-col bg-white/95 backdrop-blur-md rounded-2xl shadow-lg border border-gray-200/60 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
          <Sparkles className="h-4 w-4 text-purple-500" />
          AI Assistant
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
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
                  <div className="h-6 w-6 rounded-full bg-purple-100 flex items-center justify-center">
                    <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {msg.text}
                  </div>
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {msg.actions.map((action, i) => {
                        const isAdd = action.type === "add_node";
                        const isUpdate = action.type === "update_node";
                        const isRemove = action.type === "remove_node";
                        const Icon = isAdd ? Plus : isUpdate ? Pencil : Trash2;
                        const colorClass = isAdd
                          ? "bg-green-50 text-green-700 border-green-200"
                          : isUpdate
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-red-50 text-red-700 border-red-200";
                        return (
                          <span
                            key={i}
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
              <div className="h-6 w-6 rounded-full bg-purple-100 flex items-center justify-center">
                <Sparkles className="h-3.5 w-3.5 text-purple-600 animate-pulse" />
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
      </div>
    </div>
  );
};

export default CanvasAssistantPanel;

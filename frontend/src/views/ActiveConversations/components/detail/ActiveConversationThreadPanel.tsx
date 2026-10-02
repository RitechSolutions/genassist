import { User } from "lucide-react";

import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/helpers/utils";

import { ConversationEntryWrapper } from "../../common/ConversationEntryWrapper";
import { formatDateTime, formatMessageTime } from "../../helpers/format";
import type { ActiveConversationDetailController } from "../../hooks/useActiveConversationDetail";

type ActiveConversationThreadPanelProps = {
  controller: ActiveConversationDetailController;
  className?: string;
};

/**
 * The live message thread plus the takeover / supervisor composer. Extracted from
 * `ActiveConversationDialog` so the Conversations workspace can render it as its own column.
 */
export function ActiveConversationThreadPanel({
  controller,
  className,
}: ActiveConversationThreadPanelProps) {
  const {
    transcript,
    messages,
    scrollRef,
    isThinking,
    hasSupervisorTakeover,
    isCurrentUserSupervisor,
    supervisorDisplayName,
    chatInput,
    setChatInput,
    loading,
    isFinalizing,
    handleTakeOver,
    handleSendMessage,
    handleFinalize,
  } = controller;

  return (
    <div className={cn("flex flex-col h-full min-h-0", className)}>
      <div
        ref={scrollRef}
        className="flex-1 flex flex-col bg-secondary/30 rounded-lg p-3 overflow-y-auto min-h-0"
      >
        {messages.length > 0 ? (
          <div className="space-y-2">
            {transcript.timestamp && (
              <div className="flex justify-center mb-3">
                <div className="px-3 py-1 rounded-full bg-muted text-muted-foreground text-xs">
                  {formatDateTime(transcript.timestamp)}
                </div>
              </div>
            )}
            {messages.map((entry, idx) => {
              if (entry.type === "takeover") {
                return (
                  <div
                    className="flex justify-center my-3"
                    key={`takeover-${idx}-${entry.create_time}`}
                  >
                    <div className="px-3 py-1.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium flex items-center dark:bg-blue-500/20 dark:text-blue-400">
                      <User className="w-3 h-3 mr-1" />
                      {isCurrentUserSupervisor
                        ? "You took over"
                        : `${supervisorDisplayName} took over`}
                    </div>
                  </div>
                );
              }

              const speaker = (entry.speaker || "").toLowerCase();
              const isAdmin = speaker.includes("admin");
              const isAgent =
                speaker.includes("agent") || speaker.includes("operator");
              const isCustomer =
                speaker.includes("customer") || (!isAdmin && !isAgent);
              const speakerName = isAdmin
                ? "Admin"
                : isAgent
                ? "Agent"
                : isCustomer
                ? "Customer"
                : "Unknown";
              if (!entry.text || !entry.text.trim()) return null;

              return (
                <div
                  key={`${transcript.id}-message-${idx}-${entry.create_time}`}
                  className="message-container"
                >
                  <div
                    className={`flex flex-col ${
                      isAgent ? "items-end" : "items-start"
                    }`}
                  >
                    <span className="text-[11px] text-foreground font-medium mb-1">
                      {speakerName}
                    </span>
                    <div
                      className={`p-2 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words ${
                        isAgent
                          ? "bg-blue-500 text-white rounded-tl-lg"
                          : "bg-muted text-foreground rounded-tr-lg"
                      }`}
                    >
                      <ConversationEntryWrapper
                        entry={entry}
                        conversationId={transcript.id}
                      />
                      <span
                        className={`block text-[10px] text-right mt-1 ${
                          isAgent ? "text-white/70" : "text-muted-foreground"
                        }`}
                      >
                        {formatMessageTime(entry.create_time)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {isThinking && !isCurrentUserSupervisor && (
              <div className="flex flex-col items-end">
                <span className="text-[11px] text-foreground font-medium mb-1">
                  Agent
                </span>
                <div className="p-3 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words bg-blue-500 text-white rounded-tl-lg">
                  <div className="flex items-center space-x-1">
                    <div
                      className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                      style={{ animationDelay: "0ms" }}
                    ></div>
                    <div
                      className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    ></div>
                    <div
                      className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center text-muted-foreground py-6">
            No messages yet.
          </div>
        )}
      </div>

      <div className="mt-4 space-y-3">
        {!hasSupervisorTakeover ? (
          <Button
            onClick={handleTakeOver}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
            disabled={loading || transcript.status === "complete"}
          >
            {loading ? "Processing..." : "Take Over Conversation"}
          </Button>
        ) : isCurrentUserSupervisor ? (
          <>
            <div className="flex items-center gap-2">
              <Input
                className="flex-1"
                placeholder="Type a message as Admin..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              />
              <Button
                onClick={handleSendMessage}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white"
              >
                Send
              </Button>
            </div>
            <Button
              onClick={handleFinalize}
              className="bg-destructive text-destructive-foreground w-full"
              disabled={isFinalizing}
            >
              {isFinalizing ? "Finalizing..." : "Finalize Conversation"}
            </Button>
          </>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/30 dark:bg-amber-500/15">
            <div className="flex items-start gap-3">
              <User className="mt-0.5 h-5 w-5 shrink-0 text-amber-700 dark:text-amber-400" />
              <div>
                <p className="text-sm font-medium text-amber-900">
                  Conversation already taken over by{" "}
                  <span className="font-medium">{supervisorDisplayName}</span>
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Coins, GripVertical, Maximize2, MessageSquarePlus, Minimize2, MoreHorizontal, Sparkles, Undo2, X, FlaskConical } from "lucide-react";
import BuilderUsageDialog from "./BuilderUsageDialog";

import { AssistantComposer, type ComposerMentionable } from "@/components/AssistantComposer";
import { GenAssistMark } from "@/components/AssistantEmptyState";
import { HoverGrid } from "@/components/HoverGrid";
import { hasMention, mentionedIds, removeMention } from "@/components/assistantComposerTokens";
import { Button } from "@/components/button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import FormattedText from "@/components/FormattedText";
import { cn } from "@/helpers/utils";
import type { AssistProposal } from "@/services/workflowBuilder";
import type { PendingChange } from "@/views/AIAgents/Workflows/hooks/useCanvasAssistant";
import {
  parseSlashCommand,
  SLASH_COMMANDS,
  type AssistantMessage,
  type LiveTurn,
} from "@/views/AIAgents/Workflows/utils/assistantDraft";
import {
  BUILDER_EXAMPLES,
  BUILDER_INLINE_PLACEHOLDER,
  BUILDER_PLACEHOLDERS,
  EXAMPLES_PREVIEW_COUNT,
  pickBuilderGreeting,
} from "@/views/AIAgents/Workflows/utils/builderExamples";
import { useTypedPlaceholder } from "@/views/AIAgents/Workflows/hooks/useTypedPlaceholder";
import { BUILDER_MESSAGE_MAX_CHARS } from "@/views/AIAgents/Workflows/utils/builderLimits";
import { AssistantMessageExtras, PendingChangeBar } from "./AssistantMessageExtras";
import { MessageActions, ReasoningTrail, Typewriter, WorkSummary } from "./AssistantMotion";
import { MentionedNodesRow, MentionText, NodeChip } from "./NodeChips";

export const ASSISTANT_PANEL_DEFAULT_WIDTH_PX = 530;
const ASSISTANT_PANEL_MIN_WIDTH_PX = 340;

function maxWidthPx(): number {
  if (typeof window === "undefined") return ASSISTANT_PANEL_DEFAULT_WIDTH_PX;
  return Math.max(ASSISTANT_PANEL_MIN_WIDTH_PX, Math.round(window.innerWidth * 0.7));
}
const clampWidth = (w: number) => Math.max(ASSISTANT_PANEL_MIN_WIDTH_PX, Math.min(maxWidthPx(), Math.round(w)));

export interface AssistantPanelProps {
  isOpen: boolean;
  width: number;
  onWidthChange: (width: number) => void;
  /** Fires when a drag-resize starts/ends, so the parent can pause its own transitions. */
  onResizingChange?: (resizing: boolean) => void;
  onClose: () => void;
  messages: AssistantMessage[];
  isThinking: boolean;
  /** The assistant's work in progress (narrated steps, streamed reply), while thinking. */
  liveTurn: LiveTurn | null;
  onSendMessage: (message: string, focusNodeIds?: string[]) => void;
  /** "/explain", "/review", ... typed in the composer. */
  onCommand?: (command: string, rest: string, nodeIds?: string[]) => void;
  /** Nodes the person can @-mention. */
  mentionables: ComposerMentionable[];
  pendingChange: PendingChange | null;
  onKeepChanges: () => void;
  onUndoChanges: () => void;
  onApplyProposal: (messageId: string, proposal: AssistProposal) => void;
  onRunSuggestedTest: (message: string) => void;
  onFocusNode: (nodeId: string, openSettings: boolean) => void;
  /** Answer a question the assistant asked (one of its options or the person's own words). */
  onAnswerQuestion: (messageId: string, answer: string) => void;
  /** Thumbs up or down on a reply. */
  onReactToMessage?: (messageId: string, reaction: "up" | "down" | null) => void;
  simulateActions: boolean;
  onSimulateActionsChange: (value: boolean) => void;
  /** The node selected on the canvas, shown as context in the composer. */
  selectedNodeId: string | null;
  /** Undo everything the assistant changed in response to one of the person's messages. */
  onUndoTurn: (messageId: string) => void;
  /** Forget this chat and start a new conversation with the assistant. */
  onNewChat: () => void;
  /** The server conversation behind this chat, for the Usage dialog; null before the first message. */
  getConversationId?: () => string | null;
}

/**
 * The AI assistant for the workflow: its own panel beside the canvas (the canvas
 * makes room for it), independent of the Available Nodes sheet, resizable from
 * its left edge. Empty, it is one big box in the middle; afterwards a chat with
 * the composer at the bottom.
 */
export const AssistantPanel: React.FC<AssistantPanelProps> = ({
  isOpen,
  width,
  onWidthChange,
  onResizingChange,
  onClose,
  messages,
  isThinking,
  liveTurn,
  onSendMessage,
  onCommand,
  mentionables,
  pendingChange,
  onKeepChanges,
  onUndoChanges,
  onApplyProposal,
  onRunSuggestedTest,
  onFocusNode,
  onAnswerQuestion,
  onReactToMessage,
  simulateActions,
  onSimulateActionsChange,
  selectedNodeId,
  onUndoTurn,
  onNewChat,
  getConversationId,
}) => {
  const [inputMessage, setInputMessage] = useState("");
  // The empty-chat opener: drawn once per panel mount, and again after "New chat".
  const [greeting, setGreeting] = useState(pickBuilderGreeting);
  // Steps the person attached to the next message (picked with "@"), shown as chips.
  const [focusChips, setFocusChips] = useState<ComposerMentionable[]>([]);
  const [showAllExamples, setShowAllExamples] = useState(false);
  // Full screen: the chat takes the whole viewport; the panel keeps its place beside the canvas.
  const [fullscreen, setFullscreen] = useState(false);
  // Usage dialog: tokens and cost of this chat and of all chats. The id is read when it opens.
  const [usageOpen, setUsageOpen] = useState(false);
  const [usageConversationId, setUsageConversationId] = useState<string | null>(null);
  const openUsage = () => {
    setUsageConversationId(getConversationId?.() ?? null);
    setUsageOpen(true);
  };
  useEffect(() => {
    if (!isOpen) setFullscreen(false);
  }, [isOpen]);
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);
  // The person's message whose changes they asked to undo, pending confirmation.
  const [undoCandidate, setUndoCandidate] = useState<AssistantMessage | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Replies already revealed; a re-render must not type them out again.
  const revealedRef = useRef<Set<string>>(new Set());
  const shouldReveal = (msg: AssistantMessage) =>
    !!msg.arrivedAt && Date.now() - msg.arrivedAt < 15_000 && !revealedRef.current.has(msg.id);

  const chipNodes = mentionables.map((m) => ({ id: m.id, name: m.name, type: m.hint }));
  const selectedNode = selectedNodeId ? chipNodes.find((n) => n.id === selectedNodeId) : undefined;
  const focusCanvasNode = (nodeId: string) => onFocusNode(nodeId, false);
  const isEmptyChat = messages.length === 0 && !isThinking;

  // Drag-resize from the left edge. Pointer capture keeps the drag alive over the canvas.
  const resizeStartRef = useRef<{ x: number; width: number } | null>(null);
  const [resizing, setResizing] = useState(false);
  const handleResizeStart = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    resizeStartRef.current = { x: e.clientX, width };
    setResizing(true);
    onResizingChange?.(true);
  };
  const handleResizeMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const start = resizeStartRef.current;
    if (!start) return;
    onWidthChange(clampWidth(start.width + (start.x - e.clientX)));
  };
  const handleResizeEnd = () => {
    if (!resizeStartRef.current) return;
    resizeStartRef.current = null;
    setResizing(false);
    onResizingChange?.(false);
  };

  // When the viewport shrinks, clamp the width so the resize handle stays on screen.
  useEffect(() => {
    if (!isOpen) return;
    const handleWindowResize = () => {
      const max = maxWidthPx();
      if (width > max) onWidthChange(max);
    };
    window.addEventListener("resize", handleWindowResize);
    handleWindowResize();
    return () => window.removeEventListener("resize", handleWindowResize);
  }, [isOpen, width, onWidthChange]);

  // Keep the newest message in view.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isThinking, liveTurn]);

  // The composer owns the trimming, the Enter key and clearing the field.
  // "/command rest" goes to the command handler; "@Name" mentions become the focus of the message.
  const handleSend = useCallback(
    (message: string, focusNodeIds?: string[]) => {
      const chips = focusChips.map((m) => m.id);
      // "@Name" typed in the text adds a step only when no picked chip already covers that name:
      // a tool and the Tool Builder around it often share one, and the pick says which was meant.
      const chipNames = new Set(focusChips.map((m) => m.name.toLowerCase()));
      const nameOf = (id: string) => mentionables.find((m) => m.id === id)?.name.toLowerCase() ?? "";
      const typed = mentionedIds(message, mentionables).filter((id) => !chips.includes(id) && !chipNames.has(nameOf(id)));
      const tagged = focusNodeIds ?? [...chips, ...typed];
      const command = parseSlashCommand(message);
      setFocusChips([]);
      if (command && onCommand) {
        onCommand(command.command, command.rest, tagged);
        return;
      }
      onSendMessage(message, tagged);
    },
    [focusChips, mentionables, onCommand, onSendMessage]
  );

  // Removing a chip also takes its "@Name" out of the field, so the two never disagree.
  const removeFocusChip = (id: string) => {
    const chip = focusChips.find((c) => c.id === id);
    setFocusChips((prev) => prev.filter((c) => c.id !== id));
    if (chip) setInputMessage((prev) => removeMention(prev, chip.name));
  };

  const pickMention = (mention: ComposerMentionable) =>
    setFocusChips((prev) => (prev.some((c) => c.id === mention.id) ? prev : [...prev, mention]));

  // Deleting the "@Name" from the field drops its chip too, the mirror of removeFocusChip.
  useEffect(() => {
    setFocusChips((prev) => {
      const kept = prev.filter((chip) => hasMention(inputMessage, chip.name));
      return kept.length === prev.length ? prev : kept;
    });
  }, [inputMessage]);

  // Inside the composer, bottom-left: whether AI test runs really send or create things.
  const composerToolbar = (
    <>
      <button
        type="button"
        role="switch"
        aria-checked={simulateActions}
        onClick={() => onSimulateActionsChange(!simulateActions)}
        title={
          simulateActions
            ? "AI test runs simulate steps that send or create things (tickets, emails, messages). Click to let them really run."
            : "AI test runs really send and create things. Click to simulate those steps instead."
        }
        className={cn(
          "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-medium transition-colors",
          simulateActions
            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
            : "border-border bg-background text-muted-foreground hover:text-foreground"
        )}
      >
        <FlaskConical className="h-3 w-3" aria-hidden />
        Simulate actions
        <span
          aria-hidden
          className={cn(
            "ml-0.5 inline-flex h-3.5 w-6 items-center rounded-full p-0.5 transition-colors",
            simulateActions ? "bg-emerald-500" : "bg-muted-foreground/40"
          )}
        >
          <span className={cn("h-2.5 w-2.5 rounded-full bg-white transition-transform", simulateActions && "translate-x-2.5")} />
        </span>
      </button>
      {focusChips.length === 0 && selectedNode && !isEmptyChat && (
        <span className="flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
          <span className="shrink-0">Selected:</span>
          <NodeChip node={selectedNode} onClick={focusCanvasNode} soft />
        </span>
      )}
    </>
  );

  // Only the empty page types its placeholder, and only while nothing is written.
  const typedPlaceholder = useTypedPlaceholder(BUILDER_PLACEHOLDERS, isEmptyChat && inputMessage.length === 0);

  const composer = (hero: boolean) => (
    <AssistantComposer
      value={inputMessage}
      onChange={setInputMessage}
      onSubmit={handleSend}
      size={hero ? "hero" : "inline"}
      // A lower box on the empty page, a taller one once the conversation is going.
      minHeightPx={hero ? 56 : 48}
      autoFocus={hero}
      placeholder={hero ? typedPlaceholder : BUILDER_INLINE_PLACEHOLDER}
      busy={isThinking}
      mentionables={mentionables}
      commands={SLASH_COMMANDS}
      onMentionPick={pickMention}
      toolbar={composerToolbar}
      header={
        !hero && focusChips.length > 0
          ? focusChips.map((chip) => (
              <NodeChip
                key={chip.id}
                node={{ id: chip.id, name: chip.name, type: chip.hint }}
                onClick={focusCanvasNode}
                onRemove={removeFocusChip}
              />
            ))
          : undefined
      }
      maxLength={BUILDER_MESSAGE_MAX_CHARS}
    />
  );

  return (
    <>
      <aside
        aria-label="AI assistant"
        aria-hidden={!isOpen}
        className={cn(
          "relative z-[1002] h-full shrink-0 overflow-hidden bg-background",
          isOpen && "border-l border-border",
          // Opening and closing animate the width so the canvas is pushed aside; a drag-resize is immediate.
          !resizing && "transition-[width] duration-300 ease-out"
        )}
        style={{ width: isOpen ? width : 0 }}
      >
        <div
          className={cn(fullscreen ? "fixed inset-0 z-[1500] bg-background" : "absolute right-0 top-0 h-full")}
          style={fullscreen ? undefined : { width }}
        >
        {!fullscreen && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize assistant"
          className="group absolute bottom-0 left-0 top-0 z-20 flex w-2 cursor-col-resize touch-none items-center justify-center transition-colors hover:bg-primary/10"
          onPointerDown={handleResizeStart}
          onPointerMove={handleResizeMove}
          onPointerUp={handleResizeEnd}
          onPointerCancel={handleResizeEnd}
          onDoubleClick={() => onWidthChange(ASSISTANT_PANEL_DEFAULT_WIDTH_PX)}
        >
          <GripVertical className="pointer-events-none h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        )}

        <div className="flex h-full flex-col">
          {/* Header */}
          <div className="flex h-12 shrink-0 items-center gap-2 pl-4 pr-2">
            {/* <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[hsl(var(--brand-50))]">
              <Sparkles className="h-3.5 w-3.5 text-[hsl(var(--brand-600))]" />
            </span> */}
            {/* <span className="text-sm font-semibold text-foreground">Gen Agent</span> */}
            <span className="min-w-0 flex-1" />
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" className="h-8 w-8 rounded-full" title="Chat options" aria-label="Chat options">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" sideOffset={6} className="z-[2100] min-w-[180px]">
                <DropdownMenuItem
                  disabled={isThinking || messages.length === 0}
                  onSelect={() =>
                    setTimeout(() => {
                      setGreeting(pickBuilderGreeting());
                      onNewChat();
                    }, 0)
                  }
                >
                  <MessageSquarePlus className="mr-2 h-4 w-4" />
                  New chat
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setTimeout(() => setFullscreen((value) => !value), 0)}>
                  {fullscreen ? <Minimize2 className="mr-2 h-4 w-4" /> : <Maximize2 className="mr-2 h-4 w-4" />}
                  {fullscreen ? "Exit full screen" : "Full screen"}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setTimeout(openUsage, 0)}>
                  <Coins className="mr-2 h-4 w-4" />
                  Usage
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <BuilderUsageDialog open={usageOpen} onOpenChange={setUsageOpen} conversationId={usageConversationId} />
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 rounded-full"
              onClick={() => (fullscreen ? setFullscreen(false) : onClose())}
              aria-label={fullscreen ? "Exit full screen" : "Close assistant"}
              title={fullscreen ? "Exit full screen" : "Close"}
            >
              {fullscreen ? <Minimize2 className="h-4 w-4" /> : <X className="h-4 w-4" />}
            </Button>
          </div>

          {isEmptyChat ? (
            /* Nothing said yet: one big box in the middle, like a fresh page. */
            <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-5 pb-12 pt-6">
              {/* Something to play with while thinking of what to ask: tiles light up under the pointer. */}
              <HoverGrid className="absolute inset-x-0 bottom-0 h-[30%] [mask-image:linear-gradient(to_bottom,transparent,black_40%)]" />
              <div className="ai-rise-in relative z-10 w-full max-w-[640px]">
                <h2 className="mb-5 flex items-center justify-center gap-2 text-center text-[19px] font-semibold tracking-tight text-foreground">
                  <GenAssistMark className="h-8 w-8 text-zinc-700 dark:text-white" />
                  {greeting}
                </h2>
                {composer(true)}
                {/* The openers step aside as soon as the person starts writing, and return when the field is empty. */}
                <div
                  aria-hidden={inputMessage.trim().length > 0}
                  className={cn(
                    "mt-4 flex flex-wrap items-center justify-center gap-1.5 transition-all duration-300 ease-in-out",
                    inputMessage.trim() ? "pointer-events-none translate-y-2 opacity-0" : "translate-y-0 opacity-100"
                  )}
                >
                  {(showAllExamples ? BUILDER_EXAMPLES : BUILDER_EXAMPLES.slice(0, EXAMPLES_PREVIEW_COUNT)).map((example) => (
                    <button
                      key={example.label}
                      type="button"
                      onClick={() => setInputMessage(example.prompt)}
                      title={example.prompt}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs text-foreground transition-colors hover:border-[hsl(var(--brand-600))]/50 hover:bg-[hsl(var(--brand-600))]/5"
                    >
                      <example.icon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
                      {example.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setShowAllExamples((value) => !value)}
                    className="inline-flex items-center gap-1 px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {showAllExamples ? "Show less" : "See all"}
                    <ArrowRight className={cn("h-3 w-3 transition-transform", showAllExamples && "rotate-90")} />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
                <div className={cn("space-y-4", fullscreen && "mx-auto w-full max-w-3xl")}>
                {messages.map((msg) => (
                  <div key={msg.id}>
                    {msg.speaker === "customer" ? (
                      <div className="group flex items-end justify-end gap-1.5">
                        {msg.undoable && !msg.undone && (
                          <button
                            type="button"
                            onClick={() => setUndoCandidate(msg)}
                            disabled={isThinking}
                            title="Undo everything the assistant changed for this message"
                            aria-label="Undo this message's changes"
                            className="mb-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground opacity-60 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100 disabled:opacity-30"
                          >
                            <Undo2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                        <div
                          className={cn(
                            "max-w-[82%] rounded-2xl rounded-br-md bg-[hsl(var(--brand-600))] px-4 py-2.5 text-sm text-white shadow-sm",
                            msg.undone && "opacity-60 line-through decoration-white/60"
                          )}
                          title={msg.undone ? "The changes for this message were undone" : undefined}
                        >
                          <MentionText text={msg.text} nodes={chipNodes} preferIds={msg.nodeIds} onFocusNode={focusCanvasNode} inverted />
                        </div>
                      </div>
                    ) : (
                      <div className="min-w-0">
                          <WorkSummary steps={msg.steps} workedMs={msg.workedMs} changes={msg.changes} />
                          <div className="text-sm leading-relaxed text-foreground">
                            <Typewriter
                              text={msg.text}
                              animate={!msg.streamed && shouldReveal(msg)}
                              onDone={() => revealedRef.current.add(msg.id)}
                            >
                              <FormattedText text={msg.text} />
                              <MentionedNodesRow text={msg.text} nodes={chipNodes} onFocusNode={focusCanvasNode} />
                            </Typewriter>
                          </div>
                          <AssistantMessageExtras
                            msg={msg}
                            isLatest={msg.id === messages[messages.length - 1]?.id}
                            busy={isThinking}
                            onSend={handleSend}
                            onApplyProposal={onApplyProposal}
                            onRunSuggestedTest={onRunSuggestedTest}
                            onFocusNode={onFocusNode}
                            onAnswer={onAnswerQuestion}
                          />
                          {msg.text.trim() && (
                            <MessageActions
                              text={msg.text}
                              reaction={msg.reaction}
                              onReact={onReactToMessage ? (reaction) => onReactToMessage(msg.id, reaction) : undefined}
                            />
                          )}
                      </div>
                    )}
                  </div>
                ))}
                {isThinking && <ReasoningTrail turn={liveTurn} />}
                </div>
              </div>
              {pendingChange && <PendingChangeBar change={pendingChange} onKeep={onKeepChanges} onUndo={onUndoChanges} />}
              <div className={cn("p-3 pt-0", fullscreen && "mx-auto w-full max-w-3xl")}>
                {composer(false)}
              </div>
            </>
          )}
        </div>
        </div>
      </aside>

      <ConfirmDialog
        isOpen={undoCandidate !== null}
        onOpenChange={(open) => {
          if (!open) setUndoCandidate(null);
        }}
        isInProgress={false}
        title="Undo this change?"
        description={`The canvas goes back to how it was before "${
          (undoCandidate?.text ?? "").length > 80 ? `${undoCandidate?.text.slice(0, 80)}…` : undoCandidate?.text ?? ""
        }". Everything the assistant changed since then is undone as well.`}
        primaryButtonText="Undo"
        onConfirm={async () => {
          if (undoCandidate) onUndoTurn(undoCandidate.id);
          setUndoCandidate(null);
        }}
      />
    </>
  );
};

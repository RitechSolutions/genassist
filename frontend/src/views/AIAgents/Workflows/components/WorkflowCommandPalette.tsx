import { useEffect, useRef } from "react";
import {
  Search,
  X,
  CornerDownLeft,
  Plus,
  Crosshair,
  Sparkles,
  ArrowUp,
} from "lucide-react";
import { renderIcon } from "../utils/iconUtils";
import { getNodeBgColor, getNodeIconColor } from "../utils/nodeColors";

/** An existing node on the canvas that matches the query. */
export interface CommandPaletteExistingResult {
  id: string;
  name: string;
  typeLabel: string;
  icon: string;
  category: string;
}

/** A node type from the registry that can be added as a new node. */
export interface CommandPaletteAddResult {
  type: string;
  label: string;
  description: string;
  icon: string;
  category: string;
}

export type CommandPaletteMode = "search" | "command" | "agent";

interface WorkflowCommandPaletteProps {
  /** Current overlay mode. */
  mode: CommandPaletteMode;
  /** Current input text. */
  query: string;
  /** Called on every keystroke. */
  onQueryChange: (query: string) => void;
  /** Close the overlay entirely (Esc / X button). */
  onClose: () => void;
  /** Enter pressed in search mode — center the viewport on the matched node(s). */
  onSubmit: () => void;
  /** Number of existing nodes currently matching the query (search mode). */
  matchCount: number;
  /** Existing canvas nodes matching the query. */
  existingResults: CommandPaletteExistingResult[];
  /** Registry node types matching the query (offered as "add new"). */
  addResults: CommandPaletteAddResult[];
  /** Focus/center the viewport on a specific existing node. */
  onFocusNode: (nodeId: string) => void;
  /** Add a brand-new node of the given type to the canvas. */
  onAddNode: (nodeType: string) => void;
  /** Whether the /agent command should be offered in command mode. */
  showAgentCommand: boolean;
  /** Pick the /agent command — switches the overlay into agent mode. */
  onSelectAgent: () => void;
  /** Remove the /agent badge — back to search. */
  onExitAgent: () => void;
  /** Send the typed message to the AI assistant (agent mode). */
  onSendAgentMessage: (message: string) => void;
}

/** A single keyboard hint: a keycap chip + its label. */
const HintChip: React.FC<{ keyContent: React.ReactNode; label: string }> = ({
  keyContent,
  label,
}) => (
  <span className="inline-flex items-center gap-1.5 text-gray-600">
    <kbd className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-md border border-gray-200 bg-white px-1.5 text-[11px] font-medium text-gray-600 shadow-sm">
      {keyContent}
    </kbd>
    <span>{label}</span>
  </span>
);

/**
 * Command-palette style box docked at the bottom-center of the canvas. It has
 * three modes driven by the input text:
 *   - search  (default): spotlights matching nodes and lists them + add-new types
 *   - command ("/…"):     shows the /agent command and the list of nodes to add
 *   - agent   (/agent):   an /agent badge + free text sent to the AI assistant
 * Auto-focuses on mount so the user can type immediately after the shortcut.
 */
const WorkflowCommandPalette: React.FC<WorkflowCommandPaletteProps> = ({
  mode,
  query,
  onQueryChange,
  onClose,
  onSubmit,
  matchCount,
  existingResults,
  addResults,
  onFocusNode,
  onAddNode,
  showAgentCommand,
  onSelectAgent,
  onExitAgent,
  onSendAgentMessage,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus the input as soon as the overlay opens.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const trimmed = query.trim();
  const hasQuery = trimmed.length > 0;

  const isAgent = mode === "agent";
  const isCommand = mode === "command";
  const isSearch = mode === "search";

  const showResultsPanel = isCommand || (isSearch && hasQuery);
  const hasAnyResult =
    (isCommand && showAgentCommand) ||
    existingResults.length > 0 ||
    addResults.length > 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (isAgent) {
        onSendAgentMessage(query);
      } else if (isCommand) {
        if (showAgentCommand) onSelectAgent();
        else if (addResults.length > 0) onAddNode(addResults[0].type);
      } else {
        onSubmit();
      }
      return;
    }
    // Backspace on an empty agent input removes the /agent badge.
    if (e.key === "Backspace" && isAgent && query.length === 0) {
      e.preventDefault();
      onExitAgent();
    }
  };

  const placeholder = isAgent
    ? "Ask AI to update your workflow…"
    : isCommand
    ? "Type a command or search nodes…"
    : "Search nodes by name or type…";

  return (
    <div className="fixed bottom-6 inset-x-0 mx-auto z-50 w-full max-w-xl px-4 animate-in fade-in slide-in-from-bottom-4 duration-200">
      {/* Results panel — grows upward from the input */}
      {showResultsPanel && (
        <div className="mb-2 max-h-[46vh] overflow-y-auto rounded-2xl border border-gray-200 bg-white p-1.5 shadow-xl shadow-black/10">
          {/* /agent command (command mode) */}
          {isCommand && showAgentCommand && (
            <div className="mb-1">
              <div className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Command
              </div>
              <button
                type="button"
                onClick={onSelectAgent}
                className="group flex w-full items-center gap-3 rounded-lg bg-[hsl(var(--brand-50))] px-3 py-2.5 text-left transition-colors hover:bg-[hsl(var(--brand-600))]/10"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[hsl(var(--brand-600))]">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-gray-800">/agent</p>
                  <p className="truncate text-xs text-gray-500">
                    Ask AI to build or edit this workflow
                  </p>
                </div>
                <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-[hsl(var(--brand-600))]">
                  <CornerDownLeft className="h-3.5 w-3.5" /> Enter
                </span>
              </button>
            </div>
          )}

          {/* Existing matching nodes (search mode) */}
          {existingResults.length > 0 && (
            <div className="mb-1">
              <div className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                On this workflow
              </div>
              {existingResults.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onFocusNode(item.id)}
                  className="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-gray-50"
                >
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${getNodeBgColor(
                      item.category
                    )}`}
                  >
                    {renderIcon(item.icon, `h-4 w-4 ${getNodeIconColor(item.category)}`)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-800">{item.name}</p>
                    <p className="truncate text-xs text-gray-400">{item.typeLabel}</p>
                  </div>
                  <span className="flex shrink-0 items-center gap-1 text-xs text-gray-400 opacity-0 transition-opacity group-hover:opacity-100">
                    <Crosshair className="h-3.5 w-3.5" /> Focus
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Node types to add */}
          {addResults.length > 0 && (
            <div>
              <div className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Add new node
              </div>
              {addResults.map((item) => (
                <button
                  key={item.type}
                  type="button"
                  onClick={() => onAddNode(item.type)}
                  className="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-gray-50"
                >
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${getNodeBgColor(
                      item.category
                    )}`}
                  >
                    {renderIcon(item.icon, `h-4 w-4 ${getNodeIconColor(item.category)}`)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-800">{item.label}</p>
                    <p className="truncate text-xs text-gray-400">{item.description}</p>
                  </div>
                  <span className="flex shrink-0 items-center gap-1 rounded-full bg-[hsl(var(--brand-50))] px-2 py-1 text-xs font-medium text-[hsl(var(--brand-600))]">
                    <Plus className="h-3.5 w-3.5" /> Add
                  </span>
                </button>
              ))}
            </div>
          )}

          {!hasAnyResult && (
            <div className="px-3 py-6 text-center text-sm text-gray-400">
              {isCommand
                ? `No commands or nodes match “${trimmed.replace(/^\//, "")}”`
                : `No nodes match “${trimmed}”`}
            </div>
          )}
        </div>
      )}

      {/* Input + hints — one cohesive card */}
      <div className="overflow-hidden rounded-[26px] border border-[hsl(var(--brand-600))] bg-white shadow-lg transition-all focus-within:ring-2 focus-within:ring-[hsl(var(--brand-600))]/30">
      <div className="relative flex items-center">
        {/* Left indicator: /agent badge in agent mode, Search icon otherwise */}
        {isAgent ? (
          <span className="ml-2 flex shrink-0 items-center gap-1 rounded-full bg-[hsl(var(--brand-50))] py-1 pl-2 pr-1.5 text-xs font-medium text-[hsl(var(--brand-600))]">
            <Sparkles className="h-3 w-3" />
            /agent
            <button
              type="button"
              onClick={onExitAgent}
              className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full transition-colors hover:bg-[hsl(var(--brand-600))]/15"
              aria-label="Exit agent mode"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ) : (
          <Search className="absolute left-4 h-4 w-4 text-[hsl(var(--brand-600))] pointer-events-none" />
        )}

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`h-12 bg-transparent text-sm placeholder:text-gray-400 focus:outline-none ${
            isAgent ? "min-w-0 flex-1 pl-2 pr-12" : "w-full pl-10 pr-24"
          }`}
        />

        {isAgent ? (
          <button
            type="button"
            onClick={() => onSendAgentMessage(query)}
            disabled={!hasQuery}
            className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-full bg-[hsl(var(--brand-600))] text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:opacity-100"
            aria-label="Send to AI"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        ) : (
          <>
            {isSearch && hasQuery && (
              <span
                className={`absolute right-12 text-xs font-medium tabular-nums ${
                  matchCount > 0 ? "text-[hsl(var(--brand-600))]" : "text-gray-400"
                }`}
              >
                {matchCount > 0
                  ? `${matchCount} match${matchCount === 1 ? "" : "es"}`
                  : "No matches"}
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Close search</span>
            </button>
          </>
        )}
      </div>

      {/* Footer hints — folded into the same card, more visible */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5 border-t border-gray-100 bg-gray-50 px-4 py-2.5 text-xs">
        {isAgent ? (
          <>
            <HintChip keyContent={<CornerDownLeft className="h-3 w-3" />} label="send to AI" />
            <HintChip keyContent="⌫" label="exit agent" />
            <HintChip keyContent="Esc" label="close" />
          </>
        ) : isCommand ? (
          <>
            <HintChip keyContent={<CornerDownLeft className="h-3 w-3" />} label="select" />
            <HintChip keyContent="Esc" label="close" />
          </>
        ) : (
          <>
            <HintChip keyContent={<CornerDownLeft className="h-3 w-3" />} label="focus matches" />
            <HintChip keyContent="/" label="commands" />
            <HintChip keyContent="Esc" label="close" />
          </>
        )}
      </div>
      </div>
    </div>
  );
};

export default WorkflowCommandPalette;

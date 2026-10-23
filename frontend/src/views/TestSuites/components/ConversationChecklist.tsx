import React, { useMemo, useState } from "react";
import { ChevronRight, Eye } from "lucide-react";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { SearchInput } from "@/components/SearchInput";
import { cn } from "@/helpers/utils";
import type { CheckConversation, CheckTurn } from "../helpers/checks";
import { turnLabel } from "../helpers/datasetConversations";
import { DatasetConversationSheet } from "./DatasetConversationSheet";

// Past this many, a search box helps find one.
const SEARCH_FROM = 6;

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

const found = (conversation: CheckConversation, query: string): boolean =>
  !query ||
  conversation.label.toLowerCase().includes(query) ||
  conversation.turns.some(
    (turn) => turn.message.toLowerCase().includes(query) || (turn.expected ?? "").toLowerCase().includes(query),
  );

interface ConversationChecklistProps {
  conversations: CheckConversation[];
  /** "conversations" ticks any number of them; "turn" picks one turn. */
  mode: "conversations" | "turn";
  /** The conversations chosen, by key, including any the dataset lost. */
  chosen?: string[];
  onChoose?: (keys: string[]) => void;
  /** The picked turn, by case id. */
  pickedTurn?: string | null;
  onPickTurn?: (conversation: CheckConversation, turn: CheckTurn) => void;
}

/** The dataset's conversations in the form itself, ticked like knowledge bases on a query step. */
export const ConversationChecklist: React.FC<ConversationChecklistProps> = ({
  conversations,
  mode,
  chosen = [],
  onChoose,
  pickedTurn = null,
  onPickTurn,
}) => {
  const [search, setSearch] = useState("");
  const [viewing, setViewing] = useState<string | null>(null);
  // The picked turn's conversation starts open, so the pick shows.
  const [expanded, setExpanded] = useState<Set<string>>(
    () =>
      new Set(
        conversations.filter((item) => item.turns.some((turn) => turn.caseId === pickedTurn)).map((item) => item.key),
      ),
  );
  const query = search.trim().toLowerCase();
  // Folding during a search lasts for that search only, since a search opens what it found.
  const [foldedInSearch, setFoldedInSearch] = useState<{ query: string; keys: Set<string> }>({
    query: "",
    keys: new Set(),
  });
  const searchFolds = foldedInSearch.query === query ? foldedInSearch.keys : new Set<string>();
  const shown = useMemo(() => conversations.filter((item) => found(item, query)), [conversations, query]);
  const chosenSet = new Set(chosen);
  const kept = conversations.filter((item) => chosenSet.has(item.key)).map((item) => item.key);
  const lost = chosen.filter((key) => !conversations.some((item) => item.key === key));
  const viewed = conversations.find((item) => item.key === viewing) ?? null;

  // Chosen ones keep the dataset's order.
  const choose = (keys: Set<string>) =>
    onChoose?.([...conversations.map((item) => item.key).filter((key) => keys.has(key)), ...lost.filter((key) => keys.has(key))]);
  const toggle = (key: string) => {
    const next = new Set(chosen);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    choose(next);
  };
  const flip = (set: Set<string>, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };
  const toggleOpen = (key: string) => {
    if (query) setFoldedInSearch({ query, keys: flip(searchFolds, key) });
    else setExpanded((previous) => flip(previous, key));
  };
  // A turn picked in the side panel shows in the list too.
  const pickTurn = (conversation: CheckConversation, turn: CheckTurn) => {
    setExpanded((previous) => new Set(previous).add(conversation.key));
    onPickTurn?.(conversation, turn);
  };

  const linkClass =
    "font-medium text-primary hover:underline disabled:cursor-default disabled:text-muted-foreground disabled:no-underline";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="text-sm font-medium">{mode === "turn" ? "Turn" : "Conversations"}</span>
        {mode === "conversations" ? (
          <div className="flex items-center gap-3 text-xs">
            <span className="text-muted-foreground">
              {kept.length} of {plural(conversations.length, "conversation")} chosen
            </span>
            <button
              type="button"
              className={linkClass}
              disabled={shown.every((item) => chosenSet.has(item.key))}
              onClick={() => choose(new Set([...chosen, ...shown.map((item) => item.key)]))}
            >
              {query ? "Choose all found" : "Choose all"}
            </button>
            <button type="button" className={linkClass} disabled={chosen.length === 0} onClick={() => choose(new Set())}>
              Clear
            </button>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">Open a conversation and pick the turn.</span>
        )}
      </div>

      {conversations.length > SEARCH_FROM && (
        <SearchInput value={search} onChange={setSearch} placeholder="Search the messages..." className="sm:w-full" />
      )}

      <div className="max-h-72 overflow-y-auto rounded-lg border bg-background">
        {shown.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            {conversations.length === 0 ? "This dataset has no conversations yet." : "No conversation matches your search."}
          </p>
        ) : (
          <ul className="divide-y">
            {shown.map((conversation) => {
              const isChosen = chosenSet.has(conversation.key);
              // A search opens what it found, so the matching turns show.
              const open =
                mode === "turn" && (query ? !searchFolds.has(conversation.key) : expanded.has(conversation.key));
              const view = (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 text-muted-foreground"
                  aria-label={`View "${conversation.label}"`}
                  title="View the conversation"
                  onClick={() => setViewing(conversation.key)}
                >
                  <Eye className="h-4 w-4" />
                </Button>
              );
              return (
                <li key={conversation.key}>
                  {mode === "conversations" ? (
                    <div className={cn("flex items-center gap-3 px-3 py-2", isChosen && "bg-primary/5")}>
                      <Checkbox
                        id={`conversation-${conversation.key}`}
                        checked={isChosen}
                        onCheckedChange={() => toggle(conversation.key)}
                      />
                      <label htmlFor={`conversation-${conversation.key}`} className="min-w-0 flex-1 cursor-pointer">
                        <span className="block truncate text-sm">{conversation.label}</span>
                      </label>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {plural(conversation.turns.length, "turn")}
                      </span>
                      {view}
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 px-3 py-2">
                        <button
                          type="button"
                          onClick={() => toggleOpen(conversation.key)}
                          aria-expanded={open}
                          className="flex min-w-0 flex-1 items-center gap-2 text-left"
                        >
                          <ChevronRight
                            className={cn(
                              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                              open && "rotate-90",
                            )}
                          />
                          <span className="min-w-0 flex-1 truncate text-sm">{conversation.label}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {plural(conversation.turns.length, "turn")}
                          </span>
                        </button>
                        {view}
                      </div>
                      {open && (
                        <div className="space-y-1 px-3 pb-2 pl-9">
                          {conversation.turns.map((turn) => {
                            const picked = turn.caseId === pickedTurn;
                            return (
                              <button
                                key={turn.caseId}
                                type="button"
                                aria-pressed={picked}
                                onClick={() => pickTurn(conversation, turn)}
                                className={cn(
                                  "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted",
                                  picked && "bg-primary/10 ring-1 ring-primary hover:bg-primary/10",
                                )}
                              >
                                <span
                                  aria-hidden="true"
                                  className={cn(
                                    "mt-1 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border",
                                    picked ? "border-primary" : "border-muted-foreground/50",
                                  )}
                                >
                                  {picked && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
                                </span>
                                <span className="min-w-0">
                                  <span className="block text-xs font-medium text-muted-foreground">
                                    {turnLabel(turn.position)}
                                  </span>
                                  <span className="block whitespace-pre-wrap break-words text-sm">
                                    {turn.message || <span className="italic text-muted-foreground">No message</span>}
                                  </span>
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {mode === "conversations" && lost.length > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {lost.length === 1
            ? "1 chosen conversation is no longer in the dataset."
            : `${lost.length} chosen conversations are no longer in the dataset.`}{" "}
          <button
            type="button"
            className="font-medium underline-offset-2 hover:underline"
            onClick={() => choose(new Set(kept))}
          >
            Remove {lost.length === 1 ? "it" : "them"}
          </button>
        </p>
      )}

      {viewed && (
        <DatasetConversationSheet
          conversation={viewed}
          onClose={() => setViewing(null)}
          {...(mode === "conversations"
            ? {
                chosen: chosenSet.has(viewed.key),
                // Choosing or leaving it out is the decision the panel was opened for, so it closes.
                onToggleChosen: () => {
                  toggle(viewed.key);
                  setViewing(null);
                },
              }
            : { pickedTurn, onPickTurn: (turn: CheckTurn) => pickTurn(viewed, turn) })}
        />
      )}
    </div>
  );
};

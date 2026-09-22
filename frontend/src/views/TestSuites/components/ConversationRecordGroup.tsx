import React from "react";
import {
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  MessagesSquare,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/button";
import JsonViewer from "@/components/JsonViewer";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type { ConversationGroup } from "../helpers/datasetConversations";
import { answerOf, hasExpected, isPlainRecord, questionOf } from "../helpers/recordFields";

// Plain text when the engine reads the field as text, raw JSON otherwise. The
// label follows the view, since a raw object is not a question or an answer.
const RecordField: React.FC<{
  label: string;
  rawLabel: string;
  text: string | null;
  raw?: Record<string, unknown> | null;
  emptyText?: string;
}> = ({ label, rawLabel, text, raw, emptyText }) => (
  <div>
    <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {text !== null || emptyText ? label : rawLabel}
    </div>
    {text !== null ? (
      <p className="whitespace-pre-wrap break-words rounded-md border bg-background px-3 py-2 text-sm text-foreground">
        {text}
      </p>
    ) : emptyText ? (
      <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
        {emptyText}
      </p>
    ) : (
      <JsonViewer data={(raw ?? {}) as unknown as never} />
    )}
  </div>
);

// A turn renders as text only when BOTH halves round-trip through text, so the
// view matches the editor. One structured half puts the whole turn in JSON.
const RecordBody: React.FC<{ entry: TestCase }> = ({ entry }) => {
  const plain = isPlainRecord(entry.input_data, entry.expected_output);
  return (
    <div className="mt-3 space-y-3">
      <RecordField
        label="User message"
        rawLabel="Input"
        text={plain ? questionOf(entry.input_data) : null}
        raw={entry.input_data}
      />
      <RecordField
        label="Expected reply"
        rawLabel="Expected Output"
        text={plain ? answerOf(entry.expected_output) : null}
        raw={entry.expected_output}
        emptyText={
          hasExpected(entry.expected_output)
            ? undefined
            : "No expected reply. This turn scores as a failure."
        }
      />
    </div>
  );
};

interface ConversationRecordGroupProps {
  group: ConversationGroup;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  expandedRecords: Set<string>;
  onToggleRecord: (caseId: string) => void;
  onEdit: (entry: TestCase) => void;
  /** Receives the turn's displayed position so the confirm can name it. */
  onDelete: (entry: TestCase, turnNumber: number) => void;
  /** Removes every turn in this conversation, named as the user sees it. */
  onRemoveConversation?: (conversation: {
    id: string;
    label: string;
    turns: number;
  }) => void;
  /** Opens or closes every turn in this conversation at once. */
  onSetTurnsExpanded?: (expand: boolean) => void;
  /** Appends a turn to this hand-authored thread. Manual groups only. */
  onAddTurn?: () => void;
}

export const ConversationRecordGroup: React.FC<ConversationRecordGroupProps> = ({
  group,
  isCollapsed,
  onToggleCollapse,
  expandedRecords,
  onToggleRecord,
  onEdit,
  onDelete,
  onRemoveConversation,
  onSetTurnsExpanded,
  onAddTurn,
}) => {
  const isImported = group.isImported;
  const turnLabel = `${group.cases.length} turn${group.cases.length === 1 ? "" : "s"}`;
  // Named by its own id, which never changes. A position-based number would
  // shift every time a conversation above it was deleted.
  const shortId = (group.conversationId ?? group.cases[0]?.id ?? "").slice(-6);
  const name = `Conversation #${shortId}`;
  const origin = isImported
    ? "Imported from a real conversation"
    : "Written by hand";
  // Both actions can be meaningful at once when only some turns are open, so
  // each is offered separately and disabled only when it would do nothing.
  const allTurnsExpanded = group.cases.every((entry) => expandedRecords.has(entry.id ?? ""));
  const anyTurnsExpanded = group.cases.some((entry) => expandedRecords.has(entry.id ?? ""));

  return (
    <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
      <div
        className="flex cursor-pointer items-center justify-between gap-3 px-6 py-4 transition-colors hover:bg-muted"
        onClick={onToggleCollapse}
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Decorative: the whole row owns the click. */}
          <span className="shrink-0 text-muted-foreground">
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </span>
          {/* Both are conversations, so colour carries the distinction. The
              label is there for anyone who cannot use the colour. */}
          <span className="flex shrink-0" title={origin} aria-label={origin}>
            <MessagesSquare
              className={`h-4 w-4 ${isImported ? "text-blue-600" : "text-muted-foreground"}`}
            />
          </span>
          <div className="min-w-0 text-sm font-medium truncate">{name}</div>
          {/* Describes the conversation, so it sits with the title rather than
              among the buttons that act on it. */}
          {/* Carries the card's own ground, not the hover ground, so it stays
              readable when the row lights up. */}
          <span className="inline-flex shrink-0 items-center rounded-full border bg-card px-2 py-0.5 text-xs text-muted-foreground">
            {turnLabel}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {group.conversationId && onAddTurn && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label="Add a turn to this conversation"
              title="Add a turn to this conversation"
              onClick={(e) => {
                e.stopPropagation();
                onAddTurn();
              }}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          )}
          {group.conversationId && onRemoveConversation && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-red-500"
              aria-label="Remove this conversation from the dataset"
              title="Remove this conversation from the dataset"
              onClick={(e) => {
                e.stopPropagation();
                onRemoveConversation({
                  id: group.conversationId as string,
                  label: name,
                  turns: group.cases.length,
                });
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {!isCollapsed && (
        // Turns sit on a recessed ground so their cards read as contained.
        <div className="border-t bg-muted/30">
          {onSetTurnsExpanded && (
            <div className="flex justify-end gap-1 px-4 pt-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-muted-foreground"
                icon={<ChevronsUpDown className="h-3.5 w-3.5" />}
                disabled={allTurnsExpanded}
                onClick={() => onSetTurnsExpanded(true)}
              >
                Expand all
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-muted-foreground"
                icon={<ChevronsDownUp className="h-3.5 w-3.5" />}
                disabled={!anyTurnsExpanded}
                onClick={() => onSetTurnsExpanded(false)}
              >
                Collapse all
              </Button>
            </div>
          )}
          <div className="space-y-2 p-4">
            {group.cases.map((entry, index) => {
              const isExpanded = expandedRecords.has(entry.id ?? "");
              return (
                <div
                  key={entry.id}
                  id={`record-${entry.id}`}
                  className="rounded-lg border bg-card p-3 dark:bg-zinc-900"
                >
                  <div
                    className="flex cursor-pointer items-center justify-between gap-2"
                    onClick={() => entry.id && onToggleRecord(entry.id)}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      {/* Decorative: the whole row owns the click. */}
                      <span className="text-muted-foreground">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </span>
                      {/* Numbered by position, so deleting a turn renumbers the
                          rest rather than leaving a gap. The stored turn_index
                          keeps its value, since that is what rules target. */}
                      <span className="shrink-0 text-sm font-medium">
                        Turn {index + 1}
                      </span>
                    </div>
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        aria-label={`Edit turn ${index + 1}`}
                        onClick={() => onEdit(entry)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-500"
                        aria-label={`Delete turn ${index + 1}`}
                        onClick={() => onDelete(entry, index + 1)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  {isExpanded && <RecordBody entry={entry} />}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

import React from "react";
import { ChevronDown, ChevronRight, ListOrdered, MessagesSquare, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import JsonViewer from "@/components/JsonViewer";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type { ConversationGroup } from "../helpers/datasetConversations";

interface ConversationRecordGroupProps {
  group: ConversationGroup;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  expandedRecords: Set<string>;
  onToggleRecord: (caseId: string) => void;
  onEdit: (entry: TestCase) => void;
  onDelete: (entry: TestCase) => void;
}

export const ConversationRecordGroup: React.FC<ConversationRecordGroupProps> = ({
  group,
  isCollapsed,
  onToggleCollapse,
  expandedRecords,
  onToggleRecord,
  onEdit,
  onDelete,
}) => {
  const isImported = !!group.conversationId;
  const turnLabel = `${group.cases.length} turn${group.cases.length === 1 ? "" : "s"}`;

  return (
    <div className="border rounded-lg overflow-hidden">
      <div
        className={`flex items-center justify-between gap-3 px-3 py-2 cursor-pointer ${
          isImported ? "bg-blue-50/60" : "bg-gray-50"
        }`}
        onClick={onToggleCollapse}
      >
        <div className="flex items-center gap-2 min-w-0">
          <button type="button" className="text-gray-400 hover:text-gray-600 shrink-0">
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          <MessagesSquare
            className={`h-4 w-4 shrink-0 ${isImported ? "text-blue-600" : "text-gray-400"}`}
          />
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">
              {isImported
                ? `Conversation #${group.conversationId?.slice(-6)}`
                : "Independent record"}
            </div>
            <div className="text-xs text-gray-500 truncate">{group.preview}</div>
          </div>
        </div>
        <span className="inline-flex items-center text-xs rounded-full bg-white border px-2 py-0.5 shrink-0">
          {turnLabel}
        </span>
      </div>

      {!isCollapsed && (
        <div className="divide-y">
          {group.cases.map((entry, index) => {
            const isExpanded = expandedRecords.has(entry.id ?? "");
            return (
              <div key={entry.id} id={`record-${entry.id}`} className="p-3">
                <div
                  className="flex items-center justify-between gap-2 cursor-pointer"
                  onClick={() => entry.id && onToggleRecord(entry.id)}
                >
                  <div className="flex items-center gap-2 text-gray-600 min-w-0">
                    <button type="button" className="text-gray-400 hover:text-gray-600">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                    <ListOrdered className="h-3.5 w-3.5 shrink-0" />
                    {isImported && (
                      <span className="text-xs text-gray-500 shrink-0">
                        Turn {(entry.turn_index ?? index) + 1}
                      </span>
                    )}
                    <span className="text-sm font-medium shrink-0">
                      #{entry.id?.slice(-4)}
                    </span>
                  </div>
                  <div
                    className="flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => onEdit(entry)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-red-500"
                      onClick={() => onDelete(entry)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
                {isExpanded && (
                  <div className="mt-3 space-y-2">
                    <div className="text-xs text-gray-500 mb-1">Input</div>
                    <JsonViewer data={(entry.input_data ?? {}) as unknown as never} />
                    <div className="text-xs text-gray-500 mt-2 mb-1">Expected Output</div>
                    <JsonViewer data={(entry.expected_output ?? {}) as unknown as never} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

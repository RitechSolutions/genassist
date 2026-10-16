import React from "react";
import { Check, MessageCircle } from "lucide-react";
import { Button } from "@/components/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/sheet";
import { cn } from "@/helpers/utils";
import type { CheckConversation, CheckTurn } from "../helpers/checks";

interface DatasetConversationSheetProps {
  conversation: CheckConversation;
  onClose: () => void;
  /** Whether the check applies to this conversation, with a button to change that. */
  chosen?: boolean;
  onToggleChosen?: () => void;
  /** The turn the check is about, with a button on each turn to pick it. */
  pickedTurn?: string | null;
  onPickTurn?: (turn: CheckTurn) => void;
}

const BUBBLE = "max-w-[85%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm";

/** One of the dataset's conversations as a chat, opened beside the form instead of leaving it. */
export const DatasetConversationSheet: React.FC<DatasetConversationSheetProps> = ({
  conversation,
  onClose,
  chosen,
  onToggleChosen,
  pickedTurn,
  onPickTurn,
}) => {
  const turns = conversation.turns.length;
  // A missing expected reply is worth saying only where other turns have one.
  const anyExpected = conversation.turns.some((turn) => turn.expected);
  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        overlayClassName="bg-black/30"
        className="flex w-full flex-col gap-0 p-0 sm:right-2 sm:top-2 sm:h-[calc(100vh-1rem)] sm:max-w-lg sm:rounded-2xl sm:border"
      >
        <SheetHeader className="shrink-0 space-y-0 border-b px-5 py-4 pr-12 text-left">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <MessageCircle className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <SheetTitle className="truncate text-base">{conversation.label}</SheetTitle>
              <SheetDescription className="text-xs">
                {turns} turn{turns === 1 ? "" : "s"} from the dataset.
                {anyExpected && " The replies shown are the expected ones."}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-muted/20 px-4 py-4">
          {conversation.turns.map((turn) => {
            const picked = pickedTurn === turn.caseId;
            return (
              <div
                key={turn.caseId}
                className={cn("space-y-2 rounded-lg p-2", picked && "bg-primary/5 ring-1 ring-primary/40")}
              >
                <div className="flex flex-col items-start">
                  <span className="mb-1 text-[11px] font-medium text-muted-foreground">Customer</span>
                  <div className={cn(BUBBLE, "rounded-tl-none bg-muted", !turn.message && "italic text-muted-foreground")}>
                    {turn.message || "No message"}
                  </div>
                  {turn.inputs && turn.inputs.length > 0 && (
                    <div className="mt-1 flex max-w-[85%] flex-wrap gap-1">
                      {turn.inputs.map(([name, value]) => (
                        <span
                          key={name}
                          className="truncate rounded-full border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                          title={`${name}: ${value}`}
                        >
                          {name}: {value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                {turn.expected ? (
                  <div className="flex flex-col items-end">
                    <span className="mb-1 text-[11px] font-medium text-muted-foreground">Expected reply</span>
                    <div className={cn(BUBBLE, "rounded-tr-none border border-dashed border-blue-400/70 bg-background")}>
                      {turn.expected}
                    </div>
                  </div>
                ) : (
                  anyExpected && <p className="text-right text-xs italic text-muted-foreground">No expected reply</p>
                )}
                {onPickTurn && (
                  <div className="flex justify-start">
                    <Button
                      type="button"
                      size="sm"
                      variant={picked ? "secondary" : "outline"}
                      className="h-7 text-xs"
                      disabled={picked}
                      onClick={() => onPickTurn(turn)}
                    >
                      {picked ? (
                        <>
                          <Check className="mr-1 h-3.5 w-3.5" />
                          The check's turn
                        </>
                      ) : (
                        "Use this turn"
                      )}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {onToggleChosen && (
          <div className="flex shrink-0 justify-end gap-2 border-t px-5 py-3">
            <Button type="button" variant={chosen ? "outline" : "default"} onClick={onToggleChosen}>
              {chosen ? "Leave it out" : "Choose this conversation"}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

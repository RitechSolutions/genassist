import React from "react";
import { ArrowRight } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog";
import { cn } from "@/helpers/utils";
import type { RunConversationResult, RunTurnResult } from "@/interfaces/testSuite.interface";
import {
  type GradedItem,
  ofThisReply,
  type ReplyCheckPair,
  pairChange,
  pairReplyChecks,
  replyVerdict,
} from "../helpers/runConversations";
import { VerdictIcon } from "./resultsParts";

export interface ReplySide {
  run: string;
  turn?: RunTurnResult;
  conversation?: RunConversationResult;
}

// Worse is tinted red, better green, any other change amber, as on the page's tables.
const TINT = { worse: "bg-destructive/5", better: "bg-emerald-500/5", changed: "bg-amber-500/5" } as const;

/** What a check found on this reply: the fact, the grader's reason, or why it could not check. */
const finding = (item: GradedItem): string | null => {
  if (item.status === "not_evaluated") return item.note ?? null;
  if (item.graded) return item.actual ?? null;
  return item.actual ? ofThisReply(item.actual) : null;
};

const PairRow: React.FC<{ pair: ReplyCheckPair; runs: [string, string] }> = ({ pair, runs }) => {
  const change = pairChange(pair);
  const found = [pair.before, pair.after].map((item) => (item ? finding(item) : null));
  // Said once when both runs found the same, so only a difference takes two lines.
  const lines =
    found[0] === found[1] ? [{ text: found[1], run: null }] : found.map((text, i) => ({ text, run: runs[i] }));
  return (
    <div
      className={cn("grid grid-cols-[minmax(0,1fr)_4rem_4rem] items-start gap-3 px-4 py-2.5", change && TINT[change])}
    >
      <div className="min-w-0">
        <p className="text-sm">{pair.whole ? pair.title : ofThisReply(pair.title)}</p>
        {lines
          .filter((line) => line.text)
          .map((line) => (
            <p key={line.run ?? "both"} className="mt-0.5 text-xs text-muted-foreground">
              {line.run && (
                <span className="mr-1.5 rounded bg-foreground/5 px-1.5 py-px text-[11px] font-medium text-foreground/60">
                  {line.run}
                </span>
              )}
              {line.text}
            </p>
          ))}
      </div>
      {[pair.before, pair.after].map((item, i) => (
        <span key={i} className="flex justify-center pt-0.5">
          {item ? (
            <VerdictIcon verdict={item.status} filled={!pair.whole} />
          ) : (
            <span className="text-xs text-muted-foreground" title="Not on this reply in this run">
              <span aria-hidden="true">–</span>
              <span className="sr-only">Not on this reply in this run</span>
            </span>
          )}
        </span>
      ))}
    </div>
  );
};

const PairSection: React.FC<{ title: string; pairs: ReplyCheckPair[]; runs: [string, string] }> = ({
  title,
  pairs,
  runs,
}) =>
  pairs.length ? (
    <section className="overflow-hidden rounded-lg border bg-card">
      <div className="grid grid-cols-[minmax(0,1fr)_4rem_4rem] items-center gap-3 border-b px-4 py-2 text-xs font-semibold text-muted-foreground">
        <span className="uppercase tracking-wide">{title}</span>
        <span className="text-center">{runs[0]}</span>
        <span className="text-center">{runs[1]}</span>
      </div>
      <div className="divide-y">
        {pairs.map((pair) => (
          <PairRow key={pair.key} pair={pair} runs={runs} />
        ))}
      </div>
    </section>
  ) : null;

/** One reply's checks in two runs side by side, what changed first, so a row of the conversation compares in one place. */
export const TurnCompareDialog: React.FC<{ before: ReplySide; after: ReplySide; onClose: () => void }> = ({
  before,
  after,
  onClose,
}) => {
  const side = (entry: ReplySide) =>
    entry.turn && entry.conversation ? { turn: entry.turn, conversation: entry.conversation } : undefined;
  const pairs = pairReplyChecks(side(before), side(after));
  const runs: [string, string] = [before.run, after.run];
  const turn = after.turn ?? before.turn;
  const verdict = (entry: ReplySide) =>
    entry.turn && entry.conversation ? replyVerdict(entry.turn, entry.conversation) : null;
  const [was, now] = [verdict(before), verdict(after)];
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="mb-0 shrink-0 space-y-1 border-b px-6 py-4 pr-12 text-left">
          <DialogTitle className="flex items-center gap-2">
            {/* One reply's result in each run, so filled like its own checks. */}
            <span className="flex items-center gap-1">
              {was && <VerdictIcon verdict={was} className="h-5 w-5" filled />}
              <ArrowRight aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
              {now && <VerdictIcon verdict={now} className="h-5 w-5" filled />}
            </span>
            Turn {turn?.number}
            <span className="font-normal text-muted-foreground">
              · {runs[0]} → {runs[1]}
            </span>
          </DialogTitle>
          <DialogDescription className="line-clamp-2">The reply to “{turn?.message || "No message"}”</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {pairs.length ? (
            <>
              <PairSection title="This turn" pairs={pairs.filter((pair) => !pair.whole)} runs={runs} />
              <PairSection title="Whole conversation" pairs={pairs.filter((pair) => pair.whole)} runs={runs} />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Nothing checked this reply.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

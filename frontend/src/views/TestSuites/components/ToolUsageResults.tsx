import React from "react";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";
import { ToolUsageResultCard } from "./ToolUsageResultCard";

interface Props {
  // All tool-usage results for the run; the page fetches once and passes them in.
  results: TestToolRuleResult[];
}

const isTurnScope = (scope: string): boolean =>
  scope === "every_turn" || scope === "specific_turn";

// Scope-aware headline: conversations, turns, or mixed "rule checks".
const summaryLine = (results: TestToolRuleResult[]): { headline: string; subline: string | null } => {
  const passed = results.filter((r) => r.status === "passed").length;
  const failed = results.filter((r) => r.status === "failed").length;
  const evaluated = passed + failed;
  const rate = evaluated ? Math.round((passed / evaluated) * 100) : 0;

  const conversationCount = results.filter((r) => r.scope === "conversation").length;
  const turnCount = results.filter((r) => isTurnScope(r.scope)).length;
  const onlyConversations = conversationCount > 0 && turnCount === 0;
  const onlyTurns = turnCount > 0 && conversationCount === 0;

  const unit = onlyConversations ? "conversations" : onlyTurns ? "turns" : "rule checks";
  const headline = `${passed} of ${evaluated || results.length} ${unit} passed · ${rate}% pass rate`;
  const subline =
    !onlyConversations && !onlyTurns && (conversationCount || turnCount)
      ? `${conversationCount} conversation check${conversationCount === 1 ? "" : "s"} · ${turnCount} turn check${turnCount === 1 ? "" : "s"}`
      : null;
  return { headline, subline };
};

export const ToolUsageResults: React.FC<Props> = ({ results }) => {
  if (results.length === 0) return null;

  const conversationResults = results.filter((r) => r.scope === "conversation");
  const notEvaluated = results.filter((r) => r.status === "not_evaluated").length;
  const { headline, subline } = summaryLine(results);

  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Tool Usage</h3>
          {notEvaluated > 0 && (
            <span className="text-xs text-muted-foreground">{notEvaluated} not evaluated</span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{headline}</p>
        {subline && <p className="text-[11px] text-muted-foreground">{subline}</p>}
      </header>

      <div className="space-y-2 p-3">
        {conversationResults.length > 0 ? (
          conversationResults.map((result) => (
            <ToolUsageResultCard key={result.id} result={result} />
          ))
        ) : (
          <p className="text-xs text-muted-foreground">
            Turn-level tool checks appear with each test case below.
          </p>
        )}
      </div>
    </section>
  );
};

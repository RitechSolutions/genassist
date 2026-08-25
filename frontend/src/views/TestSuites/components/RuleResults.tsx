import React from "react";
import type {
  RuleTechnique,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";
import { methodLabel } from "../helpers/methodLabels";
import { groupByTechnique, ruleCheckSummary } from "../helpers/runResults";
import { RuleResultCard } from "./RuleResultCard";

interface SectionProps {
  technique: RuleTechnique;
  results: TestToolRuleResult[];
}

const RuleTechniqueSection: React.FC<SectionProps> = ({ technique, results }) => {
  const conversationResults = results.filter((r) => r.scope === "conversation");
  const notEvaluated = results.filter((r) => r.status === "not_evaluated").length;
  const { headline, subline } = ruleCheckSummary(results);

  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{methodLabel(technique)}</h3>
          {notEvaluated > 0 && (
            <span className="text-xs text-muted-foreground">{notEvaluated} not evaluated</span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{headline}</p>
        <p className="text-[11px] text-muted-foreground">{subline}</p>
      </header>

      {conversationResults.length > 0 && (
        <div className="space-y-2 p-3">
          {conversationResults.map((result) => (
            <RuleResultCard key={result.id} result={result} />
          ))}
        </div>
      )}
    </section>
  );
};

interface Props {
  // All rule results for the run; the page fetches once and passes them in.
  results: TestToolRuleResult[];
}

export const RuleResults: React.FC<Props> = ({ results }) => {
  if (results.length === 0) return null;

  // Said once for the whole group rather than inside every section that happens
  // to have no conversation-level card to show.
  const hasTurnChecks = results.some((result) => result.scope !== "conversation");

  return (
    <div className="space-y-2">
      {groupByTechnique(results).map(([technique, techniqueResults]) => (
        <RuleTechniqueSection
          key={technique}
          technique={technique}
          results={techniqueResults}
        />
      ))}
      {hasTurnChecks && (
        <p className="px-1 text-[11px] text-muted-foreground">
          Turn-level checks are shown with each test case below.
        </p>
      )}
    </div>
  );
};

import React from "react";
import type {
  RuleTechnique,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";
import { methodLabel } from "../helpers/methodLabels";
import {
  checkResultsSummary,
  groupByTechnique,
  isConversationScope,
  ruleCheckSummary,
} from "../helpers/runResults";
import type { ConversationIndex } from "../helpers/datasetConversations";
import { RuleResultCard } from "./RuleResultCard";

interface SectionProps {
  technique: RuleTechnique;
  results: TestToolRuleResult[];
  labels?: ConversationIndex;
  checksVerdict?: string | null;
}

const RuleTechniqueSection: React.FC<SectionProps> = ({ technique, results, labels, checksVerdict }) => {
  // A check whose turn is gone has no turn to sit on, so it shows here.
  const conversationResults = results.filter(
    (r) => isConversationScope(r.scope) || (technique === "checks" && !r.case_id),
  );
  const notEvaluated = results.filter((r) => r.status === "not_evaluated").length;
  const { headline, subline } =
    technique === "checks" ? checkResultsSummary(results, checksVerdict ?? null) : ruleCheckSummary(results);

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
            <RuleResultCard key={result.id} result={result} labels={labels} />
          ))}
        </div>
      )}
    </section>
  );
};

interface Props {
  // All rule results for the run; the page fetches once and passes them in.
  results: TestToolRuleResult[];
  labels?: ConversationIndex;
  /** The run's verdict by conversation, which heads its checks. */
  checksVerdict?: string | null;
}

export const RuleResults: React.FC<Props> = ({ results, labels, checksVerdict }) => {
  if (results.length === 0) return null;

  // Said once for the whole group rather than inside every section that happens
  // to have no conversation-level card to show.
  const hasTurnChecks = results.some((result) => !isConversationScope(result.scope));

  return (
    <div className="space-y-2">
      {groupByTechnique(results).map(([technique, techniqueResults]) => (
        <RuleTechniqueSection
          key={technique}
          technique={technique}
          results={techniqueResults}
          labels={labels}
          checksVerdict={checksVerdict}
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

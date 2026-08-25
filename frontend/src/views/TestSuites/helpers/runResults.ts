import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type {
  RuleTechnique,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";

// Order rule sections the way the wizard lists the techniques.
const TECHNIQUE_ORDER: RuleTechnique[] = ["tool_used", "route_taken", "action_taken"];

// Rule-based techniques count rule checks (a rule per scope unit), not test cases.
export const isRuleTechnique = (technique: string): boolean =>
  TECHNIQUE_ORDER.includes(technique as RuleTechnique);

// Rule results arrive for every technique at once; each is displayed on its own.
export const groupByTechnique = (
  results: TestToolRuleResult[],
): [RuleTechnique, TestToolRuleResult[]][] => {
  const byTechnique = new Map<RuleTechnique, TestToolRuleResult[]>();
  for (const result of results) {
    const technique = result.technique ?? "tool_used";
    byTechnique.set(technique, [...(byTechnique.get(technique) ?? []), result]);
  }
  return TECHNIQUE_ORDER.filter((technique) => byTechnique.has(technique)).map(
    (technique) => [technique, byTechnique.get(technique) as TestToolRuleResult[]],
  );
};

// A turn-scoped result belongs to one case, so it is shown with that case; a
// conversation-scoped one has no single case to sit on.
export const isTurnScope = (scope: string): boolean =>
  scope === "every_turn" || scope === "specific_turn";

const countLabel = (count: number, noun: string): string =>
  `${count} ${noun}${count === 1 ? "" : "s"}`;

// A rule is graded once per scope unit, so the check count is rules x turns (plus
// one per conversation for a conversation-scoped rule) — never the turn count. The
// subline spells that out, so a number like "24 checks" over 12 turns is traceable.
export const ruleCheckSummary = (
  results: TestToolRuleResult[],
): { headline: string; subline: string } => {
  const passed = results.filter((result) => result.status === "passed").length;
  const failed = results.filter((result) => result.status === "failed").length;
  const evaluated = passed + failed;
  const rate = evaluated ? Math.round((passed / evaluated) * 100) : 0;

  const ruleCount = new Set(results.map((result) => result.rule_id)).size;
  const turnChecks = results.filter((result) => isTurnScope(result.scope)).length;
  const conversationChecks = results.filter((result) => result.scope === "conversation").length;

  const parts = [countLabel(ruleCount, "rule")];
  if (turnChecks) parts.push(countLabel(turnChecks, "turn check"));
  if (conversationChecks) parts.push(countLabel(conversationChecks, "conversation check"));

  return {
    headline: `${passed} of ${evaluated || results.length} checks passed · ${rate}% pass rate`,
    subline: parts.join(" · "),
  };
};

export type CaseStatus = "passed" | "failed" | "not_scored";

export const hasMetrics = (result: TestResult): boolean =>
  !!result.metrics && Object.keys(result.metrics).length > 0;

// No metrics means no score, whatever the stored status claims.
export const isResultNotScored = (result: TestResult): boolean =>
  !hasMetrics(result) || (!!result.status && result.status !== "scored");

export const isResultPassed = (result: TestResult): boolean =>
  hasMetrics(result) &&
  !isResultNotScored(result) &&
  Object.values(result.metrics!).every((m) => m.passed);

export const isResultFailed = (result: TestResult): boolean =>
  !isResultPassed(result) && !isResultNotScored(result);

export const notScoredLabel = (result: TestResult): string => {
  if (result.status === "skipped") return "Skipped";
  if (result.status === "scoring_failed") return "Scoring failed";
  if (result.status === "execution_failed") return "Execution failed";
  return "Not scored";
};

// A case's status reflects its turn-level rule results too (tool usage, route,
// action): a failed rule fails the case, and a passed rule can score an
// otherwise-unscored case.
export const caseStatusFor = (
  result: TestResult,
  ruleResults: TestToolRuleResult[],
): CaseStatus => {
  const ruleFailed = ruleResults.some((rule) => rule.status === "failed");
  const rulePassed = ruleResults.some((rule) => rule.status === "passed");
  if (ruleFailed) return "failed";
  const passed = isResultPassed(result) || (isResultNotScored(result) && rulePassed);
  if (passed) return "passed";
  if (isResultFailed(result)) return "failed";
  return "not_scored";
};

export const runAvgAccuracy = (run: TestRun): number | null => {
  const summaryMetrics = run.summary_metrics as
    | Record<string, { accuracy?: number }>
    | undefined;
  const scored = Object.values(summaryMetrics ?? {}).filter(
    (m) => typeof m.accuracy === "number",
  );
  if (!scored.length) return null;
  return scored.reduce((sum, m, _, arr) => sum + (m.accuracy ?? 0) / arr.length, 0);
};

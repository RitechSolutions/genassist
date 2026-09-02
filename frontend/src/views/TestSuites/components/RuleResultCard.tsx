import React from "react";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import { Badge } from "@/components/badge";
import type {
  RuleTechnique,
  TestToolRuleResult,
  ToolRuleResultDetails,
} from "@/interfaces/testEvaluation.interface";
import { cn } from "@/helpers/utils";
import { times, toolActualText, toolExpectedText } from "../helpers/toolRuleText";

const STATUS_META = {
  passed: { icon: CheckCircle2, className: "text-emerald-600", border: "border-l-emerald-500", label: "Passed" },
  failed: { icon: XCircle, className: "text-destructive", border: "border-l-destructive", label: "Failed" },
  not_evaluated: { icon: MinusCircle, className: "text-muted-foreground", border: "border-l-muted", label: "Not evaluated" },
} as const;

const scopeLabel = (scope: string): string =>
  scope === "conversation"
    ? "Whole conversation"
    : scope === "specific_turn"
      ? "Specific turn"
      : "Every turn";

const targetLine = (details: ToolRuleResultDetails): string | null => {
  const target = details.target;
  if (!target) return null;
  if (target.type === "conversation" && target.turn_count) {
    return `${target.label} · ${times(target.turn_count).replace("time", "turn")}`;
  }
  return target.label;
};

// Route and action results already carry a plain expected/observed pair; tool
// results are described from their observed/missing/forbidden tool lists.
const expectedText = (technique: RuleTechnique, details: ToolRuleResultDetails): string =>
  technique === "tool_used" ? toolExpectedText(details) : details.expected ?? "";

const actualText = (
  technique: RuleTechnique,
  details: ToolRuleResultDetails,
  status: string,
): string => {
  if (technique === "tool_used") return toolActualText(details, status);
  return details.comment ?? details.observed ?? "";
};

interface Props {
  result: TestToolRuleResult;
}

export const RuleResultCard: React.FC<Props> = ({ result }) => {
  const details = (result.details ?? {}) as ToolRuleResultDetails;
  const technique = result.technique ?? "tool_used";
  const meta = STATUS_META[result.status] ?? STATUS_META.not_evaluated;
  const Icon = meta.icon;
  const target = targetLine(details);

  return (
    <div className={cn("rounded-lg border border-l-2 bg-card p-3 space-y-2", meta.border)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className={cn("h-4 w-4 shrink-0", meta.className)} />
          <span className={cn("text-sm font-medium", meta.className)}>{meta.label}</span>
          {details.rule_number != null && (
            <Badge variant="secondary" className="text-[10px]">Rule {details.rule_number}</Badge>
          )}
        </div>
        <Badge variant="outline" className="text-[10px]">{scopeLabel(result.scope)}</Badge>
      </div>

      {target && <p className="text-xs text-muted-foreground">{target}</p>}

      {details.rule_summary && (
        <p className="text-sm text-foreground">{details.rule_summary}</p>
      )}

      {result.status !== "not_evaluated" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Expected</div>
            <p className="text-xs text-foreground">{expectedText(technique, details)}</p>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Actual</div>
            <p className={cn("text-xs", result.status === "passed" ? "text-foreground" : "text-destructive")}>
              {actualText(technique, details, result.status)}
            </p>
          </div>
        </div>
      )}

      {result.status === "not_evaluated" && details.comment && (
        <p className="text-xs text-muted-foreground">{details.comment}</p>
      )}
    </div>
  );
};

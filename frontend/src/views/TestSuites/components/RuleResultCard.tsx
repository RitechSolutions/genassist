import React from "react";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import { Badge } from "@/components/badge";
import type { TestToolRuleResult, ToolRuleResultDetails } from "@/interfaces/testEvaluation.interface";
import { cn } from "@/helpers/utils";
import { times } from "../helpers/toolRuleText";
import { ruleActualText, ruleExpectedText } from "../helpers/runConversations";
import { ruleTargetLabel, type ConversationIndex } from "../helpers/datasetConversations";

const STATUS_META = {
  passed: { icon: CheckCircle2, className: "text-emerald-600", border: "border-l-emerald-500", label: "Passed" },
  failed: { icon: XCircle, className: "text-destructive", border: "border-l-destructive", label: "Failed" },
  not_evaluated: { icon: MinusCircle, className: "text-muted-foreground", border: "border-l-muted", label: "Not evaluated" },
} as const;

const SCOPE_LABELS: Record<string, string> = {
  conversation: "Whole conversation",
  every_conversation: "Every conversation",
  specific_turn: "Specific turn",
  turn: "One turn",
};

const scopeLabel = (scope: string): string => SCOPE_LABELS[scope] ?? "Every turn";

const targetLine = (details: ToolRuleResultDetails): string | null => {
  const target = details.target;
  if (!target) return null;
  if (target.type === "conversation" && target.turn_count) {
    return `${target.label} · ${times(target.turn_count).replace("time", "turn")}`;
  }
  return target.label;
};

interface Props {
  result: TestToolRuleResult;
  /** The dataset's names for turns and conversations, preferred over the stored label. */
  labels?: ConversationIndex;
}

export const RuleResultCard: React.FC<Props> = ({ result, labels }) => {
  const details = (result.details ?? {}) as ToolRuleResultDetails;
  const meta = STATUS_META[result.status] ?? STATUS_META.not_evaluated;
  const Icon = meta.icon;
  const target = (labels && ruleTargetLabel(result, labels)) ?? targetLine(details);

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
            <p className="text-xs text-foreground">{ruleExpectedText(result)}</p>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Actual</div>
            <p className={cn("text-xs", result.status === "passed" ? "text-foreground" : "text-destructive")}>
              {ruleActualText(result)}
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

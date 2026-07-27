import React from "react";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import { Badge } from "@/components/badge";
import type {
  TestToolRuleResult,
  ToolRuleResultDetails,
} from "@/interfaces/testEvaluation.interface";
import { cn } from "@/helpers/utils";

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

const toolName = (details: ToolRuleResultDetails, id: string): string =>
  details.tools?.[id]?.label ?? id;

const listPhrase = (names: string[], conjunction: "and" | "or"): string => {
  if (names.length === 0) return "a tool";
  const quoted = names.map((name) => `"${name}"`);
  if (quoted.length === 1) return quoted[0];
  return `${quoted.slice(0, -1).join(", ")} ${conjunction} ${quoted[quoted.length - 1]}`;
};

const times = (n: number): string => `${n} time${n === 1 ? "" : "s"}`;

// One-line "what the rule requires", derived from the stored rule snapshot.
const expectedText = (details: ToolRuleResultDetails): string => {
  const rule = details.rule ?? {};
  const operator = rule.operator ?? details.operator ?? "all";
  const ids = rule.tool_ids ?? Object.keys(details.tools ?? {});
  const names = ids.map((id) => toolName(details, id));

  if (operator === "none") return `Do not use ${listPhrase(names, "or")}.`;
  if (operator === "only") {
    return names.length ? `Use only ${listPhrase(names, "or")}.` : "Do not use any tools.";
  }

  const conjunction = operator === "all" ? "and" : "or";
  const successfully = rule.require_success ? " successfully" : "";
  const { min_calls: min, max_calls: max } = rule;
  let count = "at least once";
  if (min != null && max != null) count = `between ${min} and ${max} times`;
  else if (min != null) count = `at least ${times(min)}`;
  else if (max != null) count = `at most ${times(max)}`;
  return `Use ${listPhrase(names, conjunction)}${successfully} ${count}.`;
};

// One-line "what actually happened", from observed/missing/failed tools + counts.
const actualText = (details: ToolRuleResultDetails, status: string): string => {
  if (status === "not_evaluated") {
    return details.comment ?? "This rule could not be checked.";
  }
  const counts = details.call_counts ?? {};
  const successful = details.successful_call_counts ?? {};
  const parts: string[] = [];

  for (const id of details.observed_tools ?? []) {
    const total = counts[id] ?? 0;
    const succeeded = successful[id] ?? 0;
    // Only say "successfully" when the calls actually succeeded (a rule without
    // require_success is satisfied even by a failed call).
    if (succeeded > 0 && succeeded === total) {
      parts.push(`Used "${toolName(details, id)}" successfully ${times(total)}`);
    } else {
      parts.push(`Called "${toolName(details, id)}" ${times(total)}; ${succeeded} succeeded`);
    }
  }
  for (const id of details.failed_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was called ${times(counts[id] ?? 0)}, but did not succeed`);
  }
  for (const id of details.missing_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was not called`);
  }
  for (const id of details.forbidden_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was used ${times(counts[id] ?? 0)} (not allowed)`);
  }
  for (const [id, reason] of Object.entries(details.check_failures ?? {})) {
    parts.push(`"${toolName(details, id)}": ${reason}`);
  }

  if (parts.length === 0) {
    return details.comment ?? (status === "passed" ? "Expectation met." : "");
  }
  return `${parts.join(". ")}.`;
};

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
}

export const ToolUsageResultCard: React.FC<Props> = ({ result }) => {
  const details = (result.details ?? {}) as ToolRuleResultDetails;
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
            <p className="text-xs text-foreground">{expectedText(details)}</p>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Actual</div>
            <p className={cn("text-xs", result.status === "passed" ? "text-foreground" : "text-destructive")}>
              {actualText(details, result.status)}
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

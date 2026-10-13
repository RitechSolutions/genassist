import React from "react";
import { AlertTriangle, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";
import type { EvaluationToolCatalog, ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import {
  type CheckConversation,
  checkProblem,
  checkSentence,
  findCheckTurn,
} from "../helpers/checks";
import { turnLabel } from "../helpers/datasetConversations";
import { CheckForm } from "./CheckForm";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";

interface ChecksListProps {
  checks: ScenarioCheck[];
  conversations: CheckConversation[];
  /** False while the dataset's turns load, so no check reads as left behind. */
  conversationsReady?: boolean;
  /** Flags tools, steps and routers the workflow no longer has once it is loaded. */
  catalog?: EvaluationCatalog | null;
  /** Read only when left out. */
  onChange?: (checks: ScenarioCheck[]) => void;
  editingId?: string | null;
  onEdit?: (id: string | null) => void;
  /** The open form's own problem, such as two values with one name. */
  onFormProblem?: (problem: string | null) => void;
}

interface Group {
  key: string;
  title: string;
  checks: { check: ScenarioCheck; turn?: string }[];
}

const toToolCatalog = (catalog: EvaluationCatalog): EvaluationToolCatalog => ({
  workflow_id: "",
  agents: catalog.agents,
  routers: catalog.routers,
  action_nodes: catalog.actionNodes,
});

/** Every conversation first, then each conversation in dataset order, then what the dataset lost. */
const groupChecks = (checks: ScenarioCheck[], conversations: CheckConversation[], ready: boolean): Group[] => {
  const every: Group = { key: "every", title: "Every conversation", checks: [] };
  const byConversation = new Map<string, Group>(
    conversations.map((item) => [item.key, { key: item.key, title: item.label, checks: [] }]),
  );
  const loading: Group = { key: "loading", title: "Loading the dataset's conversations…", checks: [] };
  const removed: Group = { key: "removed", title: "No longer in the dataset", checks: [] };
  for (const check of checks) {
    if (check.level === "every_conversation") {
      every.checks.push({ check });
    } else if (!ready) {
      loading.checks.push({ check });
    } else if (check.level === "conversation") {
      (byConversation.get(check.conversation_id ?? "") ?? removed).checks.push({ check });
    } else {
      const found = findCheckTurn(check, conversations);
      if ("problem" in found) removed.checks.push({ check });
      else byConversation.get(found.conversation.key)?.checks.push({ check, turn: turnLabel(found.turn.position) });
    }
  }
  return [every, ...byConversation.values(), loading, removed].filter((group) => group.checks.length > 0);
};

export const ChecksList: React.FC<ChecksListProps> = ({
  checks,
  conversations,
  conversationsReady = true,
  catalog,
  onChange,
  editingId,
  onEdit,
  onFormProblem,
}) => {
  const toolCatalog = catalog?.ready ? toToolCatalog(catalog) : null;
  const replace = (next: ScenarioCheck) => onChange?.(checks.map((check) => (check.id === next.id ? next : check)));
  const remove = (id: string) => {
    onChange?.(checks.filter((check) => check.id !== id));
    if (editingId === id) onEdit?.(null);
  };

  return (
    <div className="space-y-4">
      {groupChecks(checks, conversations, conversationsReady).map((group) => (
        <div key={group.key} className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</div>
          {group.checks.map(({ check, turn }) =>
            onChange && catalog && editingId === check.id ? (
              <CheckForm
                key={check.id}
                check={check}
                onChange={replace}
                onDone={() => onEdit?.(null)}
                onRemove={() => remove(check.id)}
                conversations={conversations}
                catalog={catalog}
                onProblem={onFormProblem}
              />
            ) : (
              <CheckRow
                key={check.id}
                check={check}
                turn={turn}
                problem={
                  conversationsReady || check.level === "every_conversation"
                    ? checkProblem(check, conversations, toolCatalog)
                    : null
                }
                onEdit={onChange ? () => onEdit?.(check.id) : undefined}
                onRemove={onChange ? () => remove(check.id) : undefined}
              />
            ),
          )}
        </div>
      ))}
    </div>
  );
};

const CheckRow: React.FC<{
  check: ScenarioCheck;
  turn?: string;
  problem: string | null;
  onEdit?: () => void;
  onRemove?: () => void;
}> = ({ check, turn, problem, onEdit, onRemove }) => (
  <div className="flex items-start gap-3 rounded-lg border bg-background px-3 py-2.5">
    <span
      className={cn(
        "mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        check.expect === "should"
          ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
          : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
      )}
    >
      {check.expect === "should" ? "Should" : "Should not"}
    </span>
    <div className="min-w-0 flex-1">
      <p className="text-sm">
        {turn && <span className="mr-1.5 font-medium text-muted-foreground">{turn}:</span>}
        {checkSentence(check)}
      </p>
      {problem && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {problem} It will not be graded until you fix it.
        </p>
      )}
    </div>
    {onEdit && (
      <div className="flex shrink-0 gap-1">
        <Button type="button" variant="ghost" size="icon" className="h-8 w-8" aria-label="Edit check" onClick={onEdit}>
          <Pencil className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" className="h-8 w-8" aria-label="Remove check" onClick={onRemove}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    )}
  </div>
);

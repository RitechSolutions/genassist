import React, { useState } from "react";
import { AlertTriangle, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";
import type { EvaluationToolCatalog, ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import {
  CHECK_LEVELS,
  type CheckConversation,
  checkMissing,
  checkProblem,
  checkSentence,
  chosenConversations,
  findCheckTurn,
  goneNote,
  isPlaced,
} from "../helpers/checks";
import { turnLabel } from "../helpers/datasetConversations";
import { CheckForm } from "./CheckForm";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";

interface ChecksListProps {
  checks: ScenarioCheck[];
  conversations: CheckConversation[];
  /** False while the dataset's turns load, so no check reads as left behind. */
  conversationsReady?: boolean;
  /** The dataset's turns could not be loaded. */
  conversationsFailed?: boolean;
  /** Flags tools, steps and routers the workflow no longer has once it is loaded. */
  catalog?: EvaluationCatalog | null;
  /** Read only when left out. */
  onChange?: (checks: ScenarioCheck[]) => void;
  editingId?: string | null;
  /** The check just added, listed last while its form is open. */
  newId?: string | null;
  onEdit?: (id: string | null) => void;
  /** The open form's own problem, such as two values with one name. */
  onFormProblem?: (problem: string | null) => void;
  /** Bumped to bring the open form into view again. */
  reveal?: number;
  /** The AI graders a check can pick from. */
  providers?: LLMProviderMinimal[];
}

interface Group {
  key: string;
  title: string;
  /** Each check, with the turn or the conversations it names in its row. */
  checks: { check: ScenarioCheck; place?: Place }[];
}

interface Place {
  /** One badge each. */
  names: string[];
  /** Conversations past the badges, counted beside them. */
  rest: number;
  /** Every name, for when the badges are cut short. */
  full: string;
}

const toToolCatalog = (catalog: EvaluationCatalog): EvaluationToolCatalog => ({
  workflow_id: "",
  agents: catalog.agents,
  routers: catalog.routers,
  action_nodes: catalog.actionNodes,
});

// Conversations given a badge before the rest are counted.
const TAG_NAMES = 2;

/** The group a check is listed in, and the turn or conversations its row names. */
const placementOf = (
  check: ScenarioCheck,
  conversations: CheckConversation[],
  ready: boolean,
): { group: string; place?: Place } => {
  if (check.level === "every_conversation") return { group: "every_conversation" };
  if (!isPlaced(check)) return { group: "unplaced" };
  if (!ready) return { group: "loading" };
  if (check.level === "conversation") {
    // Lost conversations are left to the row's note.
    const labels = chosenConversations(check).flatMap((key) => conversations.find((item) => item.key === key)?.label ?? []);
    if (!labels.length) return { group: "removed" };
    const place = { names: labels.slice(0, TAG_NAMES), rest: Math.max(labels.length - TAG_NAMES, 0), full: labels.join(", ") };
    return { group: "conversation", place };
  }
  const found = findCheckTurn(check, conversations);
  if ("problem" in found) return { group: "removed" };
  const label = `${found.conversation.label} · ${turnLabel(found.turn.position)}`;
  return { group: "turn", place: { names: [label], rest: 0, full: label } };
};

/** Grouped by how far each check reaches, then what the dataset lost, then a check just added; the edited check keeps its group. */
const groupChecks = (
  checks: ScenarioCheck[],
  conversations: CheckConversation[],
  ready: boolean,
  pinned: { id: string | null; group: string | null },
): Group[] => {
  const groups = new Map<string, Group>([
    // Headed as the form's picker names each reach.
    ...CHECK_LEVELS.map(({ value, label }): [string, Group] => [value, { key: value, title: label, checks: [] }]),
    ["unplaced", { key: "unplaced", title: "Not placed yet", checks: [] }],
    ["loading", { key: "loading", title: "Loading the dataset's conversations…", checks: [] }],
    ["removed", { key: "removed", title: "No longer in the dataset", checks: [] }],
    // No heading: its form stands on its own above Add check.
    ["new", { key: "new", title: "", checks: [] }],
  ]);
  let moved: string | null = null;
  for (const check of checks) {
    const { group, place } = placementOf(check, conversations, ready);
    const kept = check.id === pinned.id && pinned.group && groups.has(pinned.group) ? pinned.group : group;
    if (kept !== group) moved = group;
    groups.get(kept)?.checks.push({ check, place });
  }
  // A form alone where it began is headed by where its check now applies.
  const held = pinned.group ? groups.get(pinned.group) : undefined;
  if (moved && held?.checks.length === 1 && pinned.group !== "new") held.title = groups.get(moved)?.title ?? held.title;
  return [...groups.values()].filter((group) => group.checks.length > 0);
};

export const ChecksList: React.FC<ChecksListProps> = ({
  checks,
  conversations,
  conversationsReady = true,
  conversationsFailed = false,
  catalog,
  onChange,
  editingId,
  newId,
  onEdit,
  onFormProblem,
  providers = [],
  reveal = 0,
}) => {
  const toolCatalog = catalog?.ready ? toToolCatalog(catalog) : null;
  // Where the check being edited was listed when editing began.
  const [pinned, setPinned] = useState<{ id: string | null; group: string | null }>({ id: null, group: null });
  const editing = editingId ?? null;
  if (pinned.id !== editing) {
    const check = editing ? checks.find((item) => item.id === editing) : undefined;
    const group = !check ? null : editing === newId ? "new" : placementOf(check, conversations, conversationsReady).group;
    setPinned({ id: editing, group });
  }
  const replace = (next: ScenarioCheck) => onChange?.(checks.map((check) => (check.id === next.id ? next : check)));
  const remove = (id: string) => {
    onChange?.(checks.filter((check) => check.id !== id));
    if (editingId === id) onEdit?.(null);
  };

  return (
    <div className="space-y-4">
      {groupChecks(checks, conversations, conversationsReady, pinned).map((group) => (
        <div key={group.key} className="space-y-2">
          {group.title && (
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</div>
          )}
          {group.checks.map(({ check, place }) =>
            onChange && catalog && editingId === check.id ? (
              <CheckForm
                key={check.id}
                check={check}
                onChange={replace}
                onDone={() => onEdit?.(null)}
                onRemove={() => remove(check.id)}
                conversations={conversations}
                conversationsReady={conversationsReady}
                conversationsFailed={conversationsFailed}
                reveal={reveal}
                catalog={catalog}
                onProblem={onFormProblem}
                providers={providers}
              />
            ) : (
              <CheckRow
                key={check.id}
                check={check}
                place={place}
                problem={
                  conversationsReady || check.level === "every_conversation"
                    ? checkProblem(check, conversations, toolCatalog)
                    : null
                }
                note={conversationsReady ? goneNote(check, conversations) : null}
                missing={onChange ? checkMissing(check) : null}
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
  /** The turn, or the conversations, the row names. */
  place?: Place;
  problem: string | null;
  /** Something to know that does not stop the check, such as a chosen conversation the dataset lost. */
  note?: string | null;
  /** What it still needs before the evaluation can be saved. */
  missing?: string | null;
  onEdit?: () => void;
  onRemove?: () => void;
}> = ({ check, place, problem, note, missing, onEdit, onRemove }) => (
  <div className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2.5">
    <span
      className={cn(
        "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        check.expect === "should"
          ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
          : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
      )}
    >
      {check.expect === "should" ? "Should" : "Should not"}
    </span>
    <div className="min-w-0 flex-1">
      <p className="text-sm">{checkSentence(check)}</p>
      {place && (
        <div title={place.full} className="mt-1.5 flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
          {place.names.map((name, index) => (
            <span key={index} className="min-w-0 truncate rounded-md bg-muted px-1.5 py-0.5">
              {name}
            </span>
          ))}
          {place.rest > 0 && <span className="shrink-0">+{place.rest}</span>}
        </div>
      )}
      {missing && <p className="mt-1 text-xs text-destructive">Not complete: {missing}</p>}
      {(problem || note) && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {problem ?? note}
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

import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/command";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";
import { Check, ChevronDown, ChevronRight, Plus, Trash2, X } from "lucide-react";
import { cn } from "@/helpers/utils";
import type {
  EvaluationAgentInfo,
  RuleConversation,
  RuleScopeTarget,
  ToolUsageOperator,
  ToolUsageRule,
} from "@/interfaces/testEvaluation.interface";
import { RuleScopeFields } from "./RuleScopeFields";
import { scopePhrase } from "../helpers/ruleScope";

export type { RuleConversation };

const ANY_AGENT = "__any__";

type Expectation = "must_use" | "must_not_use" | "only";
type MatchMode = "all" | "any";

const EXPECTATION_OPTIONS: { value: Expectation; label: string }[] = [
  { value: "must_use", label: "Must use" },
  { value: "must_not_use", label: "Must not use" },
  { value: "only", label: "May use only" },
];

const MATCH_OPTIONS: { value: MatchMode; label: string }[] = [
  { value: "all", label: "All selected tools" },
  { value: "any", label: "At least one" },
];

const operatorToExpectation = (operator: ToolUsageOperator): Expectation =>
  operator === "none" ? "must_not_use" : operator === "only" ? "only" : "must_use";

const operatorToMatch = (operator: ToolUsageOperator): MatchMode =>
  operator === "any" ? "any" : "all";

const toOperator = (expectation: Expectation, match: MatchMode): ToolUsageOperator => {
  if (expectation === "must_not_use") return "none";
  if (expectation === "only") return "only";
  return match;
};

export const newToolRule = (): ToolUsageRule => ({
  id:
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `rule-${Math.random().toString(36).slice(2)}`,
  agent_id: null,
  tool_ids: [],
  operator: "all",
  require_success: false,
  scope: "every_turn",
});

const joinPhrases = (items: string[], conjunction: "and" | "or"): string => {
  if (items.length === 0) return "a tool";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} ${conjunction} ${items[items.length - 1]}`;
};

const toNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

// ---- one rule card ---------------------------------------------------------

interface RuleCardProps {
  rule: ToolUsageRule;
  index: number;
  catalog: EvaluationAgentInfo[];
  conversations: RuleConversation[];
  onChange: (patch: Partial<ToolUsageRule>) => void;
  onRemove: () => void;
}

const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  index,
  catalog,
  conversations,
  onChange,
  onRemove,
}) => {
  const [toolsOpen, setToolsOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const toolsRef = useRef<HTMLDivElement>(null);

  // Close the tools dropdown when clicking outside it.
  useEffect(() => {
    if (!toolsOpen) return;
    const handleClick = (event: MouseEvent) => {
      if (toolsRef.current && !toolsRef.current.contains(event.target as Node)) {
        setToolsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [toolsOpen]);

  const expectation = operatorToExpectation(rule.operator);
  const match = operatorToMatch(rule.operator);

  const toolLabelById = new Map<string, string>();
  catalog.forEach((agent) =>
    agent.tools.forEach((tool) => toolLabelById.set(tool.id, tool.label)),
  );

  const availableTools = (() => {
    if (!rule.agent_id) {
      const seen = new Map<string, { id: string; label: string }>();
      catalog.forEach((agent) =>
        agent.tools.forEach((tool) => seen.set(tool.id, { id: tool.id, label: tool.label })),
      );
      return Array.from(seen.values());
    }
    const agent = catalog.find((a) => a.id === rule.agent_id);
    return agent ? agent.tools.map((t) => ({ id: t.id, label: t.label })) : [];
  })();

  const changeAgent = (value: string) => {
    const agentId = value === ANY_AGENT ? null : value;
    const allowed = new Set(
      (agentId ? catalog.find((a) => a.id === agentId)?.tools ?? [] : availableTools).map(
        (t) => t.id,
      ),
    );
    onChange({ agent_id: agentId, tool_ids: rule.tool_ids.filter((id) => allowed.has(id)) });
  };

  const toggleTool = (toolId: string) => {
    const tool_ids = rule.tool_ids.includes(toolId)
      ? rule.tool_ids.filter((id) => id !== toolId)
      : [...rule.tool_ids, toolId];
    onChange({ tool_ids });
  };

  const summary = (): string => {
    const agent = rule.agent_id ? catalog.find((a) => a.id === rule.agent_id) : null;
    const agentLabel = agent ? `"${agent.label}"` : "Any agent";
    const tools = rule.tool_ids.map((id) => `"${toolLabelById.get(id) ?? id}"`);
    const scope = scopePhrase(rule, conversations);
    const successfully = rule.require_success ? "successfully " : "";
    if (expectation === "must_not_use")
      return `${agentLabel} must not use ${joinPhrases(tools, "or")} ${scope}.`;
    if (expectation === "only")
      return `${agentLabel} may only use ${joinPhrases(tools, "or")} ${scope}.`;
    const conjunction = match === "all" ? "and" : "or";
    return `${agentLabel} must ${successfully}use ${joinPhrases(tools, conjunction)} ${scope}.`;
  };

  const toolsRequired = expectation !== "only" && rule.tool_ids.length === 0;
  const matchDisabled = expectation !== "must_use";

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">Rule {index + 1}</span>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove} aria-label="Remove rule">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label>Agent</Label>
          <Select value={rule.agent_id ?? ANY_AGENT} onValueChange={changeAgent}>
            <SelectTrigger>
              <SelectValue placeholder="Any agent" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY_AGENT}>Any agent</SelectItem>
              {catalog.map((agent) => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label>Expectation</Label>
          <Select
            value={expectation}
            onValueChange={(value) =>
              onChange({ operator: toOperator(value as Expectation, match) })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EXPECTATION_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label className={cn(matchDisabled && "text-muted-foreground")}>Match</Label>
          <Select
            value={match}
            disabled={matchDisabled}
            onValueChange={(value) => onChange({ operator: toOperator("must_use", value as MatchMode) })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MATCH_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Tools multi-select — inline dropdown so it stays anchored inside the dialog */}
      <div className="space-y-1.5">
        <Label>Tools{expectation === "only" ? " (allowed set)" : ""}</Label>
        <div className="relative" ref={toolsRef}>
          <div
            role="button"
            tabIndex={0}
            onClick={() => setToolsOpen((open) => !open)}
            className="flex min-h-10 w-full cursor-pointer flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {rule.tool_ids.map((id) => (
              <span
                key={id}
                className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary"
              >
                {toolLabelById.get(id) ?? id}
                <button
                  type="button"
                  aria-label={`Remove ${toolLabelById.get(id) ?? id}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleTool(id);
                  }}
                  className="hover:text-primary/70"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            {rule.tool_ids.length === 0 && (
              <span className="text-muted-foreground">Select tools…</span>
            )}
            <ChevronDown className="ml-auto h-4 w-4 shrink-0 text-muted-foreground" />
          </div>

          {toolsOpen && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-md border bg-popover shadow-md">
              <Command>
                <CommandInput placeholder="Search tools…" />
                <CommandList>
                  <CommandEmpty>No tools for this agent.</CommandEmpty>
                  <CommandGroup>
                    {availableTools.map((tool) => {
                      const selected = rule.tool_ids.includes(tool.id);
                      return (
                        <CommandItem
                          key={tool.id}
                          value={tool.label}
                          onSelect={() => toggleTool(tool.id)}
                        >
                          <Check className={cn("mr-2 h-4 w-4", selected ? "opacity-100" : "opacity-0")} />
                          {tool.label}
                        </CommandItem>
                      );
                    })}
                  </CommandGroup>
                </CommandList>
              </Command>
            </div>
          )}
        </div>
        {toolsRequired && <p className="text-xs text-destructive">Select at least one tool.</p>}
      </div>

      <RuleScopeFields
        rule={rule}
        conversations={conversations}
        onChange={(patch: Partial<RuleScopeTarget>) => onChange(patch)}
      >
        {expectation !== "must_not_use" && (
          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <div>
              <Label className="cursor-pointer">Must succeed</Label>
              <p className="text-xs text-muted-foreground">Only count successful calls</p>
            </div>
            <Switch
              checked={Boolean(rule.require_success)}
              onCheckedChange={(checked) => onChange({ require_success: checked })}
            />
          </div>
        )}
      </RuleScopeFields>

      {/* Advanced settings */}
      <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ChevronRight className={cn("h-4 w-4 transition-transform", advancedOpen && "rotate-90")} />
          <span className="font-medium">Advanced settings</span>
          <span className="text-xs">Call limits</span>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Min calls</Label>
              <Input
                type="number"
                min={0}
                placeholder="No minimum"
                value={rule.min_calls ?? ""}
                onChange={(event) => onChange({ min_calls: toNumberOrNull(event.target.value) })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Max calls</Label>
              <Input
                type="number"
                min={0}
                placeholder="No maximum"
                value={rule.max_calls ?? ""}
                onChange={(event) => onChange({ max_calls: toNumberOrNull(event.target.value) })}
              />
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>

      <div className="rounded-md bg-primary/5 px-3 py-2">
        <p className="text-sm text-primary">{summary()}</p>
      </div>
    </div>
  );
};

// ---- builder ---------------------------------------------------------------

interface Props {
  rules: ToolUsageRule[];
  onChange: (rules: ToolUsageRule[]) => void;
  catalog: EvaluationAgentInfo[];
  conversations?: RuleConversation[];
  loading?: boolean;
  error?: string | null;
}

export const ToolUsageRuleBuilder: React.FC<Props> = ({
  rules,
  onChange,
  catalog,
  conversations = [],
  loading,
  error,
}) => {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading agents and tools…</p>;
  }
  if (error) {
    return (
      <p className="text-sm text-destructive">
        Could not load this workflow&apos;s tools. You can still save, but tools cannot be picked here.
      </p>
    );
  }

  const updateRule = (index: number, patch: Partial<ToolUsageRule>) =>
    onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));

  return (
    <div className="space-y-4">
      {catalog.length === 0 && (
        <p className="text-sm text-muted-foreground">
          This workflow has no agents with connected tools.
        </p>
      )}

      {rules.map((rule, index) => (
        <RuleCard
          key={rule.id}
          rule={rule}
          index={index}
          catalog={catalog}
          conversations={conversations}
          onChange={(patch) => updateRule(index, patch)}
          onRemove={() => onChange(rules.filter((_, i) => i !== index))}
        />
      ))}

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...rules, newToolRule()])}
      >
        <Plus className="mr-1.5 h-4 w-4" />
        Add rule
      </Button>
    </div>
  );
};

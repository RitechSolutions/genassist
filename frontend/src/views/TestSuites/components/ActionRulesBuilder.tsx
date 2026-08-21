import React from "react";
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
import { Plus, Trash2 } from "lucide-react";
import type {
  ActionRuleDraft,
  EvaluationActionNodeInfo,
  RuleConversation,
  RuleScopeTarget,
} from "@/interfaces/testEvaluation.interface";
import { RuleScopeFields } from "./RuleScopeFields";
import { scopePhrase } from "../helpers/ruleScope";
import { newRuleId } from "../helpers/evaluationForm";

export const newActionRule = (): ActionRuleDraft => ({
  id: newRuleId(),
  node: "",
  nodeType: "",
  shouldFire: true,
  scope: "every_turn",
});

interface ActionRuleRowProps {
  rule: ActionRuleDraft;
  index: number;
  nodes: EvaluationActionNodeInfo[];
  conversations: RuleConversation[];
  onChange: (patch: Partial<ActionRuleDraft>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

const ActionRuleRow: React.FC<ActionRuleRowProps> = ({
  rule,
  index,
  nodes,
  conversations,
  onChange,
  onRemove,
  canRemove,
}) => {
  const selectedNode = nodes.find((node) => node.id === rule.node);
  // Free text is only for a config the catalogue can't match: a saved node id
  // that is gone, or a legacy node_type-based config.
  const isLegacyValue =
    (Boolean(rule.node) && nodes.length > 0 && !selectedNode) || Boolean(rule.nodeType);
  const useDropdown = nodes.length > 0 && !isLegacyValue;

  const targetName = selectedNode?.label ?? rule.node ?? rule.nodeType;
  const requirement = rule.shouldFire ? "must complete" : "must not complete";
  const summary = targetName
    ? `"${targetName}" ${requirement} ${scopePhrase(rule, conversations)}.`
    : null;

  return (
    <div className="rounded-lg border p-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">Rule {index + 1}</span>
        {canRemove && (
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={onRemove}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      {useDropdown ? (
        <div>
          <Label className="text-xs">Node *</Label>
          <Select
            value={rule.node}
            onValueChange={(next) => onChange({ node: next, nodeType: "" })}
          >
            <SelectTrigger className="mt-1">
              <SelectValue placeholder="Select a node" />
            </SelectTrigger>
            <SelectContent>
              {nodes.map((node) => (
                <SelectItem key={node.id} value={node.id}>
                  {node.label} ({node.type})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <>
          <div>
            <Label className="text-xs">Node (id or label)</Label>
            <Input
              value={rule.node}
              onChange={(e) => onChange({ node: e.target.value })}
              placeholder="e.g. Create Support Ticket"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Node Type</Label>
            <Input
              value={rule.nodeType}
              onChange={(e) => onChange({ nodeType: e.target.value })}
              placeholder="e.g. httpRequestNode"
              className="mt-1"
            />
          </div>
        </>
      )}
      <div className="flex items-center justify-between rounded-lg border px-3 py-2">
        <div>
          <div className="text-xs font-medium">Must complete</div>
          <div className="text-xs text-muted-foreground">
            Turn off to require that the node does not complete successfully
          </div>
        </div>
        <Switch
          checked={rule.shouldFire}
          onCheckedChange={(checked) => onChange({ shouldFire: checked })}
        />
      </div>

      <RuleScopeFields
        rule={rule}
        conversations={conversations}
        onChange={(patch: Partial<RuleScopeTarget>) => onChange(patch)}
      />

      {summary && (
        <div className="rounded-md bg-primary/5 px-3 py-2">
          <p className="text-sm text-primary">{summary}</p>
        </div>
      )}
    </div>
  );
};

interface ActionRulesBuilderProps {
  rules: ActionRuleDraft[];
  nodes: EvaluationActionNodeInfo[];
  conversations?: RuleConversation[];
  onChange: (rules: ActionRuleDraft[]) => void;
}

export const ActionRulesBuilder: React.FC<ActionRulesBuilderProps> = ({
  rules,
  nodes,
  conversations = [],
  onChange,
}) => {
  const updateRule = (index: number, patch: Partial<ActionRuleDraft>) => {
    onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
  };

  const removeRule = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      {rules.map((rule, index) => (
        <ActionRuleRow
          key={rule.id || index}
          rule={rule}
          index={index}
          nodes={nodes}
          conversations={conversations}
          onChange={(patch) => updateRule(index, patch)}
          onRemove={() => removeRule(index)}
          canRemove={rules.length > 1}
        />
      ))}
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange([...rules, newActionRule()])}
      >
        <Plus className="mr-1 h-3.5 w-3.5" />
        Add rule
      </Button>
    </div>
  );
};

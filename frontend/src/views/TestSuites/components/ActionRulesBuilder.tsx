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
} from "@/interfaces/testEvaluation.interface";

export const newActionRule = (): ActionRuleDraft => ({
  node: "",
  nodeType: "",
  shouldFire: true,
});

interface ActionRuleRowProps {
  rule: ActionRuleDraft;
  index: number;
  nodes: EvaluationActionNodeInfo[];
  onChange: (patch: Partial<ActionRuleDraft>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

const ActionRuleRow: React.FC<ActionRuleRowProps> = ({
  rule,
  index,
  nodes,
  onChange,
  onRemove,
  canRemove,
}) => {
  const nodeInCatalog = nodes.some((node) => node.id === rule.node);
  // Free text is only for a config the catalogue can't match: a saved node id
  // that is gone, or a legacy node_type-based config.
  const isLegacyValue =
    (Boolean(rule.node) && nodes.length > 0 && !nodeInCatalog) || Boolean(rule.nodeType);
  const useDropdown = nodes.length > 0 && !isLegacyValue;

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
              placeholder="e.g. Create Zendesk Ticket"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Node Type</Label>
            <Input
              value={rule.nodeType}
              onChange={(e) => onChange({ nodeType: e.target.value })}
              placeholder="e.g. zendeskTicketNode"
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
    </div>
  );
};

interface ActionRulesBuilderProps {
  rules: ActionRuleDraft[];
  nodes: EvaluationActionNodeInfo[];
  onChange: (rules: ActionRuleDraft[]) => void;
}

export const ActionRulesBuilder: React.FC<ActionRulesBuilderProps> = ({
  rules,
  nodes,
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
          key={index}
          rule={rule}
          index={index}
          nodes={nodes}
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

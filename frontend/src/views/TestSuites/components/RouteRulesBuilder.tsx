import React from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Plus, Trash2 } from "lucide-react";
import type {
  EvaluationRouterInfo,
  RouteRuleDraft,
} from "@/interfaces/testEvaluation.interface";

export const newRouteRule = (): RouteRuleDraft => ({ router: "", expected: "" });

interface RouteRuleRowProps {
  rule: RouteRuleDraft;
  index: number;
  routers: EvaluationRouterInfo[];
  onChange: (patch: Partial<RouteRuleDraft>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

const RouteRuleRow: React.FC<RouteRuleRowProps> = ({
  rule,
  index,
  routers,
  onChange,
  onRemove,
  canRemove,
}) => {
  const selectedRouter = routers.find((router) => router.id === rule.router);
  // Free text is only for a config the catalogue can't match: a saved router id
  // that is gone, or an old "any router" config (expected set with no router).
  const isLegacyValue =
    routers.length > 0 &&
    ((Boolean(rule.router) && !selectedRouter) || (!rule.router && Boolean(rule.expected)));
  const useDropdowns = routers.length > 0 && !isLegacyValue;

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
      {useDropdowns ? (
        <>
          <div>
            <Label className="text-xs">Router *</Label>
            <Select
              value={rule.router}
              onValueChange={(next) => onChange({ router: next, expected: "" })}
            >
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select a router" />
              </SelectTrigger>
              <SelectContent>
                {routers.map((router) => (
                  <SelectItem key={router.id} value={router.id}>
                    {router.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedRouter && selectedRouter.branches.length > 0 && (
            <div>
              <Label className="text-xs">Expected Branch *</Label>
              <Select
                value={rule.expected}
                onValueChange={(next) => onChange({ expected: next })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select a branch" />
                </SelectTrigger>
                <SelectContent>
                  {selectedRouter.branches.map((branch) => (
                    <SelectItem key={branch.value} value={branch.value}>
                      {branch.destination
                        ? `${branch.value} → ${branch.destination}`
                        : branch.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {selectedRouter && selectedRouter.branches.length === 0 && (
            <div>
              <Label className="text-xs">Expected Route *</Label>
              <Input
                value={rule.expected}
                onChange={(e) => onChange({ expected: e.target.value })}
                placeholder="e.g. escalate"
                className="mt-1"
              />
            </div>
          )}
        </>
      ) : (
        <>
          <div>
            <Label className="text-xs">Expected Route *</Label>
            <Input
              value={rule.expected}
              onChange={(e) => onChange({ expected: e.target.value })}
              placeholder="e.g. escalate"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Router Node (id or label, optional)</Label>
            <Input
              value={rule.router}
              onChange={(e) => onChange({ router: e.target.value })}
              placeholder="Leave empty to match any router node"
              className="mt-1"
            />
          </div>
        </>
      )}
    </div>
  );
};

interface RouteRulesBuilderProps {
  rules: RouteRuleDraft[];
  routers: EvaluationRouterInfo[];
  onChange: (rules: RouteRuleDraft[]) => void;
}

export const RouteRulesBuilder: React.FC<RouteRulesBuilderProps> = ({
  rules,
  routers,
  onChange,
}) => {
  const updateRule = (index: number, patch: Partial<RouteRuleDraft>) => {
    onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
  };

  const removeRule = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      {rules.map((rule, index) => (
        <RouteRuleRow
          key={index}
          rule={rule}
          index={index}
          routers={routers}
          onChange={(patch) => updateRule(index, patch)}
          onRemove={() => removeRule(index)}
          canRemove={rules.length > 1}
        />
      ))}
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange([...rules, newRouteRule()])}
      >
        <Plus className="mr-1 h-3.5 w-3.5" />
        Add rule
      </Button>
    </div>
  );
};

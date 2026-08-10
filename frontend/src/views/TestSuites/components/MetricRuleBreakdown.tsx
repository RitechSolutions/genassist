import React from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import type { MetricRuleDetail } from "@/interfaces/testSuite.interface";

interface MetricRuleBreakdownProps {
  details: MetricRuleDetail[];
}

// Per-rule pass/fail lines under a multi-rule metric (Route Taken / Action Taken).
export const MetricRuleBreakdown: React.FC<MetricRuleBreakdownProps> = ({ details }) => (
  <div className="mt-1 space-y-0.5 pl-4">
    {details.map((detail, index) => (
      <div key={detail.rule_number ?? index} className="flex items-start gap-1.5 text-xs">
        {detail.passed ? (
          <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-green-600 dark:text-green-400" />
        ) : (
          <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-red-600 dark:text-red-400" />
        )}
        <span className="text-muted-foreground">{detail.comment}</span>
      </div>
    ))}
  </div>
);

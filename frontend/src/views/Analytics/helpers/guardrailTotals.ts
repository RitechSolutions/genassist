import { guardrailCheckLabel } from "@/helpers/guardrailChecks";
import type { GuardrailTotalsItem } from "@/interfaces/analyticsReports.interface";

export const summarizeGuardrailTotals = (items: GuardrailTotalsItem[]) => {
  const rows = items
    .filter((item) => item.blocked + item.flagged > 0)
    .map((item) => ({ ...item, label: guardrailCheckLabel(item) }))
    .sort(
      (a, b) =>
        b.blocked + b.flagged - (a.blocked + a.flagged) ||
        a.label.localeCompare(b.label)
    );
  const sum = (key: "blocked" | "flagged" | "errors") =>
    items.reduce((total, item) => total + item[key], 0);
  const busiest = rows[0] ? rows[0].blocked + rows[0].flagged : 0;
  return {
    rows,
    busiest,
    blocked: sum("blocked"),
    flagged: sum("flagged"),
    failed: sum("errors"),
  };
};

export const segmentWidth = (count: number, busiest: number): string =>
  count > 0 && busiest > 0 ? `${Math.max((count / busiest) * 100, 1.5)}%` : "0%";

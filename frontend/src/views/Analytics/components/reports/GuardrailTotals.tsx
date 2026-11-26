import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { guardrailCheckLabel } from "@/helpers/guardrailChecks";
import { cn } from "@/helpers/utils";
import type { GuardrailTotalsItem } from "@/interfaces/analyticsReports.interface";
import { analyticsFadeUpClass } from "../../constants/animations";

export function GuardrailTotals({ items }: { items: GuardrailTotalsItem[] }) {
  return (
    <Card className={cn("bg-card dark:bg-zinc-900", analyticsFadeUpClass)}>
      <CardHeader className="pb-4">
        <CardTitle className="text-base font-semibold">Guardrails</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/80">
                <th className="text-left py-2.5 px-2 sm:px-4 font-medium text-muted-foreground">Check</th>
                <th className="text-right py-2.5 px-2 sm:px-4 font-medium text-muted-foreground">Blocked</th>
                <th className="text-right py-2.5 px-2 sm:px-4 font-medium text-muted-foreground">Flagged</th>
                <th className="text-right py-2.5 px-2 sm:px-4 font-medium text-muted-foreground">Errors</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.check_type} className="border-t border-border hover:bg-muted/50">
                  <td className="py-2.5 px-2 sm:px-4 font-medium">{guardrailCheckLabel(item)}</td>
                  <td className="text-right py-2.5 px-2 sm:px-4 tabular-nums">{item.blocked.toLocaleString()}</td>
                  <td className="text-right py-2.5 px-2 sm:px-4 tabular-nums">{item.flagged.toLocaleString()}</td>
                  <td className="text-right py-2.5 px-2 sm:px-4 tabular-nums">{item.errors.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

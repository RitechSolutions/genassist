import { useEffect, useMemo, useState } from "react";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { Coins, DollarSign, Layers, PhoneCall, PieChart } from "lucide-react";

import { Card, CardContent } from "@/components/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ExportButton } from "@/components/ui/ExportButton";
import { formatUsd } from "@/helpers/formatCurrency";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { fetchLlmUsageBreakdown, fetchLlmUsageSummary } from "@/services/llmUsage";
import type {
  LlmUsageBreakdownItem,
  LlmUsageDimension,
  LlmUsageSummaryResponse,
} from "@/interfaces/llmUsage.interface";

import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "../components/AnalyticsKpiStat";
import { analyticsFadeUpClass } from "../constants/animations";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import { LlmUsageBreakdownChart } from "../components/reports/LlmUsageBreakdownChart";

const DIMENSIONS: Array<{ value: LlmUsageDimension; label: string }> = [
  { value: "provider", label: "Provider" },
  { value: "model", label: "Model" },
  { value: "agent", label: "Agent" },
];

function LlmUsagePage() {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  } as DateRange);
  const { groups, showGroupFilter, groupFilter, setGroupFilter, agentFilter, setAgentFilter, agents, filterParams } =
    useAnalyticsFilters();

  const [dimension, setDimension] = useState<LlmUsageDimension>("provider");
  const [summary, setSummary] = useState<LlmUsageSummaryResponse | null>(null);
  const [items, setItems] = useState<LlmUsageBreakdownItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      const params = { ...filterParams, ...toExpandedUTCDateRange(dateRange) };
      try {
        const [summaryRes, breakdownRes] = await Promise.all([
          fetchLlmUsageSummary(params),
          fetchLlmUsageBreakdown(dimension, params),
        ]);
        if (!active) return;
        setSummary(summaryRes);
        setItems(breakdownRes?.items ?? []);
      } catch {
        if (active) setError("Failed to load LLM usage data.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [dateRange, filterParams, dimension]);

  const exportParams = useMemo(
    () => ({ ...filterParams, ...toExpandedUTCDateRange(dateRange), dimension }),
    [filterParams, dateRange, dimension]
  );

  const dimensionLabel = DIMENSIONS.find((d) => d.value === dimension)?.label ?? "Provider";

  const columns: Column<LlmUsageBreakdownItem>[] = [
    { header: dimensionLabel, key: "label", cell: (i) => <span className="font-medium">{i.label}</span> },
    {
      header: "Cost",
      key: "cost_usd",
      sortable: true,
      sortValue: (i) => i.cost_usd,
      cell: (i) => (
        <span className="tabular-nums">
          {formatUsd(i.cost_usd)}
          {i.cost_is_partial && <span className="ml-1 text-xs text-amber-500">partial</span>}
        </span>
      ),
    },
    {
      header: "Tokens",
      key: "total_tokens",
      sortable: true,
      sortValue: (i) => i.total_tokens,
      cell: (i) => <span className="tabular-nums">{i.total_tokens.toLocaleString()}</span>,
    },
    {
      header: "Calls",
      key: "calls",
      sortable: true,
      sortValue: (i) => i.calls,
      cell: (i) => <span className="tabular-nums">{i.calls.toLocaleString()}</span>,
    },
    {
      header: "Unpriced",
      key: "unpriced_calls",
      sortable: true,
      sortValue: (i) => i.unpriced_calls,
      cell: (i) => <span className="tabular-nums">{i.unpriced_calls.toLocaleString()}</span>,
    },
  ];

  const kpis = [
    {
      label: "Total LLM Cost",
      value: formatUsd(summary?.total_cost_usd),
      icon: DollarSign,
      sub: summary?.cost_is_partial ? "Partial — some calls are unpriced" : undefined,
    },
    {
      label: "Cost / Conversation",
      value: formatUsd(summary?.cost_per_conversation_usd),
      icon: PhoneCall,
    },
    {
      label: "Priced Coverage",
      value: `${(summary?.priced_token_coverage_pct ?? 0).toFixed(1)}%`,
      icon: PieChart,
      sub: `${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced calls`,
    },
    {
      label: "Total Tokens",
      value: (summary?.total_tokens ?? 0).toLocaleString(),
      icon: Coins,
    },
    {
      label: "Total Calls",
      value: (summary?.total_calls ?? 0).toLocaleString(),
      icon: Layers,
    },
  ];

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <AnalyticsPageHeader title="LLM Usage" subtitle="Token and cost usage per provider, model, and agent">
          <AnalyticsFilters
            groups={showGroupFilter ? groups : undefined}
            groupFilter={groupFilter}
            onGroupFilterChange={setGroupFilter}
            agents={agents}
            agentFilter={agentFilter}
            onAgentFilterChange={setAgentFilter}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
          >
            <ExportButton
              endpoint="/analytics/llm-usage/export"
              params={exportParams}
              filename="llm-usage"
              disabled={loading || items.length === 0}
            />
          </AnalyticsFilters>
        </AnalyticsPageHeader>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <Card className={analyticsFadeUpClass}>
          <CardContent className="pt-6">
            <div className={analyticsKpiGridClass(kpis.length)}>
              {kpis.map((k) => (
                <AnalyticsKpiStat key={k.label} label={k.label} value={k.value} icon={k.icon} sub={k.sub} />
              ))}
            </div>
            {summary?.cost_source === "daily_stats" && (
              <p className="mt-4 text-xs text-muted-foreground">
                These figures read the usage ledger. The main dashboard keeps healed daily stats until ledger cutover.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Group by</span>
          <Select value={dimension} onValueChange={(v) => setDimension(v as LlmUsageDimension)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DIMENSIONS.map((d) => (
                <SelectItem key={d.value} value={d.value}>
                  {d.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <LlmUsageBreakdownChart items={items} dimensionLabel={dimensionLabel} loading={loading} />

        <div className={analyticsFadeUpClass}>
          <DataTable
            data={items}
            columns={columns}
            loading={loading}
            error={error}
            emptyMessage="No LLM usage recorded for this period."
            keyExtractor={(item) => item.key}
            pageSize={10}
          />
        </div>
      </div>
    </div>
  );
}

export default LlmUsagePage;

import { useEffect, useMemo, useState } from "react";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { Activity, AlertTriangle, Coins, DollarSign, Percent, PhoneCall, SlidersHorizontal } from "lucide-react";

import { Card, CardContent } from "@/components/card";
import { Button } from "@/components/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ExportButton } from "@/components/ui/ExportButton";
import Can from "@/hooks/Can";
import { formatUsd } from "@/helpers/formatCurrency";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { fetchLlmUsageBreakdown, fetchLlmUsageSummary, fetchLlmUsageTimeseries } from "@/services/llmUsage";
import type {
  LlmUsageBreakdownItem,
  LlmUsageDimension,
  LlmUsageSummaryResponse,
  LlmUsageTimeseriesItem,
} from "@/interfaces/llmUsage.interface";
import { LlmCostRatesDialog } from "@/views/LlmProviders/components/LlmCostRatesDialog";

import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "../components/AnalyticsKpiStat";
import { analyticsFadeUpClass } from "../constants/animations";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import { LlmUsageProviderDonut } from "../components/reports/LlmUsageProviderDonut";
import { LlmUsageTimeseriesChart, type SpendMetric } from "../components/reports/LlmUsageTimeseriesChart";

const DIMENSIONS: Array<{ value: LlmUsageDimension; label: string }> = [
  { value: "provider", label: "Provider" },
  { value: "model", label: "Model" },
  { value: "agent", label: "Agent" },
  { value: "source", label: "Source" },
];

const compact = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : `${n}`;

function LlmUsagePage() {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  } as DateRange);
  const { groups, showGroupFilter, groupFilter, setGroupFilter, agentFilter, setAgentFilter, agents, filterParams } =
    useAnalyticsFilters();

  const [dimension, setDimension] = useState<LlmUsageDimension>("provider");
  const [spendMetric, setSpendMetric] = useState<SpendMetric>("cost");
  const [summary, setSummary] = useState<LlmUsageSummaryResponse | null>(null);
  const [timeseries, setTimeseries] = useState<LlmUsageTimeseriesItem[]>([]);
  const [providerItems, setProviderItems] = useState<LlmUsageBreakdownItem[]>([]);
  const [sourceItems, setSourceItems] = useState<LlmUsageBreakdownItem[]>([]);
  const [items, setItems] = useState<LlmUsageBreakdownItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ratesOpen, setRatesOpen] = useState(false);

  // Filter-scoped data: KPIs, spend-over-time, provider donut, workflow/analyst split
  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      const params = { ...filterParams, ...toExpandedUTCDateRange(dateRange) };
      try {
        const [summaryRes, timeseriesRes, providerRes, sourceRes] = await Promise.all([
          fetchLlmUsageSummary(params),
          fetchLlmUsageTimeseries(params),
          fetchLlmUsageBreakdown("provider", params),
          fetchLlmUsageBreakdown("source", params),
        ]);
        if (!active) return;
        setSummary(summaryRes);
        setTimeseries(timeseriesRes?.items ?? []);
        setProviderItems(providerRes?.items ?? []);
        setSourceItems(sourceRes?.items ?? []);
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
  }, [dateRange, filterParams]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setTableLoading(true);
      const params = { ...filterParams, ...toExpandedUTCDateRange(dateRange) };
      const res = await fetchLlmUsageBreakdown(dimension, params);
      if (!active) return;
      setItems(res?.items ?? []);
      setTableLoading(false);
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
  const costFor = (key: string) => sourceItems.find((i) => i.key === key)?.cost_usd ?? 0;
  const unpricedTokenPct = 100 - (summary?.priced_token_coverage_pct ?? 100);
  const totalItemCost = items.reduce((sum, i) => sum + i.cost_usd, 0);

  const columns: Column<LlmUsageBreakdownItem>[] = [
    { header: dimensionLabel, key: "label", cell: (i) => <span className="font-medium">{i.label}</span> },
    {
      header: "Calls",
      key: "calls",
      sortable: true,
      sortValue: (i) => i.calls,
      cell: (i) => <span className="tabular-nums">{i.calls.toLocaleString()}</span>,
    },
    {
      header: "Tokens",
      key: "total_tokens",
      sortable: true,
      sortValue: (i) => i.total_tokens,
      cell: (i) => <span className="tabular-nums">{i.total_tokens.toLocaleString()}</span>,
    },
    {
      header: "Cost",
      key: "cost_usd",
      sortable: true,
      sortValue: (i) => i.cost_usd,
      cell: (i) => (
        <span className="tabular-nums font-semibold">
          {formatUsd(i.cost_usd)}
          {i.cost_is_partial && <span className="ml-1 text-xs font-normal text-amber-500">partial</span>}
        </span>
      ),
    },
    {
      header: "Avg / Call",
      key: "avg",
      cell: (i) => <span className="tabular-nums text-muted-foreground">{formatUsd(i.calls ? i.cost_usd / i.calls : 0)}</span>,
    },
    {
      header: "Share",
      key: "share",
      cell: (i) => {
        const pct = totalItemCost > 0 ? (i.cost_usd / totalItemCost) * 100 : 0;
        return (
          <div className="flex items-center justify-end gap-2 tabular-nums">
            <span className="h-1.5 w-14 overflow-hidden rounded-full bg-muted">
              <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </span>
            {pct.toFixed(1)}%
          </div>
        );
      },
    },
  ];

  const kpis = [
    {
      label: "Total LLM Cost",
      value: formatUsd(summary?.total_cost_usd),
      icon: DollarSign,
      sub: `Workflow ${formatUsd(costFor("workflow"), 2)} · Analyst ${formatUsd(costFor("llm_analyst"), 2)}`,
    },
    {
      label: "Total Tokens",
      value: compact(summary?.total_tokens ?? 0),
      icon: Coins,
      sub: `${compact(summary?.total_input_tokens ?? 0)} input · ${compact(summary?.total_output_tokens ?? 0)} output`,
    },
    {
      label: "LLM Calls",
      value: (summary?.total_calls ?? 0).toLocaleString(),
      icon: Activity,
      sub: `${((summary?.total_calls ?? 0) - (summary?.unpriced_calls ?? 0)).toLocaleString()} priced · ${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced`,
    },
    {
      label: "Cost / Conversation",
      value: formatUsd(summary?.cost_per_conversation_usd),
      icon: PhoneCall,
      sub: summary?.non_conversation_cost_usd
        ? `${formatUsd(summary.non_conversation_cost_usd, 2)} non-conversation`
        : undefined,
    },
    {
      label: "Pricing Coverage",
      value: `${(summary?.priced_token_coverage_pct ?? 0).toFixed(1)}%`,
      icon: Percent,
      sub: `${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced calls`,
    },
  ];

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <AnalyticsPageHeader
          title="LLM Usage"
          subtitle="Token consumption and LLM spend across workflows and metric analysis"
        >
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
            <Can permissions={["update:llm_provider"]}>
              <Button variant="outline" size="sm" onClick={() => setRatesOpen(true)}>
                <SlidersHorizontal className="h-4 w-4" />
                Manage rates
              </Button>
            </Can>
            <ExportButton
              endpoint="/analytics/llm-usage/export"
              params={exportParams}
              filename="llm-usage"
              disabled={loading || items.length === 0}
            />
          </AnalyticsFilters>
        </AnalyticsPageHeader>

        {error && <p className="text-sm text-red-500">{error}</p>}

        {summary?.cost_is_partial && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              <span className="font-semibold">{unpricedTokenPct.toFixed(1)}% of tokens have no configured rate.</span>{" "}
              Totals below are the priced subtotal — add rates to complete cost coverage.
            </span>
            <Can permissions={["update:llm_provider"]}>
              <button onClick={() => setRatesOpen(true)} className="ml-auto whitespace-nowrap font-semibold underline underline-offset-2">
                Manage rates
              </button>
            </Can>
          </div>
        )}

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

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <LlmUsageTimeseriesChart
              items={timeseries}
              loading={loading}
              metric={spendMetric}
              onMetricChange={setSpendMetric}
            />
          </div>
          <LlmUsageProviderDonut items={providerItems} loading={loading} />
        </div>

        <Card className={analyticsFadeUpClass}>
          <CardContent className="pt-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-foreground">Usage by {dimensionLabel}</h3>
              <div className="inline-flex overflow-hidden rounded-md border border-border">
                {DIMENSIONS.map((d) => (
                  <button
                    key={d.value}
                    onClick={() => setDimension(d.value)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      dimension === d.value
                        ? "bg-primary/10 text-primary"
                        : "bg-background text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
            <DataTable
              data={items}
              columns={columns}
              loading={tableLoading}
              error={error}
              emptyMessage="No LLM usage recorded for this period."
              keyExtractor={(item) => item.key}
              pageSize={10}
            />
          </CardContent>
        </Card>
      </div>

      <LlmCostRatesDialog open={ratesOpen} onOpenChange={setRatesOpen} />
    </div>
  );
}

export default LlmUsagePage;

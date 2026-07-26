import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { Activity, AlertTriangle, Coins, DollarSign, Info, Percent, PhoneCall, SlidersHorizontal } from "lucide-react";

import { Card, CardContent } from "@/components/card";
import { Button } from "@/components/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ExportButton } from "@/components/ui/ExportButton";
import { usePermissions } from "@/context/PermissionContext";
import { formatUsd } from "@/helpers/formatCurrency";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { cn } from "@/helpers/utils";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import {
  fetchLlmUsageBreakdown,
  fetchLlmUsageFilterOptions,
  fetchLlmUsageSummary,
  fetchLlmUsageTimeseries,
} from "@/services/llmUsage";
import type {
  LlmUsageBreakdownItem,
  LlmUsageDimension,
  LlmUsageQueryFilters,
} from "@/interfaces/llmUsage.interface";
import { LlmCostRatesDialog } from "@/views/LlmProviders/components/LlmCostRatesDialog";

import { AnalyticsFilters, analyticsFilterSelectTriggerClassName } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "../components/AnalyticsKpiStat";
import { analyticsFadeUpClass } from "../constants/animations";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import { LlmUsageBreakdownChart } from "../components/reports/LlmUsageBreakdownChart";
import { LlmUsageProviderDonut } from "../components/reports/LlmUsageProviderDonut";
import { LlmUsageTimeseriesChart, type SpendMetric } from "../components/reports/LlmUsageTimeseriesChart";

const DIMENSIONS: Array<{ value: LlmUsageDimension; label: string; heading?: string }> = [
  { value: "provider", label: "Provider" },
  { value: "model", label: "Model" },
  { value: "agent", label: "Agent" },
  { value: "source", label: "Usage type", heading: "Type" },
];

const ALL = "all";
const RATE_PERMISSION = "update:llm_provider";

const compact = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : `${n}`;

function LlmUsagePage() {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  } as DateRange);
  const { groups, showGroupFilter, groupFilter, setGroupFilter, agentFilter, setAgentFilter, agents, filterParams } =
    useAnalyticsFilters();

  const [provider, setProvider] = useState(ALL);
  const [model, setModel] = useState(ALL);
  const [dimension, setDimension] = useState<LlmUsageDimension>("provider");
  const [spendMetric, setSpendMetric] = useState<SpendMetric>("cost");
  const [ratesOpen, setRatesOpen] = useState(false);

  const permissions = usePermissions();
  const canManageRates = permissions.includes("*") || permissions.includes(RATE_PERMISSION);

  const dateParams = useMemo(() => toExpandedUTCDateRange(dateRange), [dateRange]);
  const queryFilters = useMemo<LlmUsageQueryFilters>(
    () => ({
      ...filterParams,
      ...dateParams,
      provider: provider !== ALL ? provider : undefined,
      model: model !== ALL ? model : undefined,
    }),
    [filterParams, dateParams, provider, model]
  );
  const filterKey = [
    dateParams.from_date,
    dateParams.to_date,
    filterParams.group_id,
    filterParams.agent_id,
    provider,
    model,
  ];

  const overview = useQuery({
    queryKey: ["llm-usage", "overview", ...filterKey],
    queryFn: async () => {
      const [summary, timeseries, providerBreakdown, sourceBreakdown] = await Promise.all([
        fetchLlmUsageSummary(queryFilters),
        fetchLlmUsageTimeseries(queryFilters),
        fetchLlmUsageBreakdown("provider", queryFilters),
        fetchLlmUsageBreakdown("source", queryFilters),
      ]);
      return {
        summary,
        timeseries: timeseries.items,
        providerItems: providerBreakdown.items,
        sourceItems: sourceBreakdown.items,
      };
    },
    placeholderData: keepPreviousData,
  });

  const breakdown = useQuery({
    queryKey: ["llm-usage", "breakdown", dimension, ...filterKey],
    queryFn: () => fetchLlmUsageBreakdown(dimension, queryFilters),
    placeholderData: keepPreviousData,
  });

  const filterOptions = useQuery({
    queryKey: ["llm-usage", "filter-options", ...filterKey],
    queryFn: () => fetchLlmUsageFilterOptions(queryFilters),
    placeholderData: keepPreviousData,
  });

  const summary = overview.data?.summary;
  const timeseries = overview.data?.timeseries ?? [];
  const providerItems = overview.data?.providerItems ?? [];
  const sourceItems = overview.data?.sourceItems ?? [];
  const items = breakdown.data?.items ?? [];

  const overviewLoading = overview.isPending || overview.isPlaceholderData;
  const tableLoading = breakdown.isPending || breakdown.isPlaceholderData;
  const error = overview.error || breakdown.error ? "Failed to load cost data." : null;

  const options = filterOptions.isPlaceholderData ? undefined : filterOptions.data;

  useEffect(() => {
    if (!options) return;
    if (provider !== ALL && !options.providers.includes(provider)) setProvider(ALL);
    if (model !== ALL && !options.models.includes(model)) setModel(ALL);
  }, [options, provider, model]);

  const onProviderChange = (value: string) => {
    setProvider(value);
    setModel(ALL);
  };

  const exportParams = useMemo(() => ({ ...queryFilters, dimension }), [queryFilters, dimension]);

  const activeDimension = DIMENSIONS.find((d) => d.value === dimension);
  const dimensionLabel = activeDimension?.label ?? "Provider";
  const dimensionHeading = activeDimension?.heading ?? dimensionLabel;
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
      cell: (i) => (
        <span className="tabular-nums text-muted-foreground">{formatUsd(i.calls ? i.cost_usd / i.calls : 0)}</span>
      ),
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
      value: summary ? `${summary.priced_token_coverage_pct.toFixed(1)}%` : "—",
      icon: Percent,
      sub: `${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced calls`,
    },
  ];

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <AnalyticsPageHeader
          title="Cost Explorer"
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
            <Select value={provider} onValueChange={onProviderChange}>
              <SelectTrigger className={cn(analyticsFilterSelectTriggerClassName, "shrink-0")}>
                <SelectValue placeholder="All providers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All providers</SelectItem>
                {(options?.providers ?? []).map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={model} onValueChange={setModel}>
              <SelectTrigger className={cn(analyticsFilterSelectTriggerClassName, "shrink-0")}>
                <SelectValue placeholder="All models" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All models</SelectItem>
                {(options?.models ?? []).map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {canManageRates && (
              <Button variant="outline" size="sm" onClick={() => setRatesOpen(true)}>
                <SlidersHorizontal className="h-4 w-4" />
                Manage costs
              </Button>
            )}
            <ExportButton
              endpoint="/analytics/llm-usage/export"
              params={exportParams}
              filename="llm-usage"
              disabled={overviewLoading || tableLoading || items.length === 0}
            />
          </AnalyticsFilters>
        </AnalyticsPageHeader>

        {error && <p className="text-sm text-red-500">{error}</p>}

        {summary && summary.unpriced_calls > 0 && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              <span className="font-semibold">{unpricedTokenPct.toFixed(1)}% of tokens have no configured rate.</span>{" "}
              Totals below are the priced subtotal — add rates to complete cost coverage.
            </span>
            {canManageRates && (
              <button
                onClick={() => setRatesOpen(true)}
                className="ml-auto whitespace-nowrap font-semibold underline underline-offset-2"
              >
                Manage costs
              </button>
            )}
          </div>
        )}

        {summary && summary.fallback_calls > 0 && (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">
            <Info className="h-4 w-4 shrink-0" />
            <span>
              <span className="font-semibold text-foreground">
                {summary.fallback_calls.toLocaleString()} calls used bundled fallback rates.
              </span>{" "}
              Add matching rates to price them from your own configuration.
            </span>
          </div>
        )}

        <Card className={analyticsFadeUpClass}>
          <CardContent className="pt-6">
            <div className={analyticsKpiGridClass(kpis.length)}>
              {kpis.map((k) => (
                <AnalyticsKpiStat key={k.label} label={k.label} value={k.value} icon={k.icon} sub={k.sub} />
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <LlmUsageTimeseriesChart
              items={timeseries}
              loading={overviewLoading}
              metric={spendMetric}
              onMetricChange={setSpendMetric}
            />
          </div>
          <LlmUsageProviderDonut items={providerItems} loading={overviewLoading} />
        </div>

        <LlmUsageBreakdownChart items={items} dimensionLabel={dimensionHeading} loading={tableLoading} />

        <Card className={analyticsFadeUpClass}>
          <CardContent className="pt-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-foreground">Usage by {dimensionHeading}</h3>
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
              emptyMessage="No LLM costs recorded for this period."
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

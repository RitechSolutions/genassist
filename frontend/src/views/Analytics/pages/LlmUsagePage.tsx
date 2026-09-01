import { useEffect, useMemo, useState, type ReactNode } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { format } from "date-fns";
import {
  Activity,
  AlertTriangle,
  Coins,
  DollarSign,
  Info,
  MessageSquare,
  Percent,
  TrendingDown,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/card";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ExportButton } from "@/components/ui/ExportButton";
import { formatUsd } from "@/helpers/formatCurrency";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { cn } from "@/helpers/utils";
import { useDismissibleNotice } from "@/hooks/useDismissibleNotice";
import { COMPARE_DATE_RANGE_STORAGE_KEY, usePersistedDateRange } from "@/hooks/usePersistedDateRange";
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
  LlmUsageSummaryResponse,
} from "@/interfaces/llmUsage.interface";

import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "../components/AnalyticsKpiStat";
import { LlmUsageTableEmptyState } from "../components/AnalyticsEmptyStates";
import { ALL_FILTER_VALUE, AnalyticsFilterMenu } from "../components/AnalyticsFilterMenu";
import { analyticsFadeUpClass } from "../constants/animations";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import { LlmUsageBreakdownChart } from "../components/reports/LlmUsageBreakdownChart";
import { LlmUsageCostShare } from "../components/reports/LlmUsageCostShare";
import { LlmUsageEvaluationMethods } from "../components/reports/LlmUsageEvaluationMethods";
import { LlmUsageProviderDonut } from "../components/reports/LlmUsageProviderDonut";
import { LlmUsageTimeseriesChart, type SpendMetric } from "../components/reports/LlmUsageTimeseriesChart";

// Provider is covered by the always-on Provider share card, so it stays out of this selector
const DIMENSIONS: Array<{ value: LlmUsageDimension; label: string; heading?: string }> = [
  { value: "model", label: "Model" },
  { value: "agent", label: "Agent" },
  { value: "source", label: "Usage type", heading: "Type" },
];

const ALL = ALL_FILTER_VALUE;
const KPI_SUB_CLASS = "text-sm font-medium text-muted-foreground";
const EVALUATION_KEY = "evaluation";
const COVERAGE_NOTICE = "llm-unpriced-coverage";
const PARTIAL_COST_HELP =
  "Some calls here ran on a model with no configured rate. " +
  "This figure is the priced subtotal, real spend may be higher. Add the missing rates under " +
  "LLM Settings › LLM Providers to price them.";

interface LlmUsageKpi {
  label: string;
  value: string;
  icon: LucideIcon;
  sub?: string;
  description?: string;
  delta: ReactNode;
}

const compact = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : `${n}`;

/** Percentage change against the comparison period */
const pctChange = (current: number, previous: number): number | null => {
  if (previous === 0) return current > 0 ? 100 : null;
  return Math.round(((current - previous) / previous) * 100 * 10) / 10;
};

/** Percentage-point difference, for metrics already expressed as a rate */
const ppDiff = (current: number, previous: number): number | null => {
  const diff = Math.round((current - previous) * 10) / 10;
  return diff === 0 ? null : diff;
};

interface KpiDeltaProps {
  delta: number | null | undefined;
  unit?: "%" | "pp";
  tone?: "neutral" | "semantic";
}

function KpiDelta({ delta, unit = "%", tone = "semantic" }: KpiDeltaProps) {
  if (delta === undefined || delta === null || delta === 0) return null;
  const rising = delta > 0;
  const Icon = rising ? TrendingUp : TrendingDown;
  const color =
    tone === "neutral"
      ? "text-muted-foreground"
      : rising
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-rose-500";
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", color)}>
      <Icon className="h-3 w-3" aria-hidden />
      {rising ? "+" : ""}
      {delta.toFixed(1)}
      {unit === "pp" ? " pp" : "%"}
    </span>
  );
}

function LlmUsagePage() {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  } as DateRange);
  const [compareDateRange, setCompareDateRange] = usePersistedDateRange(undefined, COMPARE_DATE_RANGE_STORAGE_KEY);
  const { groups, showGroupFilter, groupFilter, setGroupFilter, agentFilter, setAgentFilter, agents, filterParams } =
    useAnalyticsFilters();

  const [provider, setProvider] = useState(ALL);
  const [model, setModel] = useState(ALL);
  const [dimension, setDimension] = useState<LlmUsageDimension>("model");
  const [spendMetric, setSpendMetric] = useState<SpendMetric>("cost");
  const [evalExpanded, setEvalExpanded] = useState(false);

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

  const evalMethods = useQuery({
    queryKey: ["llm-usage", "breakdown", "evaluation_method", ...filterKey],
    queryFn: () => fetchLlmUsageBreakdown("evaluation_method", queryFilters),
    enabled: evalExpanded && dimension === "source",
    placeholderData: keepPreviousData,
  });

  const showNodePanel = agentFilter !== ALL;
  const agentNodes = useQuery({
    queryKey: ["llm-usage", "breakdown", "node", ...filterKey],
    queryFn: () => fetchLlmUsageBreakdown("node", queryFilters),
    enabled: showNodePanel,
    placeholderData: keepPreviousData,
  });

  const filterOptions = useQuery({
    queryKey: ["llm-usage", "filter-options", ...filterKey],
    queryFn: () => fetchLlmUsageFilterOptions(queryFilters),
    placeholderData: keepPreviousData,
  });

  const hasCompare = Boolean(compareDateRange?.from && compareDateRange?.to);
  const compareParams = useMemo<LlmUsageQueryFilters>(
    () => ({ ...queryFilters, ...toExpandedUTCDateRange(compareDateRange) }),
    [queryFilters, compareDateRange]
  );

  const compare = useQuery<LlmUsageSummaryResponse>({
    queryKey: [
      "llm-usage",
      "compare",
      compareParams.from_date,
      compareParams.to_date,
      filterParams.group_id,
      filterParams.agent_id,
      provider,
      model,
    ],
    queryFn: () => fetchLlmUsageSummary(compareParams),
    enabled: hasCompare,
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

  const exportParams = useMemo(() => ({ ...queryFilters, dimension }), [queryFilters, dimension]);

  const activeDimension = DIMENSIONS.find((d) => d.value === dimension);
  const dimensionLabel = activeDimension?.label ?? "Model";
  const dimensionHeading = activeDimension?.heading ?? dimensionLabel;
  const costFor = (key: string) => sourceItems.find((i) => i.key === key)?.cost_usd ?? 0;
  const unpricedTokenPct = 100 - (summary?.priced_token_coverage_pct ?? 100);
  const totalItemCost = items.reduce((sum, i) => sum + i.cost_usd, 0);
  const previous = hasCompare ? compare.data : undefined;
  const hasPartialCost = items.some((i) => i.cost_is_partial);
  const coverageNotice = useDismissibleNotice(COVERAGE_NOTICE, summary?.last_unpriced_at);

  const isEvaluationRow = (i: LlmUsageBreakdownItem) => dimension === "source" && i.key === EVALUATION_KEY;

  // Only a settled response may label the row, so a filter change can't flash a stale count
  const evaluationMethodCount =
    !evalMethods.isPlaceholderData && !evalMethods.isError ? evalMethods.data?.total : undefined;
  const methodCountLabel = evaluationMethodCount
    ? `${evaluationMethodCount} ${evaluationMethodCount === 1 ? "method" : "methods"}`
    : null;

  const columns: Column<LlmUsageBreakdownItem>[] = [
    {
      header: dimensionLabel,
      key: "label",
      cell: (i) =>
        isEvaluationRow(i) ? (
          // No onClick: the native click bubbles to the row handler, keyboard included
          <button
            type="button"
            aria-expanded={evalExpanded}
            className="flex items-center gap-2 rounded text-left font-medium ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <span>{i.label}</span>
            {methodCountLabel && <span className="text-xs font-normal text-muted-foreground">{methodCountLabel}</span>}
          </button>
        ) : (
          <span className="font-medium">{i.label}</span>
        ),
    },
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
      description: hasPartialCost ? PARTIAL_COST_HELP : undefined,
      cell: (i) => <span className="tabular-nums font-semibold">{formatUsd(i.cost_usd)}</span>,
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
      cell: (i) => <LlmUsageCostShare costUsd={i.cost_usd} totalCostUsd={totalItemCost} />,
    },
  ];

  const cacheReadTokens = summary?.total_cache_read_tokens ?? 0;
  const cacheWriteTokens = summary?.total_cache_creation_tokens ?? 0;

  const kpis: LlmUsageKpi[] = [
    {
      label: "Total LLM Cost",
      value: formatUsd(summary?.total_cost_usd),
      icon: DollarSign,
      sub: `Workflow ${formatUsd(costFor("workflow"), 2)} · Analyst ${formatUsd(costFor("llm_analyst"), 2)}`,
      delta:
        summary && previous ? <KpiDelta delta={pctChange(summary.total_cost_usd, previous.total_cost_usd)} /> : null,
    },
    {
      label: "Total Tokens",
      value: compact(summary?.total_tokens ?? 0),
      icon: Coins,
      sub: `${compact(summary?.total_input_tokens ?? 0)} input · ${compact(summary?.total_output_tokens ?? 0)} output`,
      description:
        cacheReadTokens || cacheWriteTokens
          ? `Input includes ${cacheReadTokens.toLocaleString()} cache-read and ${cacheWriteTokens.toLocaleString()} cache-write tokens reported by providers.`
          : undefined,
      delta: summary && previous ? <KpiDelta delta={pctChange(summary.total_tokens, previous.total_tokens)} /> : null,
    },
    {
      label: "LLM Calls",
      value: (summary?.total_calls ?? 0).toLocaleString(),
      icon: Activity,
      sub: `${((summary?.total_calls ?? 0) - (summary?.unpriced_calls ?? 0)).toLocaleString()} priced · ${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced`,
      delta: summary && previous ? <KpiDelta delta={pctChange(summary.total_calls, previous.total_calls)} /> : null,
    },
    {
      label: "Cost / Conversation",
      value: formatUsd(summary?.cost_per_conversation_usd),
      icon: MessageSquare,
      sub: summary?.agent_studio_test_cost_usd
        ? `${formatUsd(summary.agent_studio_test_cost_usd, 2)} agent studio tests`
        : undefined,
      delta:
        summary?.cost_per_conversation_usd != null && previous?.cost_per_conversation_usd != null ? (
          <KpiDelta delta={pctChange(summary.cost_per_conversation_usd, previous.cost_per_conversation_usd)} />
        ) : null,
    },
    {
      label: "Pricing Coverage",
      value: summary ? `${summary.priced_token_coverage_pct.toFixed(1)}%` : "—",
      icon: Percent,
      sub: `${(summary?.unpriced_calls ?? 0).toLocaleString()} unpriced calls`,
      // Coverage is a rate, so it compares in points
      delta:
        summary && previous ? (
          <KpiDelta
            delta={ppDiff(summary.priced_token_coverage_pct, previous.priced_token_coverage_pct)}
            unit="pp"
            tone="semantic"
          />
        ) : null,
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
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            compareDateRange={compareDateRange}
            onCompareDateRangeChange={setCompareDateRange}
          >
            <AnalyticsFilterMenu
              groups={showGroupFilter ? groups : undefined}
              groupFilter={groupFilter}
              onGroupFilterChange={setGroupFilter}
              agents={agents}
              agentFilter={agentFilter}
              onAgentFilterChange={setAgentFilter}
              extraGroups={[
                {
                  key: "model",
                  label: "Model",
                  allLabel: "All models",
                  value: model,
                  options: (options?.models ?? []).map((m) => ({ value: m, label: m })),
                  onChange: setModel,
                },
              ]}
            />
            <ExportButton
              endpoint="/analytics/llm-usage/export"
              params={exportParams}
              filename="llm-usage"
              disabled={overviewLoading || tableLoading || items.length === 0}
            />
          </AnalyticsFilters>
        </AnalyticsPageHeader>

        {error && <p className="text-sm text-red-500">{error}</p>}

        {summary && summary.unpriced_calls > 0 && coverageNotice.visible && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              <span className="font-semibold">{unpricedTokenPct.toFixed(1)}% of tokens have no configured rate.</span>{" "}
              Totals below are the priced subtotal, add rates under LLM Settings › LLM Providers to complete cost
              coverage.
            </span>
            <button
              type="button"
              onClick={coverageNotice.dismiss}
              aria-label="Dismiss pricing coverage notice"
              className="ml-auto shrink-0 rounded p-0.5 opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
            >
              <X className="h-4 w-4" />
            </button>
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

        {/* Padding lives on the Card here, matching the sibling Analytics stat cards */}
        <Card className={cn("w-full bg-card dark:bg-zinc-900 px-4 py-4 shadow-sm sm:px-6 sm:py-6", analyticsFadeUpClass)}>
          {previous && compareDateRange?.from && compareDateRange?.to && (
            <p className="mb-4 text-xs text-muted-foreground/60">
              vs {format(compareDateRange.from, "MMM d")} – {format(compareDateRange.to, "MMM d")}
            </p>
          )}
          <div className={analyticsKpiGridClass(kpis.length)}>
            {kpis.map((k) => (
              <AnalyticsKpiStat
                key={k.label}
                label={k.label}
                value={k.value}
                icon={k.icon}
                sub={k.sub}
                description={k.description}
                subClassName={KPI_SUB_CLASS}
                delta={k.delta}
              />
            ))}
          </div>
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

        <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
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
              emptyState={<LlmUsageTableEmptyState />}
              keyExtractor={(item) => item.key}
              pageSize={10}
              getRowProps={
                dimension === "source"
                  ? (i) =>
                      isEvaluationRow(i)
                        ? {
                            onClick: () => setEvalExpanded((current) => !current),
                            className: "cursor-pointer hover:bg-muted/60 focus-within:bg-muted/60",
                          }
                        : undefined
                  : undefined
              }
              renderSubRows={
                dimension === "source"
                  ? (i) =>
                      isEvaluationRow(i) && evalExpanded ? (
                        <LlmUsageEvaluationMethods
                          items={evalMethods.data?.items ?? []}
                          totalCostUsd={totalItemCost}
                          loading={evalMethods.isPending || evalMethods.isPlaceholderData}
                          error={evalMethods.isError}
                        />
                      ) : null
                  : undefined
              }
            />
          </CardContent>
        </Card>

        {showNodePanel && (
          <LlmUsageBreakdownChart
            items={agentNodes.data?.items ?? []}
            dimensionLabel="Node"
            scopeNote="Workflow node calls only."
            loading={agentNodes.isPending || agentNodes.isPlaceholderData}
            error={agentNodes.error ? "Failed to load node costs for this agent." : null}
          />
        )}
      </div>
    </div>
  );
}

export default LlmUsagePage;

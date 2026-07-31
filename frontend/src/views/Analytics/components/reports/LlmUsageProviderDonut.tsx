import type { ReactNode } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { CHART_NEUTRALS, CHART_SERIES_COLORS } from "@/constants/chartColors";
import { formatUsd } from "@/helpers/formatCurrency";
import { cn } from "@/helpers/utils";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";
import { analyticsFadeUpClass } from "../../constants/animations";

interface LlmUsageProviderDonutProps {
  items: LlmUsageBreakdownItem[];
  loading?: boolean;
}

const TOP_N = 8;
const OTHERS_KEY = "others";
// Grows into whatever height the card already has, never below the original ring height
const RING_BOX = "relative min-h-[13rem] flex-1";
// Percentages, not pixels: the ring fills the box at any width, and the hole still clears a five-figure total
const INNER_RADIUS = "55%";
const OUTER_RADIUS = "100%";
// Mirrors the ResponsiveContainer height below: the label and placeholders centre on the ring, not the box
const CHART_AREA = "h-[90%]";
// Same proportions in CSS, so the loading and unpriced placeholders trace the real ring
const PLACEHOLDER_RING = "flex aspect-square h-full items-center justify-center rounded-full";
const PLACEHOLDER_HOLE = "aspect-square h-[55%] rounded-full bg-card dark:bg-zinc-900";

const sliceColor = (item: LlmUsageBreakdownItem, index: number) =>
  item.key === "unknown" || item.key === OTHERS_KEY
    ? CHART_NEUTRALS.axis
    : CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length];

const formatShare = (pct: number) => (pct > 0 && pct < 1 ? "<1%" : `${Math.round(pct)}%`);

function aggregateOthers(rest: LlmUsageBreakdownItem[]): LlmUsageBreakdownItem {
  return rest.reduce<LlmUsageBreakdownItem>(
    (acc, i) => ({
      ...acc,
      cost_usd: acc.cost_usd + i.cost_usd,
      cost_is_partial: acc.cost_is_partial || i.cost_is_partial,
      total_tokens: acc.total_tokens + i.total_tokens,
      calls: acc.calls + i.calls,
      unpriced_calls: acc.unpriced_calls + i.unpriced_calls,
    }),
    {
      key: OTHERS_KEY,
      label: "Others",
      cost_usd: 0,
      cost_is_partial: false,
      total_tokens: 0,
      calls: 0,
      unpriced_calls: 0,
    }
  );
}

interface ProviderSliceTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: LlmUsageBreakdownItem }>;
  total: number;
  digits: number;
}

function ProviderSliceTooltip({ active, payload, total, digits }: ProviderSliceTooltipProps) {
  const slice = payload?.[0]?.payload;
  if (!active || !slice) return null;
  const stats: Array<[string, ReactNode]> = [
    ["Cost", formatUsd(slice.cost_usd, digits)],
    ["Calls", slice.calls.toLocaleString()],
    ["Tokens", slice.total_tokens.toLocaleString()],
    ["Share", total > 0 ? formatShare((slice.cost_usd / total) * 100) : "—"],
  ];
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1.5 font-semibold text-foreground">{slice.label}</p>
      <dl className="space-y-0.5">
        {stats.map(([term, value]) => (
          <div key={term} className="flex items-baseline gap-4">
            <dt className="text-muted-foreground">{term}</dt>
            <dd className="ml-auto font-semibold tabular-nums text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Provider share of LLM spend: the slice tooltip carries the per-provider detail */
export function LlmUsageProviderDonut({ items, loading }: LlmUsageProviderDonutProps) {
  const ranked = [...items].sort((a, b) => b.cost_usd - a.cost_usd);
  const top = ranked.slice(0, TOP_N);
  const rest = ranked.slice(TOP_N);
  // Providers past the top eight can be unpriced yet still have calls and tokens, so Others follows slice count, not cost
  const slices = rest.length > 0 ? [...top, aggregateOthers(rest)] : top;
  const total = ranked.reduce((s, i) => s + i.cost_usd, 0);
  const digits = total >= 1 ? 2 : 4;
  const priced = total > 0;

  return (
    <Card className={cn("flex flex-col bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardContent className="flex flex-1 flex-col pt-6">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Cost by Provider</h3>
        {loading ? (
          <div className={RING_BOX}>
            <div className={cn(CHART_AREA, "flex items-center justify-center")}>
              <Skeleton className={PLACEHOLDER_RING}>
                <div className={PLACEHOLDER_HOLE} />
              </Skeleton>
            </div>
          </div>
        ) : slices.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <div className={RING_BOX}>
            {/* The list below is the accessible representation of these slices */}
            <div className="absolute inset-0" aria-hidden>
              {priced ? (
                <ResponsiveContainer width="100%" height="90%">
                  <PieChart>
                    <Pie
                      data={slices}
                      dataKey="cost_usd"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      innerRadius={INNER_RADIUS}
                      outerRadius={OUTER_RADIUS}
                      paddingAngle={2}
                      strokeWidth={0}
                      minAngle={2}
                      rootTabIndex={-1}
                    >
                      {slices.map((slice, i) => (
                        <Cell key={slice.key} fill={sliceColor(slice, i)} />
                      ))}
                    </Pie>
                    {/* Recharts anchors pie tooltips on the arc itself; pinning y keeps it off the ring */}
                    <Tooltip
                      content={<ProviderSliceTooltip total={total} digits={digits} />}
                      position={{ y: 0 }}
                      wrapperStyle={{ zIndex: 10 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className={cn(CHART_AREA, "flex items-center justify-center")}>
                  <div className={cn(PLACEHOLDER_RING, "bg-muted")}>
                    <div className={PLACEHOLDER_HOLE} />
                  </div>
                </div>
              )}
            </div>
            <div
              className={cn(
                CHART_AREA,
                "pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center justify-center"
              )}
            >
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground xl:text-xs">Total</span>
              {/* Steps up with the hole, which widens as the ring grows into the card */}
              <span className="text-base font-bold tabular-nums text-foreground lg:text-xl xl:text-2xl">
                {formatUsd(total, digits)}
              </span>
              {!priced && <span className="mt-0.5 text-[11px] text-muted-foreground">no priced spend</span>}
            </div>
            <ul className="sr-only">
              {slices.map((slice) => (
                <li key={slice.key}>
                  {slice.label}: {formatUsd(slice.cost_usd, digits)}, {slice.calls.toLocaleString()} calls,{" "}
                  {slice.total_tokens.toLocaleString()} tokens
                  {priced && `, ${formatShare((slice.cost_usd / total) * 100)} of spend`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

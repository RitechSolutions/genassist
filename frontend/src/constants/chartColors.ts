/**
 * Single source of truth for chart colors.
 *
 * These are plain color strings (not `hsl(var(--chart-*))` tokens) on purpose:
 * Recharts applies them as SVG `fill`/`stroke` attributes, where CSS `var()`
 * references do not resolve. The CSS `--chart-*` tokens in index.css cover
 * className/CSS-based chart chrome; this file covers the values passed to
 * Recharts props. Keep the two in visual sync.
 */

/** Categorical palette for generic multi-series charts (cycled by index). */
export const CHART_SERIES_COLORS = [
  "#10b981",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#06b6d4",
  "#f97316",
  "#84cc16",
  "#ec4899",
  "#14b8a6",
] as const;

/**
 * Semantic colors for the four conversation-quality metrics. Shared by
 * PerformanceChart, AnalyticsMetricsSection, and the Transcripts views so the
 * same metric is always the same color across the product.
 */
export const METRIC_COLORS = {
  satisfaction: "#10b981",
  serviceQuality: "#8b5cf6",
  resolutionRate: "#f59e0b",
  efficiency: "#06b6d4",
} as const;

/** Neutral chart chrome (axis text, gridlines, tooltip/cursor borders). */
export const CHART_NEUTRALS = {
  axis: "#a1a1aa",
  grid: "#f4f4f5",
  border: "#e4e4e7",
} as const;

/** Shared Recharts <Tooltip> contentStyle for the analytics chart family. */
export const chartTooltipStyle = {
  background: "white",
  border: `1px solid ${CHART_NEUTRALS.border}`,
  borderRadius: "10px",
  fontSize: "12px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
} as const;

/** Shared Recharts <Tooltip> cursor for line/area charts. */
export const chartTooltipCursor = {
  stroke: CHART_NEUTRALS.border,
  strokeWidth: 1,
} as const;

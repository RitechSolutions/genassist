import { cn } from "@/helpers/utils";

/** Fade-in used on analytics cards, charts, tables, and skeletons (matches AI Insights). */
export const analyticsFadeUpClass = "animate-fade-up";

/** Fade-in for page titles (used in AnalyticsPageHeader). */
export const analyticsFadeDownClass = "animate-fade-down";

/** Opacity transition while metrics refresh without a full reload. */
export function analyticsRefreshingClassName(refreshing?: boolean) {
  return cn(
    "transition-opacity duration-200",
    refreshing ? "opacity-70" : undefined,
  );
}

import type { ReactNode } from "react";
import { analyticsFadeDownClass, analyticsFadeUpClass } from "../constants/animations";

interface AnalyticsPageHeaderProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

/**
 * Analytics page title + filter toolbar.
 * Mobile: title block, then full-width stacked filters.
 * md–lg: filters below title on one row (scroll if needed).
 * xl+: title and filters side by side.
 */
export function AnalyticsPageHeader({ title, subtitle, children }: AnalyticsPageHeaderProps) {
  return (
    <header className="mb-5 md:mb-6 xl:mb-8">
      <div className="flex flex-col gap-3 md:gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 shrink-0">
          <h1
            className={`mb-0.5 text-xl font-bold md:mb-1 md:text-2xl xl:mb-2 xl:text-3xl ${analyticsFadeDownClass}`}
          >
            {title}
          </h1>
          <p className={`text-xs text-muted-foreground md:text-sm xl:text-base ${analyticsFadeUpClass}`}>
            {subtitle}
          </p>
        </div>
        <div className="min-w-0 w-full md:overflow-x-auto xl:w-auto xl:overflow-visible">
          {children}
        </div>
      </div>
    </header>
  );
}

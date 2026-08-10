import * as React from "react";
import { cn } from "@/helpers/utils";

/**
 * Standardized page and section headings.
 *
 * Use these instead of ad-hoc `<h1 className="text-2xl font-bold ...">` so
 * title size, weight, and color stay consistent across views. Colors use the
 * `text-foreground` token (never literal `text-gray-900` / `text-slate-900`).
 */

type HeadingProps = React.HTMLAttributes<HTMLHeadingElement>;

export function PageTitle({ className, children, ...props }: HeadingProps) {
  return (
    <h1
      className={cn(
        "text-2xl md:text-3xl font-bold tracking-tight text-foreground",
        className
      )}
      {...props}
    >
      {children}
    </h1>
  );
}

export function SectionTitle({ className, children, ...props }: HeadingProps) {
  return (
    <h2
      className={cn("text-lg font-semibold text-foreground", className)}
      {...props}
    >
      {children}
    </h2>
  );
}

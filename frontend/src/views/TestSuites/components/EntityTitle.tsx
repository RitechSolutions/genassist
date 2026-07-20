import React from "react";
import { cn } from "@/lib/utils";

type EntityTitleLevel = "group" | "row";

// Shared title scale so equivalent content looks equivalent across the section.
// Hierarchy comes only from weight/size here — family, color, leading and
// truncation stay identical. "row" (default) covers datasets, workflow groups
// and evaluations, which intentionally share one style today; "group" is kept
// as an extension point if a heavier grouping level is reintroduced later.
const levelClasses: Record<EntityTitleLevel, string> = {
  group: "text-base font-semibold",
  row: "text-sm font-medium",
};

interface EntityTitleProps {
  level?: EntityTitleLevel;
  muted?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const EntityTitle: React.FC<EntityTitleProps> = ({
  level = "row",
  muted = false,
  className,
  children,
}) => (
  <span
    className={cn(
      "block min-w-0 truncate leading-tight",
      levelClasses[level],
      muted ? "text-gray-500" : "text-gray-900",
      className,
    )}
  >
    {children}
  </span>
);

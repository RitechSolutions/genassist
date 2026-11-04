import React from "react";
import { Tag } from "lucide-react";
import { badgeVariants } from "@/components/badge";
import { cn } from "@/helpers/utils";

/** An item's category, small, beside its name. A span, as it sits inside row buttons. */
export const CategoryBadge: React.FC<{ name: string; className?: string }> = ({ name, className }) => (
  <span
    title={`Category: ${name}`}
    className={cn(
      badgeVariants({ variant: "outline" }),
      "max-w-[12rem] shrink-0 gap-1 px-2 py-0 font-normal text-muted-foreground",
      className,
    )}
  >
    <Tag className="h-3 w-3 shrink-0" aria-hidden="true" />
    <span className="sr-only">Category: </span>
    <span className="truncate">{name}</span>
  </span>
);

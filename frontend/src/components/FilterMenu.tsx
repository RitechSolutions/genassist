import type { KeyboardEvent } from "react";
import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { Badge } from "@/components/badge";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { cn } from "@/helpers/utils";

export const ALL_FILTER_VALUE = "all";

export interface FilterMenuOption {
  value: string;
  label: string;
}

/** Pick-one submenu; `ALL_FILTER_VALUE` means the filter is off. */
export interface FilterMenuSelectGroup {
  type?: "select";
  key: string;
  label: string;
  allLabel: string;
  value: string;
  options: FilterMenuOption[];
  onChange: (value: string) => void;
}

/** Free-text submenu; an empty (or whitespace-only) value means the filter is off. */
export interface FilterMenuTextGroup {
  type: "text";
  key: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
}

export type FilterMenuGroup = FilterMenuSelectGroup | FilterMenuTextGroup;

const isActive = (group: FilterMenuGroup) =>
  group.type === "text" ? group.value.trim() !== "" : group.value !== ALL_FILTER_VALUE;

const activeLabel = (group: FilterMenuGroup) =>
  group.type === "text"
    ? group.value.trim()
    : group.options.find((o) => o.value === group.value)?.label ?? group.value;

// Radix menus run typeahead (and arrow-key navigation) on keydown, which would steal focus
// from a text input nested in the menu. Escape still bubbles so the menu can close.
const keepKeysInInput = (event: KeyboardEvent<HTMLInputElement>) => {
  if (event.key !== "Escape") event.stopPropagation();
};

interface FilterMenuProps {
  /** Rendered in order as submenus; clearing also runs in this order. */
  groups: FilterMenuGroup[];
  align?: "start" | "center" | "end";
  className?: string;
}

/**
 * A single "Filters" pill that nests each filter in its own submenu, with an active-count
 * badge and a "Clear filters" action. Used by the Analytics pages and Audit Logs.
 */
export function FilterMenu({ groups, align = "end", className }: FilterMenuProps) {
  const activeCount = groups.filter(isActive).length;

  const clearAll = () => {
    // Reset in array order so a parent filter that also clears its dependants (e.g. the
    // Analytics group filter resets the agent) cannot clobber a value set after it.
    for (const group of groups) group.onChange(group.type === "text" ? "" : ALL_FILTER_VALUE);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Filters${activeCount > 0 ? `, ${activeCount} active` : ""}`}
          className={cn(
            "flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-xs ring-offset-background transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 max-md:w-full xl:h-10 xl:text-sm",
            activeCount > 0
              ? "border-primary/30 bg-primary/5 text-foreground"
              : "border-input bg-card text-muted-foreground hover:bg-muted",
            className
          )}
        >
          <SlidersHorizontal className="h-3.5 w-3.5 shrink-0" />
          <span>Filters</span>
          {activeCount > 0 && (
            <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium text-primary-foreground">
              {activeCount}
            </span>
          )}
          <ChevronDown className="ml-auto h-3 w-3 shrink-0 opacity-50" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="min-w-[14rem]">
        {groups.map((group) => (
          <DropdownMenuSub key={group.key}>
            <DropdownMenuSubTrigger className="flex items-center gap-2">
              <span className="shrink-0">{group.label}</span>
              {isActive(group) && (
                <Badge variant="outline" className="ml-auto max-w-[9rem] truncate px-1 py-0 text-[10px]">
                  {activeLabel(group)}
                </Badge>
              )}
            </DropdownMenuSubTrigger>
            {group.type === "text" ? (
              <DropdownMenuSubContent className="w-[16rem] p-2">
                <Input
                  autoFocus
                  value={group.value}
                  onChange={(e) => group.onChange(e.target.value)}
                  onKeyDown={keepKeysInInput}
                  placeholder={group.placeholder}
                  aria-label={group.label}
                  className="h-8 text-sm"
                />
                {isActive(group) && (
                  <DropdownMenuItem onClick={() => group.onChange("")} className="mt-1 text-muted-foreground">
                    Clear
                  </DropdownMenuItem>
                )}
              </DropdownMenuSubContent>
            ) : (
              <DropdownMenuSubContent className="max-h-64 max-w-[16rem] overflow-y-auto">
                <DropdownMenuItem onClick={() => group.onChange(ALL_FILTER_VALUE)}>
                  <span className="truncate">{group.allLabel}</span>
                  {group.value === ALL_FILTER_VALUE && <span className="ml-auto pl-2">✓</span>}
                </DropdownMenuItem>
                {group.options.length === 0 ? (
                  <DropdownMenuItem disabled>No options available</DropdownMenuItem>
                ) : (
                  group.options.map((option) => (
                    <DropdownMenuItem key={option.value} onClick={() => group.onChange(option.value)}>
                      <span className="truncate" title={option.label}>
                        {option.label}
                      </span>
                      {group.value === option.value && <span className="ml-auto pl-2">✓</span>}
                    </DropdownMenuItem>
                  ))
                )}
              </DropdownMenuSubContent>
            )}
          </DropdownMenuSub>
        ))}
        {activeCount > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={clearAll} className="text-muted-foreground">
              Clear filters
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

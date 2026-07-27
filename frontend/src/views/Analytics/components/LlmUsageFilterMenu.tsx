import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { Badge } from "@/components/badge";
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

interface FilterOption {
  value: string;
  label: string;
}

interface FilterGroup {
  key: string;
  label: string;
  allLabel: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
}

interface LlmUsageFilterMenuProps {
  agents: Array<{ id: string; name: string }>;
  agentFilter: string;
  onAgentFilterChange: (value: string) => void;
  providers: string[];
  provider: string;
  onProviderChange: (value: string) => void;
  models: string[];
  model: string;
  onModelChange: (value: string) => void;
}

/** Agent, provider and model in one pill menu, matching the Transcripts quality filter */
export function LlmUsageFilterMenu({
  agents,
  agentFilter,
  onAgentFilterChange,
  providers,
  provider,
  onProviderChange,
  models,
  model,
  onModelChange,
}: LlmUsageFilterMenuProps) {
  const groups: FilterGroup[] = [
    {
      key: "agent",
      label: "Agent",
      allLabel: "All agents",
      value: agentFilter,
      options: agents.map((a) => ({ value: a.id, label: a.name })),
      onChange: onAgentFilterChange,
    },
    {
      key: "provider",
      label: "Provider",
      allLabel: "All providers",
      value: provider,
      options: providers.map((p) => ({ value: p, label: p })),
      onChange: onProviderChange,
    },
    {
      key: "model",
      label: "Model",
      allLabel: "All models",
      value: model,
      options: models.map((m) => ({ value: m, label: m })),
      onChange: onModelChange,
    },
  ];

  const activeCount = groups.filter((g) => g.value !== ALL_FILTER_VALUE).length;
  const selectedLabel = (group: FilterGroup) =>
    group.options.find((o) => o.value === group.value)?.label ?? group.value;

  const clearAll = () => {
    onAgentFilterChange(ALL_FILTER_VALUE);
    onProviderChange(ALL_FILTER_VALUE);
    onModelChange(ALL_FILTER_VALUE);
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
              : "border-input bg-card text-muted-foreground hover:bg-muted"
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
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        {groups.map((group) => (
          <DropdownMenuSub key={group.key}>
            <DropdownMenuSubTrigger className="flex items-center gap-2">
              <span className="shrink-0">{group.label}</span>
              {group.value !== ALL_FILTER_VALUE && (
                <Badge variant="outline" className="ml-auto max-w-[9rem] truncate px-1 py-0 text-[10px]">
                  {selectedLabel(group)}
                </Badge>
              )}
            </DropdownMenuSubTrigger>
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

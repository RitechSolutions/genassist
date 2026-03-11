import { useMemo } from "react";
import { format, subDays, subMonths, subYears, startOfYear, startOfWeek, startOfMonth } from "date-fns";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/button";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";

export interface DatePreset {
  label: string;
  range: DateRange;
}

function getDefaultPresets(): DatePreset[] {
  const now = new Date();
  return [
    { label: "Today", range: { from: new Date(now.setHours(0, 0, 0, 0)), to: new Date() } },
    { label: "Last 7 days", range: { from: subDays(new Date(), 7), to: new Date() } },
    { label: "Last 30 days", range: { from: subDays(new Date(), 30), to: new Date() } },
    { label: "This week", range: { from: startOfWeek(new Date(), { weekStartsOn: 1 }), to: new Date() } },
    { label: "This month", range: { from: startOfMonth(new Date()), to: new Date() } },
    { label: "Last month", range: { from: startOfMonth(subMonths(new Date(), 1)), to: subDays(startOfMonth(new Date()), 0) } },
    { label: "Year to date", range: { from: startOfYear(new Date()), to: new Date() } },
    { label: "Last year", range: { from: subYears(new Date(), 1), to: new Date() } },
  ];
}

export interface DateRangePickerProps {
  value: DateRange | undefined;
  onChange: (value: DateRange | undefined) => void;
  /** Custom presets — defaults to a built-in set if omitted */
  presets?: DatePreset[];
  /** Placeholder text when no date is selected */
  placeholder?: string;
  /** Popover alignment */
  align?: "start" | "center" | "end";
  /** Number of calendar months to display */
  numberOfMonths?: number;
}

export const DateRangePicker = ({
  value,
  onChange,
  presets: customPresets,
  placeholder = "Pick date range",
  align = "end",
  numberOfMonths = 2,
}: DateRangePickerProps) => {
  const presets = useMemo(() => customPresets ?? getDefaultPresets(), [customPresets]);

  const label = value?.from
    ? value.to
      ? `${format(value.from, "MMM d")} – ${format(value.to, "MMM d, yyyy")}`
      : format(value.from, "MMM d, yyyy")
    : placeholder;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="gap-2 min-w-[200px] justify-start">
          <CalendarIcon className="h-4 w-4 text-muted-foreground" />
          <span>{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0 flex" align={align}>
        <div className="border-r p-2 flex flex-col gap-1 min-w-[140px]">
          {presets.map((preset) => (
            <Button
              key={preset.label}
              variant="ghost"
              size="sm"
              className="justify-start text-xs h-8"
              onClick={() => onChange(preset.range)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="justify-start text-xs h-8 text-muted-foreground"
            onClick={() => onChange(undefined)}
          >
            Clear
          </Button>
        </div>
        <Calendar
          mode="range"
          selected={value}
          onSelect={onChange}
          numberOfMonths={numberOfMonths}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
};

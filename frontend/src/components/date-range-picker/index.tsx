import { useCallback, useMemo } from "react";
import {
  endOfDay,
  endOfYear,
  format,
  isAfter,
  startOfDay,
  subDays,
  subMonths,
  subYears,
  startOfMonth,
  startOfWeek,
  startOfYear,
} from "date-fns";
import type { PeriodPreset } from "@/helpers/analyticsPeriodComparison";
import { PERIOD_PRESET_BY_LABEL } from "@/helpers/analyticsPeriodComparison";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/button";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { cn } from "@/helpers/utils";

export interface DatePreset {
  label: string;
  range: DateRange;
}

function getDefaultPresets(): DatePreset[] {
  const now = new Date();
  const todayStart = startOfDay(now);
  const lastYear = subYears(now, 1);
  return [
    { label: "Today", range: { from: todayStart, to: now } },
    { label: "Last 7 days", range: { from: subDays(now, 7), to: now } },
    { label: "Last 30 days", range: { from: subDays(now, 30), to: now } },
    { label: "This week", range: { from: startOfWeek(now, { weekStartsOn: 1 }), to: now } },
    { label: "This month", range: { from: startOfMonth(now), to: now } },
    {
      label: "Last month",
      range: {
        from: startOfMonth(subMonths(now, 1)),
        to: endOfDay(subDays(startOfMonth(now), 1)),
      },
    },
    { label: "Year to date", range: { from: startOfYear(now), to: now } },
    {
      label: "Last year",
      range: { from: startOfYear(lastYear), to: endOfYear(lastYear) },
    },
  ];
}

export type DateRangePickerChangeMeta = {
  preset: PeriodPreset;
};

export interface DateRangePickerProps {
  value: DateRange | undefined;
  onChange: (value: DateRange | undefined, meta?: DateRangePickerChangeMeta) => void;
  /** Custom presets — defaults to a built-in set if omitted */
  presets?: DatePreset[];
  /** Placeholder text when no date is selected */
  placeholder?: string;
  /** Popover alignment */
  align?: "start" | "center" | "end";
  /** Number of calendar months to display */
  numberOfMonths?: number;
  /** Optional class override for the trigger button */
  triggerClassName?: string;
  /** When true, dates after today cannot be selected (default: false). */
  disableFutureDates?: boolean;
}

function clampRangeToToday(range: DateRange | undefined): DateRange | undefined {
  if (!range) return undefined;
  const todayEnd = endOfDay(new Date());
  const clamp = (d: Date | undefined) => {
    if (!d) return undefined;
    return isAfter(d, todayEnd) ? todayEnd : d;
  };
  const from = clamp(range.from);
  const to = clamp(range.to);
  if (from && to && isAfter(from, to)) {
    return { from: to, to };
  }
  return { from, to };
}

export const DateRangePicker = ({
  value,
  onChange,
  presets: customPresets,
  placeholder = "Pick date range",
  align = "end",
  numberOfMonths = 2,
  triggerClassName,
  disableFutureDates = false,
}: DateRangePickerProps) => {
  const presets = useMemo(() => customPresets ?? getDefaultPresets(), [customPresets]);
  const todayEnd = useMemo(() => endOfDay(new Date()), []);
  const todayStart = useMemo(() => startOfDay(new Date()), []);

  const handleSelect = useCallback(
    (range: DateRange | undefined, preset: PeriodPreset = "custom") => {
      const next = disableFutureDates ? clampRangeToToday(range) : range;
      onChange(next, { preset });
    },
    [disableFutureDates, onChange],
  );

  const handlePreset = useCallback(
    (range: DateRange, label: string) => {
      const preset = PERIOD_PRESET_BY_LABEL[label] ?? "custom";
      handleSelect(range, preset);
    },
    [handleSelect],
  );

  const label = value?.from
    ? value.to
      ? `${format(value.from, "MMM d")} – ${format(value.to, "MMM d, yyyy")}`
      : format(value.from, "MMM d, yyyy")
    : placeholder;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("gap-2 min-w-[200px] justify-start", triggerClassName)}
        >
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
              onClick={() => handlePreset(preset.range, preset.label)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="justify-start text-xs h-8 text-muted-foreground"
            onClick={() => handleSelect(undefined, "custom")}
          >
            Clear
          </Button>
        </div>
        <Calendar
          mode="range"
          selected={value}
          onSelect={(range) => handleSelect(range, "custom")}
          numberOfMonths={numberOfMonths}
          initialFocus
          disabled={disableFutureDates ? { after: todayEnd } : undefined}
          toDate={disableFutureDates ? todayEnd : undefined}
          defaultMonth={disableFutureDates ? todayStart : undefined}
        />
      </PopoverContent>
    </Popover>
  );
};

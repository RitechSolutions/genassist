import { useCallback, useMemo } from "react";
import {
  endOfDay,
  endOfYear,
  format,
  isAfter,
  subDays,
  subMonths,
  subYears,
  startOfMonth,
  startOfWeek,
  startOfYear,
} from "date-fns";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/button";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { cn } from "@/helpers/utils";
import { calendarToday, formatDateRangeLabel } from "@/helpers/dateRange";
import { readTimeZoneMode } from "@/helpers/timeZone";

export interface DatePreset {
  label: string;
  range: DateRange;
}

function getDefaultPresets(): DatePreset[] {
  const today = calendarToday();
  const lastYear = subYears(today, 1);
  return [
    { label: "Today", range: { from: today, to: today } },
    { label: "Last 7 days", range: { from: subDays(today, 7), to: today } },
    { label: "Last 30 days", range: { from: subDays(today, 30), to: today } },
    { label: "This week", range: { from: startOfWeek(today, { weekStartsOn: 1 }), to: today } },
    { label: "This month", range: { from: startOfMonth(today), to: today } },
    {
      label: "Last month",
      range: {
        from: startOfMonth(subMonths(today, 1)),
        to: endOfDay(subDays(startOfMonth(today), 1)),
      },
    },
    { label: "Year to date", range: { from: startOfYear(today), to: today } },
    {
      label: "Last year",
      range: { from: startOfYear(lastYear), to: endOfYear(lastYear) },
    },
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
  /** Optional class override for the trigger button */
  triggerClassName?: string;
  /** When true, dates after today cannot be selected (default: false). */
  disableFutureDates?: boolean;
  /** When true, the trigger is disabled and the picker cannot be opened (default: false). */
  disabled?: boolean;
}

function clampRangeToToday(range: DateRange | undefined): DateRange | undefined {
  if (!range) return undefined;
  const todayEnd = endOfDay(calendarToday());
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
  disabled = false,
}: DateRangePickerProps) => {
  const presets = useMemo(() => customPresets ?? getDefaultPresets(), [customPresets]);
  const today = useMemo(() => calendarToday(), []);
  const todayEnd = useMemo(() => endOfDay(today), [today]);

  const handleSelect = useCallback(
    (range: DateRange | undefined) => {
      onChange(disableFutureDates ? clampRangeToToday(range) : range);
    },
    [disableFutureDates, onChange],
  );

  const handlePreset = useCallback(
    (range: DateRange) => {
      handleSelect(range);
    },
    [handleSelect],
  );

  const zoneSuffix = readTimeZoneMode() === "utc" ? " (UTC)" : "";
  const label = value?.from
    ? (value.to
        ? formatDateRangeLabel(value.from, value.to)
        : format(value.from, "MMM d, yyyy")) + zoneSuffix
    : placeholder;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("gap-2 min-w-[200px] justify-start", triggerClassName)}
          disabled={disabled}
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
              onClick={() => handlePreset(preset.range)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="justify-start text-xs h-8 text-muted-foreground"
            onClick={() => handleSelect(undefined)}
          >
            Clear
          </Button>
        </div>
        <Calendar
          mode="range"
          selected={value}
          onSelect={handleSelect}
          numberOfMonths={numberOfMonths}
          initialFocus
          disabled={disableFutureDates ? { after: todayEnd } : undefined}
          toDate={disableFutureDates ? todayEnd : undefined}
          today={today}
        />
      </PopoverContent>
    </Popover>
  );
};
